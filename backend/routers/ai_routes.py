import html
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

import core.audit as audit
from services import embedding_service
from ai import vector_store
from ai.chunking import build_job_text
from core.config import EVIDENCE_MIN_SIMILARITY
from core.database import get_db
from auth.deps import user_limit
from services.embedding_service import EmbeddingUnavailable
from ai.llm_safety import detect_injection
from services.llm_service import (
    InterviewQuestionsRequest, JobDescriptionRequest, MatchAnalysisRequest, OutreachEmailRequest,
    analyze_candidate_match, generate_interview_questions, generate_job_description, generate_outreach_email,
)
from models import AICandidateMatch, InterviewQuestions, JobDescription, OutreachEmail, Resume, User
from services.resume_service import ResumeService
from services.scoring_service import ScoringService
from services.search_service import semantic_scores
from ai.skills_extractor import SkillsExtractor
from core.utils import fail, logger, safe_json_dumps, safe_json_loads, success_response, validate_email

router = APIRouter(prefix="/api", tags=["ai"])
llm_user = user_limit("llm", 30, 60)


class AnalyzeMatchPayload(BaseModel):
    resume_id: int
    job_description: str = Field(min_length=10, max_length=20000)


class GenerateInterviewQuestionsPayload(BaseModel):
    resume_id: int
    job_title: str = Field(min_length=2, max_length=255)
    job_description: Optional[str] = Field(default=None, max_length=20000)
    required_skills: Optional[List[str]] = None
    candidate_level: Optional[str] = None


class GenerateOutreachEmailPayload(BaseModel):
    resume_id: int
    email_type: str = Field(max_length=50)
    job_title: str = Field(min_length=2, max_length=255)
    company_name: Optional[str] = Field(default=None, max_length=255)
    contact_person: Optional[str] = Field(default=None, max_length=255)
    interview_date: Optional[str] = Field(default=None, max_length=100)
    interview_time: Optional[str] = Field(default=None, max_length=100)
    interview_location: Optional[str] = Field(default=None, max_length=255)


class SendEmailPayload(BaseModel):
    to_email: str = Field(max_length=254)
    subject: str = Field(min_length=1, max_length=300)
    body: str = Field(min_length=1, max_length=10000)


def _ready_resume(db: Session, resume_id: int, user_id: int):
    resume = ResumeService.get_resume_by_id(db, resume_id, user_id)
    if not resume:
        return None, fail(404, "Resume not found")
    if not resume.is_processed or not resume.extracted_text:
        return None, fail(409, "This resume is still being processed. Try again in a moment.")
    return resume, None


def _evidence_for(db: Session, resume_id: int, claims: List[str]) -> List[dict]:
    """Ties each LLM claim back to the resume chunk that best supports it. The
    match is by embedding similarity, so it does not depend on the model
    quoting the resume honestly; claims with no close chunk are flagged."""
    claims = [c for c in claims if c]
    if not claims:
        return []
    vectors = embedding_service.encode(claims)
    out = []
    for claim, vec in zip(claims, vectors):
        best = vector_store.best_chunk(db, resume_id, vec)
        if not best:
            out.append({"claim": claim, "supported": False, "chunk_id": None})
            continue
        out.append({
            "claim": claim,
            "supported": best["similarity"] >= EVIDENCE_MIN_SIMILARITY,
            "similarity": round(best["similarity"], 3),
            "chunk_id": best["chunk_id"],
            "chunk_index": best["chunk_index"],
            "snippet": best["text"][:240],
        })
    return out


@router.post("/ai/analyze-match")
def analyze_candidate_match_endpoint(payload: AnalyzeMatchPayload, request: Request, current_user: User = Depends(llm_user), db: Session = Depends(get_db)):
    resume, error = _ready_resume(db, payload.resume_id, current_user.id)
    if error:
        return error

    required = SkillsExtractor().extract(payload.job_description)
    skills = safe_json_loads(resume.skills, [])
    try:
        sem = semantic_scores(db, build_job_text(payload.job_description, required), [resume.id]).get(resume.id)
    except EmbeddingUnavailable:
        return fail(503, "Analysis is temporarily unavailable (embedding model not loaded)")
    scores = ScoringService.score_candidate(
        semantic_similarity=sem["semantic"] if sem else 0.0, candidate_skills=skills, required_skills=required,
        candidate_experience=resume.experience_years,
    )
    recommendation = ScoringService.get_recommendation(scores["final_score"])

    flags = detect_injection(resume.extracted_text)
    if flags:
        audit.record(db, "prompt_injection_suspected", user_id=current_user.id, resource_type="resume", resource_id=resume.id, request=request, count=len(flags))

    analysis = analyze_candidate_match(MatchAnalysisRequest(
        candidate_resume=resume.extracted_text, job_description=payload.job_description, candidate_name=resume.candidate_name,
        matched_skills=scores["matched_skills"], missing_skills=scores["missing_skills"],
        final_score=scores["final_score"], recommendation=recommendation,
    ))
    strengths = analysis.strengths if analysis else []
    weaknesses = analysis.weaknesses if analysis else []
    explanation = analysis.explanation if analysis else "The AI explanation is unavailable right now. The score above comes from the ranking engine."

    evidence = []
    if analysis:
        try:
            evidence = _evidence_for(db, resume.id, strengths)
        except Exception as e:
            logger.warning(f"evidence lookup failed: {e}")

    db.add(AICandidateMatch(
        resume_id=resume.id, user_id=current_user.id, job_description=payload.job_description,
        strengths=safe_json_dumps(strengths), weaknesses=safe_json_dumps(weaknesses),
        missing_skills=safe_json_dumps(scores["missing_skills"]), recommendation=recommendation,
        match_score=scores["final_score"], explanation=explanation,
    ))
    db.commit()
    audit.record(db, "llm_analysis_requested", user_id=current_user.id, resource_type="resume", resource_id=resume.id, request=request, llm_ok=bool(analysis))

    return success_response(data={
        "recommendation": recommendation, "match_score": scores["final_score"], "explanation": explanation,
        "strengths": strengths, "weaknesses": weaknesses, "missing_skills": scores["missing_skills"],
        "matched_skills": scores["matched_skills"],
        "score_breakdown": {k: scores[k] for k in ("semantic_similarity", "skill_overlap", "experience_match")},
        "evidence": evidence, "security_flags": flags, "ai_explanation_available": bool(analysis),
    })


@router.post("/ai/generate-questions")
def generate_interview_questions_endpoint(payload: GenerateInterviewQuestionsPayload, request: Request, current_user: User = Depends(llm_user), db: Session = Depends(get_db)):
    resume, error = _ready_resume(db, payload.resume_id, current_user.id)
    if error:
        return error
    candidate_skills = safe_json_loads(resume.skills, [])
    required_skills = payload.required_skills or []
    if not required_skills and payload.job_description:
        required_skills = SkillsExtractor().extract(payload.job_description)
    extractor = SkillsExtractor()
    have = set(extractor.extract_from_list(candidate_skills))
    missing_skills = [s for s in extractor.extract_from_list(required_skills) if s not in have]

    level = payload.candidate_level
    if not level:
        years = resume.experience_years or 0
        level = "fresher" if years < 2 else ("intermediate" if years < 5 else "experienced")

    questions = generate_interview_questions(InterviewQuestionsRequest(
        candidate_resume=resume.extracted_text, candidate_skills=candidate_skills, job_title=payload.job_title,
        job_description=payload.job_description or "", required_skills=required_skills, missing_skills=missing_skills,
        candidate_name=resume.candidate_name, candidate_level=level,
    ))
    if not questions:
        return fail(502, "Failed to generate questions", "The AI provider did not return usable output. Try again.")

    db.add(InterviewQuestions(
        resume_id=resume.id, user_id=current_user.id, job_title=payload.job_title,
        technical_questions=safe_json_dumps(questions.technical_questions),
        behavioral_questions=safe_json_dumps(questions.behavioral_questions),
        practical_tasks=safe_json_dumps(questions.practical_tasks),
    ))
    db.commit()
    audit.record(db, "llm_questions_requested", user_id=current_user.id, resource_type="resume", resource_id=resume.id, request=request)
    return success_response(data=questions.model_dump())


@router.post("/ai/generate-email")
def generate_email_endpoint(payload: GenerateOutreachEmailPayload, request: Request, current_user: User = Depends(llm_user), db: Session = Depends(get_db)):
    resume = ResumeService.get_resume_by_id(db, payload.resume_id, current_user.id)
    if not resume:
        return fail(404, "Resume not found")
    hr_name = f"{current_user.first_name or ''} {current_user.last_name or ''}".strip() or current_user.username
    email, _raw = generate_outreach_email(OutreachEmailRequest(
        candidate_name=resume.candidate_name or "Candidate", job_title=payload.job_title, email_type=payload.email_type,
        company_name=payload.company_name or current_user.company, contact_person=payload.contact_person or hr_name,
        interview_date=payload.interview_date, interview_time=payload.interview_time, interview_location=payload.interview_location,
    ))
    if not email:
        return fail(502, "Failed to generate email", "The AI provider did not return a usable email. Try again.")

    db.add(OutreachEmail(
        resume_id=resume.id, user_id=current_user.id, email_type=payload.email_type,
        job_title=payload.job_title, subject_line=email.subject_line, email_body=email.email_body,
    ))
    db.commit()
    return success_response(data={"subject_line": email.subject_line, "email_body": email.email_body, "candidate_email": resume.candidate_email})


@router.post("/ai/generate-job-description")
def generate_jd_endpoint(payload: JobDescriptionRequest, current_user: User = Depends(llm_user), db: Session = Depends(get_db)):
    jd = generate_job_description(payload)
    if not jd:
        return fail(502, "Failed to generate the job description", "The AI provider did not return usable output. Try again.")
    db.add(JobDescription(
        user_id=current_user.id, role_title=payload.job_title[:255], role_shorthand=payload.job_shorthand,
        generated_description=jd.job_description, required_skills=safe_json_dumps(jd.required_skills),
        nice_to_have_skills=safe_json_dumps(jd.nice_to_have_skills),
    ))
    db.commit()
    return success_response(data=jd.model_dump())


@router.post("/email/send")
def send_email_endpoint(
    payload: SendEmailPayload, request: Request, background_tasks: BackgroundTasks,
    current_user: User = Depends(user_limit("email_send", 20, 3600)), db: Session = Depends(get_db),
):
    smtp_server = os.getenv("SMTP_SERVER")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USERNAME")
    smtp_pass = os.getenv("SMTP_PASSWORD")
    sender = os.getenv("SENDER_EMAIL", smtp_user)
    if not smtp_server or not smtp_user or not smtp_pass:
        return fail(400, "Email sending is not configured on this server.")

    recipients = [e.strip() for e in payload.to_email.split(",") if e.strip()]
    if not recipients or len(recipients) > 5 or not all(validate_email(r) for r in recipients):
        return fail(400, "Provide between 1 and 5 valid recipient addresses")

    # The server's SMTP account is shared, so it may only write to this tenant's own candidates.
    known = {
        row[0].lower() for row in db.query(func.lower(Resume.candidate_email))
        .filter(Resume.user_id == current_user.id, Resume.candidate_email.isnot(None)).all()
    }
    if any(r.lower() not in known for r in recipients):
        return fail(400, "You can only email candidates that are in your own resume library")

    subject = "".join(payload.subject.splitlines())[:300]
    paragraphs = [p for p in payload.body.split("\n\n") if p.strip()]
    html_paragraphs = "".join(
        f"<p style='margin:0 0 12px 0;line-height:1.6;'>{html.escape(p).replace(chr(10), '<br>')}</p>" for p in paragraphs
    )
    html_body = f"<html><body style='font-family:sans-serif;font-size:14px;color:#333;max-width:600px;margin:0 auto;padding:20px;'>{html_paragraphs}</body></html>"

    def _send():
        try:
            msg = MIMEMultipart()
            msg["From"], msg["To"], msg["Subject"] = sender, ", ".join(recipients), subject
            msg.attach(MIMEText(payload.body, "plain", "utf-8"))
            msg.attach(MIMEText(html_body, "html", "utf-8"))
            if smtp_port == 465:
                with smtplib.SMTP_SSL(smtp_server, smtp_port, timeout=20) as server:
                    server.login(smtp_user, smtp_pass)
                    server.sendmail(sender, recipients, msg.as_string())
            else:
                with smtplib.SMTP(smtp_server, smtp_port, timeout=20) as server:
                    server.starttls()
                    server.login(smtp_user, smtp_pass)
                    server.sendmail(sender, recipients, msg.as_string())
        except Exception as e:
            logger.error(f"Background email sending failed: {e}")

    background_tasks.add_task(_send)
    audit.record(db, "email_queued", user_id=current_user.id, resource_type="email", request=request, recipients=len(recipients))
    return success_response(message="Email queued for sending")
