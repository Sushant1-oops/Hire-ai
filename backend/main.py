
import os
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'))

import smtplib
from contextlib import asynccontextmanager
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional, List
from uuid import uuid4
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form, status, Header, Cookie, BackgroundTasks, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel
from sqlalchemy.orm import Session
from datetime import datetime

from database import get_db, init_db
from models import User, Resume, SearchHistory, AICandidateMatch, InterviewQuestions, OutreachEmail, JobDescription, Job, Application
from auth import (
    verify_token, UserLoginRequest, UserRegisterRequest, UserResponse,
    login_user, register_user, get_user_by_id, get_user_by_email,
    create_access_token, create_refresh_token
)
from resume_service import ResumeService
from search_service import get_search_service
from job_service import JobService
from pipeline_service import submit_application, process_application_async
from observability import LangSmithTracingMiddleware
from llm_service import (
    get_llm_status, analyze_candidate_match, generate_interview_questions,
    generate_outreach_email, generate_job_description,
    MatchAnalysisRequest, InterviewQuestionsRequest, OutreachEmailRequest, JobDescriptionRequest
)
from utils import logger, error_response, success_response, safe_json_dumps, safe_json_loads
from skills_extractor import SkillsExtractor

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    if os.getenv("SECRET_KEY", "your-secret-key-change-in-production") == "your-secret-key-change-in-production":
        logger.warning("SECRET_KEY is not set — using the insecure default. Set SECRET_KEY in your .env before deploying.")
    try:
        get_search_service()
    except Exception as e:
        logger.warning(f"Search service init failed: {str(e)}")
    yield

app = FastAPI(title="AI Semantic Hiring Assistant", version="1.0.0", lifespan=lifespan)



_allowed_origins_env = os.getenv("ALLOWED_ORIGINS", "*")
ALLOWED_ORIGINS = ["*"] if _allowed_origins_env.strip() == "*" else [o.strip() for o in _allowed_origins_env.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    
    
    allow_credentials=ALLOWED_ORIGINS != ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)



app.add_middleware(LangSmithTracingMiddleware)

def get_current_user(
    token: str | None = Cookie(default=None),
    authorization: str | None = Header(None),
    db: Session = Depends(get_db)
) -> User:
    if not token and authorization:
        parts = authorization.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            token = parts[1]

    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    user_id = verify_token(token)
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

    user = get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user

class SearchRequest(BaseModel):
    query: str
    job_description: Optional[str] = None
    required_skills: Optional[List[str]] = None
    min_experience: Optional[float] = None
    nice_to_have_skills: Optional[List[str]] = None
    nice_to_have_experience: Optional[float] = None
    top_k: int = 10
    min_score: Optional[float] = None

class GenerateInterviewQuestionsPayload(BaseModel):
    resume_id: int
    job_title: str
    job_description: Optional[str] = None
    required_skills: Optional[List[str]] = None
    candidate_level: Optional[str] = None

class GenerateOutreachEmailPayload(BaseModel):
    resume_id: int
    email_type: str
    job_title: str
    company_name: Optional[str] = None
    contact_person: Optional[str] = None
    interview_date: Optional[str] = None
    interview_time: Optional[str] = None
    interview_location: Optional[str] = None

class SendEmailPayload(BaseModel):
    to_email: str
    subject: str
    body: str

class RefreshTokenRequest(BaseModel):
    refresh_token: str

class JobCreateRequest(BaseModel):
    title: str
    description: str
    location: Optional[str] = None
    experience_min: Optional[float] = None
    required_skills: Optional[List[str]] = None

class ApplicationStatusUpdate(BaseModel):
    status: str  

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    
    
    first = exc.errors()[0] if exc.errors() else None
    field = ".".join(str(p) for p in first["loc"] if p != "body") if first else None
    message = f"{field}: {first['msg']}" if first and field else (first["msg"] if first else "Invalid request")
    return JSONResponse(status_code=422, content=error_response(422, message, safe_json_dumps(exc.errors())))

@app.get("/health")
async def health_check():
    return {"status": "healthy", "llm": get_llm_status()}

@app.post("/api/auth/register")
async def register(request: UserRegisterRequest, db: Session = Depends(get_db)):
    result = register_user(db, request)
    if result["error"]:
        return JSONResponse(status_code=400, content=error_response(400, result["error"]))
    
    user_dict = result["user"].model_dump() if hasattr(result["user"], 'model_dump') else result["user"].dict()
    db_user = get_user_by_email(db, request.email)
    
    return success_response(
        data={
            "user": user_dict,
            "access_token": create_access_token(db_user.id),
            "refresh_token": create_refresh_token(db_user.id),
            "token_type": "bearer"
        },
        message="Registration successful"
    )

@app.post("/api/auth/login")
async def login(request: UserLoginRequest, db: Session = Depends(get_db)):
    user = login_user(db, request)
    if not user:
        return JSONResponse(status_code=401, content=error_response(401, "Invalid credentials"))
    
    user_dict = UserResponse.from_orm(user)
    user_dict = user_dict.model_dump() if hasattr(user_dict, 'model_dump') else user_dict.dict()
    
    return success_response(
        data={
            "access_token": create_access_token(user.id),
            "refresh_token": create_refresh_token(user.id),
            "token_type": "bearer",
            "user": user_dict
        },
        message="Login successful"
    )

@app.post("/api/auth/refresh")
async def refresh_token(request: RefreshTokenRequest):
    user_id = verify_token(request.refresh_token)
    if not user_id:
        return JSONResponse(status_code=401, content=error_response(401, "Invalid refresh token"))
    return success_response(data={"access_token": create_access_token(user_id), "token_type": "bearer"})

@app.get("/api/auth/me")
async def get_profile(current_user: User = Depends(get_current_user)):
    user_resp = UserResponse.from_orm(current_user)
    return success_response(data=user_resp.model_dump() if hasattr(user_resp, 'model_dump') else user_resp.dict())

@app.post("/api/resumes/upload")
async def upload_resume(file: UploadFile = File(...), current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    temp_path = f"temp_{uuid4().hex}_{file.filename}"
    try:
        with open(temp_path, "wb") as f: f.write(await file.read())
        service = ResumeService()
        processed_data = service.process_resume(temp_path)
        if not processed_data: return error_response(400, "Failed to process resume")
        
        success, storage_path = service.save_resume_file(temp_path, file.filename)
        if not success: return error_response(400, "Failed to save resume")
        
        resume = service.create_resume_record(db, current_user.id, file.filename, storage_path, processed_data)
        if not resume: return error_response(500, "Failed to create resume record")
        
        search_service = get_search_service()
        embedding_text = search_service.build_resume_embedding_text(
            processed_data["metadata"].get("skills", []),
            processed_data["metadata"].get("experience_years"),
            processed_data["extracted_text"],
        )
        search_service.add_resume_to_index(resume.id, embedding_text)
        search_service.save_index()
        
        return success_response(data={"resume_id": resume.id, "candidate_name": resume.candidate_name}, message="Resume uploaded successfully")
    except Exception as e:
        return error_response(500, "Upload failed", str(e))
    finally:
        if os.path.exists(temp_path): os.remove(temp_path)

@app.post("/api/resumes/upload-batch")
async def upload_resumes_batch(files: List[UploadFile] = File(...), current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    results = {"successful": [], "failed": []}
    service = ResumeService()
    search_service = get_search_service()
    new_ids, new_texts = [], []

    for file in files:
        temp_path = f"temp_{uuid4().hex}_{file.filename}"
        try:
            with open(temp_path, "wb") as f: f.write(await file.read())
            processed_data = service.process_resume(temp_path)
            if not processed_data:
                results["failed"].append({"file": file.filename, "error": "Failed to process"})
                continue
            ok, storage_path = service.save_resume_file(temp_path, file.filename)
            if not ok:
                results["failed"].append({"file": file.filename, "error": "Failed to save"})
                continue
            resume = service.create_resume_record(db, current_user.id, file.filename, storage_path, processed_data)
            if not resume:
                results["failed"].append({"file": file.filename, "error": "DB error"})
                continue
            new_ids.append(resume.id)
            new_texts.append(search_service.build_resume_embedding_text(
                processed_data["metadata"].get("skills", []),
                processed_data["metadata"].get("experience_years"),
                processed_data["extracted_text"],
            ))
            results["successful"].append({"resume_id": resume.id, "candidate_name": resume.candidate_name, "file": file.filename})
        except Exception as e:
            results["failed"].append({"file": file.filename, "error": str(e)})
        finally:
            if os.path.exists(temp_path): os.remove(temp_path)

    if new_ids:
        search_service.add_resumes_batch(new_ids, new_texts)
        search_service.save_index()
    return success_response(data=results, message=f"Uploaded {len(results['successful'])} of {len(files)} resumes")

@app.get("/api/resumes")
async def list_resumes(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    resumes = ResumeService.get_user_resumes(db, current_user.id)
    return success_response(data=[{
        "id": r.id, "candidate_name": r.candidate_name, "candidate_email": r.candidate_email,
        "candidate_phone": r.candidate_phone, "skills": safe_json_loads(r.skills),
        "experience_years": r.experience_years, "created_at": r.created_at.isoformat()
    } for r in resumes])

@app.get("/api/resumes/{resume_id}")
async def get_resume(resume_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    resume = ResumeService.get_resume_by_id(db, resume_id, current_user.id)
    if not resume: return error_response(404, "Resume not found")
    return success_response(data={
        "id": resume.id, "candidate_name": resume.candidate_name, "candidate_email": resume.candidate_email,
        "candidate_phone": resume.candidate_phone, "skills": safe_json_loads(resume.skills),
        "experience_years": resume.experience_years, "education": safe_json_loads(resume.education),
        "extracted_text": resume.extracted_text[:2000] if resume.extracted_text else "",
        "created_at": resume.created_at.isoformat()
    })

@app.delete("/api/resumes/{resume_id}")
async def delete_resume(resume_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    success = ResumeService.delete_resume(db, resume_id, current_user.id)
    if not success: return error_response(404, "Resume not found")
    return success_response(message="Resume deleted successfully")

@app.post("/api/resumes/reindex")
async def reindex_resumes(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    
    search_service = get_search_service()
    ok = search_service.rebuild_index(db, current_user.id)
    if not ok: return error_response(500, "Failed to rebuild search index")
    return success_response(message="Search index rebuilt")







@app.post("/api/jobs")
async def create_job(payload: JobCreateRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    job = JobService.create_job(
        db, current_user.id, title=payload.title, description=payload.description,
        location=payload.location, experience_min=payload.experience_min,
        required_skills=payload.required_skills,
    )
    return success_response(data=job.to_dict(), message="Job created")

@app.get("/api/jobs")
async def list_jobs(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    jobs = JobService.get_user_jobs(db, current_user.id)
    counts = JobService.get_application_counts(db, [job.id for job in jobs])
    return success_response(data=[{
        **job.to_dict(),
        "application_count": counts.get(job.id, 0),
    } for job in jobs])

@app.get("/api/jobs/{job_id}")
async def get_job(job_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    job = JobService.get_job_by_id(db, job_id, current_user.id)
    if not job: return error_response(404, "Job not found")
    return success_response(data={**job.to_dict(), "application_count": len(job.applications)})

@app.patch("/api/jobs/{job_id}/status")
async def update_job_status(job_id: int, payload: ApplicationStatusUpdate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if payload.status not in ("open", "closed"):
        return error_response(400, "status must be 'open' or 'closed'")
    job = JobService.set_job_status(db, job_id, current_user.id, payload.status)
    if not job: return error_response(404, "Job not found")
    return success_response(data=job.to_dict())

@app.get("/api/jobs/{job_id}/applications")
async def get_job_applications(job_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    job = JobService.get_job_by_id(db, job_id, current_user.id)
    if not job: return error_response(404, "Job not found")
    search_service = get_search_service()
    ranked = JobService.rank_applications(db, job, search_service)
    return success_response(data={"job": job.to_dict(), "applications": ranked})

@app.patch("/api/applications/{application_id}/status")
async def update_application_status(application_id: int, payload: ApplicationStatusUpdate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    valid_statuses = {"received", "screened", "shortlisted", "rejected", "interview", "hired"}
    if payload.status not in valid_statuses:
        return error_response(400, f"status must be one of {sorted(valid_statuses)}")
    application = JobService.update_application_status(db, application_id, current_user.id, payload.status)
    if not application: return error_response(404, "Application not found")
    return success_response(data=application.to_dict())




@app.get("/api/public/jobs/{slug}")
async def get_public_job(slug: str, db: Session = Depends(get_db)):
    job = JobService.get_public_job(db, slug)
    if not job: return error_response(404, "This job posting is no longer available")
    return success_response(data={
        "title": job.title, "location": job.location, "experience_min": job.experience_min,
        "description": job.description, "required_skills": safe_json_loads(job.required_skills, []),
    })

@app.post("/api/public/jobs/{slug}/apply")
async def apply_to_job(
    slug: str,
    background_tasks: BackgroundTasks,
    full_name: str = Form(...),
    email: str = Form(...),
    phone: Optional[str] = Form(None),
    resume: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    job = JobService.get_public_job(db, slug)
    if not job: return error_response(404, "This job posting is no longer available")
    if not full_name.strip() or not email.strip():
        return error_response(400, "Full name and email are required")

    
    
    
    temp_path = f"temp_apply_{uuid4().hex}_{resume.filename}"
    try:
        with open(temp_path, "wb") as f: f.write(await resume.read())
        service = ResumeService()

        
        
        
        try:
            candidate_resume, application, _is_new = submit_application(
                db=db, job=job, resume_service=service, uploaded_file_path=temp_path,
                resume_filename=resume.filename, full_name=full_name.strip(),
                email=email.strip(), phone=(phone or "").strip() or None,
            )
        except ValueError as ve:
            if os.path.exists(temp_path): os.remove(temp_path)
            return error_response(400, str(ve))

        
        
        background_tasks.add_task(
            process_application_async,
            application_id=application.id, resume_id=candidate_resume.id,
            job_id=job.id, temp_file_path=temp_path,
        )

        return success_response(
            data={"application_id": application.id, "job_title": job.title},
            message="Application received — we're processing your resume now",
        )
    except Exception as e:
        logger.error(f"Application failed: {str(e)}")
        if os.path.exists(temp_path): os.remove(temp_path)
        return error_response(500, "Failed to submit application", str(e))

@app.post("/api/search")
async def semantic_search(request: SearchRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        required_skills = request.required_skills or []
        if not required_skills and request.job_description:
            required_skills = SkillsExtractor().extract(request.job_description)

        search_service = get_search_service()
        search_result = search_service.search_with_scoring(
            query=request.query, required_skills=required_skills, top_k=request.top_k,
            db=db, user_id=current_user.id, min_experience=request.min_experience,
            nice_to_have_skills=request.nice_to_have_skills, nice_to_have_experience=request.nice_to_have_experience,
            min_score=request.min_score
        )
        results = search_result.get("results", [])
        summary = search_result.get("summary", {})

        db.add(SearchHistory(
            user_id=current_user.id, query=request.query,
            required_skills=safe_json_dumps(required_skills),
            min_experience=request.min_experience, results_count=len(results)
        ))
        db.commit()

        return success_response(data={"results": results, "summary": summary}, message=f"Found {summary.get('total_above_threshold', len(results))} matching candidates")
    except Exception as e:
        return error_response(500, "Search failed", str(e))

@app.post("/api/ai/analyze-match")
async def analyze_candidate_match_endpoint(payload: dict, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    resume_id = payload.get("resume_id")
    job_description = payload.get("job_description")
    if not resume_id or not job_description: return error_response(400, "resume_id and job_description are required")
    
    resume = ResumeService.get_resume_by_id(db, resume_id, current_user.id)
    if not resume: return error_response(404, "Resume not found")

    analysis = analyze_candidate_match(MatchAnalysisRequest(candidate_resume=resume.extracted_text, job_description=job_description, candidate_name=resume.candidate_name))
    if not analysis: return error_response(500, "Failed to analyze match")

    match = AICandidateMatch(
        resume_id=resume_id, user_id=current_user.id, job_description=job_description,
        strengths=safe_json_dumps(analysis.strengths), weaknesses=safe_json_dumps(analysis.weaknesses),
        missing_skills=safe_json_dumps(analysis.missing_skills), recommendation=analysis.recommendation,
        match_score=analysis.match_score, explanation=analysis.explanation
    )
    db.add(match)
    db.commit()

    return success_response(data={
        "recommendation": analysis.recommendation, "match_score": analysis.match_score,
        "explanation": analysis.explanation, "strengths": analysis.strengths,
        "weaknesses": analysis.weaknesses, "missing_skills": analysis.missing_skills
    })

@app.post("/api/ai/generate-questions")
async def generate_interview_questions_endpoint(payload: GenerateInterviewQuestionsPayload, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    resume = ResumeService.get_resume_by_id(db, payload.resume_id, current_user.id)
    if not resume: return error_response(404, "Resume not found")

    candidate_skills = safe_json_loads(resume.skills, [])
    required_skills = payload.required_skills or []
    if not required_skills and payload.job_description:
        required_skills = SkillsExtractor().extract(payload.job_description)
        
    missing_skills = [s for s in required_skills if s not in candidate_skills]

    candidate_level = payload.candidate_level
    if not candidate_level:
        years = resume.experience_years or 0
        candidate_level = "fresher" if years < 2 else ("intermediate" if years < 5 else "experienced")

    try:
        questions = generate_interview_questions(InterviewQuestionsRequest(
            candidate_resume=resume.extracted_text, candidate_skills=candidate_skills,
            job_title=payload.job_title, job_description=payload.job_description or "",
            required_skills=required_skills, missing_skills=missing_skills,
            candidate_name=resume.candidate_name, candidate_level=candidate_level
        ))
        if not questions: raise RuntimeError("LLM returned no questions")

        interview = InterviewQuestions(
            resume_id=payload.resume_id, user_id=current_user.id, job_title=payload.job_title,
            technical_questions=safe_json_dumps(questions.technical_questions),
            behavioral_questions=safe_json_dumps(questions.behavioral_questions),
            practical_tasks=safe_json_dumps(questions.practical_tasks)
        )
        db.add(interview)
        db.commit()
    except RuntimeError as e:
        return error_response(500, "Failed to generate questions", str(e))

    return success_response(data={
        "technical_questions": questions.technical_questions,
        "behavioral_questions": questions.behavioral_questions,
        "practical_tasks": questions.practical_tasks
    })

@app.post("/api/ai/generate-email")
async def generate_email_endpoint(payload: GenerateOutreachEmailPayload, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    resume = ResumeService.get_resume_by_id(db, payload.resume_id, current_user.id)
    if not resume: return error_response(404, "Resume not found")

    
    
    
    
    hr_name = f"{current_user.first_name or ''} {current_user.last_name or ''}".strip() or current_user.username
    company_name = payload.company_name or current_user.company
    contact_person = payload.contact_person or hr_name

    try:
        email, raw = generate_outreach_email(OutreachEmailRequest(
            candidate_name=resume.candidate_name or "Candidate", job_title=payload.job_title, email_type=payload.email_type,
            company_name=company_name, contact_person=contact_person,
            interview_date=payload.interview_date, interview_time=payload.interview_time, interview_location=payload.interview_location
        ))
        if not email: raise RuntimeError(raw or "LLM returned no email")

        db.add(OutreachEmail(
            resume_id=payload.resume_id, user_id=current_user.id, email_type=payload.email_type,
            job_title=payload.job_title, subject_line=email.subject_line, email_body=email.email_body
        ))
        db.commit()
    except RuntimeError as e:
        return error_response(500, "Failed to generate email", str(e))

    return success_response(data={"subject_line": email.subject_line, "email_body": email.email_body, "candidate_email": resume.candidate_email})

@app.post("/api/email/send")
async def send_email_endpoint(payload: SendEmailPayload, background_tasks: BackgroundTasks, current_user: User = Depends(get_current_user)):
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'), override=True)
    
    smtp_server = os.getenv("SMTP_SERVER")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USERNAME")
    smtp_pass = os.getenv("SMTP_PASSWORD")
    sender = os.getenv("SENDER_EMAIL", smtp_user)

    if not smtp_server or not smtp_user or not smtp_pass:
        return error_response(400, "Email sending not configured.")

    def _send_email_task():
        try:
            msg = MIMEMultipart()
            msg["From"] = sender
            to_emails = [e.strip() for e in payload.to_email.split(',')] if ',' in payload.to_email else [payload.to_email.strip()]
            msg["To"] = ", ".join(to_emails)
            msg["Subject"] = "".join(payload.subject.splitlines())
            
            paragraphs = payload.body.split("\n\n")
            html_paragraphs = "".join(f"<p style='margin: 0 0 12px 0; line-height: 1.6;'>{p.replace(chr(10), '<br>')}</p>" for p in paragraphs if p.strip())
            html_body = f"<html><body style='font-family: sans-serif; font-size: 14px; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;'>{html_paragraphs}</body></html>"
            msg.attach(MIMEText(html_body, "html", "utf-8"))

            if smtp_port == 465:
                with smtplib.SMTP_SSL(smtp_server, smtp_port) as server:
                    server.login(smtp_user, smtp_pass)
                    server.sendmail(sender, to_emails, msg.as_string())
            else:
                with smtplib.SMTP(smtp_server, smtp_port) as server:
                    server.starttls()
                    server.login(smtp_user, smtp_pass)
                    server.sendmail(sender, to_emails, msg.as_string())
        except Exception as e:
            logger.error(f"Background email sending failed: {str(e)}")

    background_tasks.add_task(_send_email_task)
    return success_response(message="Email queued for sending in the background")

@app.post("/api/ai/generate-job-description")
async def generate_jd_endpoint(request: JobDescriptionRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        jd = generate_job_description(request)
        if not jd: raise RuntimeError("LLM returned no job description")

        db.add(JobDescription(
            user_id=current_user.id, role_title=request.job_title, role_shorthand=request.job_shorthand,
            generated_description=jd.job_description, required_skills=safe_json_dumps(jd.required_skills),
            nice_to_have_skills=safe_json_dumps(jd.nice_to_have_skills)
        ))
        db.commit()
    except RuntimeError as e:
        return error_response(500, "Failed to generate JD", str(e))

    return success_response(data={"job_description": jd.job_description, "required_skills": jd.required_skills, "nice_to_have_skills": jd.nice_to_have_skills})

@app.get("/api/dashboard/stats")
async def get_dashboard_stats(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    stats = ResumeService.get_resume_statistics(db, current_user.id)
    recent_searches = db.query(SearchHistory).filter(SearchHistory.user_id == current_user.id).order_by(SearchHistory.created_at.desc()).limit(5).all()
    return success_response(data={
        "total_resumes": stats["total_resumes"], "avg_experience": stats["avg_experience"],
        "top_skills": stats["top_skills"], "experience_distribution": stats["experience_distribution"],
        "recent_searches": [{"query": s.query, "results_count": s.results_count, "created_at": s.created_at.isoformat()} for s in recent_searches]
    })

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)