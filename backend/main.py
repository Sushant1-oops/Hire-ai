"""
Main FastAPI application for AI HR SaaS platform.
Complete REST API with authentication, resume management, semantic search, and AI features.
"""

import os
from dotenv import load_dotenv

# Load environment variables from the root .env file
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'))

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional, List
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, status, Header
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session
from datetime import datetime

from database import get_db, init_db
from models import User, Resume, SearchHistory, SearchResult, AICandidateMatch, InterviewQuestions, OutreachEmail, JobDescription
from auth import (
    verify_token, UserLoginRequest, UserRegisterRequest, UserResponse,
    TokenResponse, login_user, register_user, get_user_by_id, hash_password,
    create_access_token, create_refresh_token
)
from resume_service import ResumeService
from search_service import get_search_service
from scoring_service import ScoringService, ScoringAnalytics
from llm_service import (
    check_ollama_health, check_groq_health, get_llm_status, get_active_provider,
    analyze_candidate_match, generate_interview_questions,
    generate_outreach_email, generate_job_description,
    MatchAnalysisRequest, InterviewQuestionsRequest, OutreachEmailRequest, JobDescriptionRequest
)
from utils import logger, error_response, success_response, safe_json_dumps, safe_json_loads

app = FastAPI(
    title="AI Semantic Hiring Assistant",
    description="Production-ready HR SaaS platform with semantic search",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==================== DEPENDENCIES ====================
def get_current_user(
    token: str | None = None,
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


# ==================== REQUEST MODELS ====================
class SearchRequest(BaseModel):
    query: str
    required_skills: Optional[List[str]] = None
    min_experience: Optional[float] = None
    nice_to_have_skills: Optional[List[str]] = None
    nice_to_have_experience: Optional[float] = None
    top_k: int = 10

class GenerateInterviewQuestionsPayload(BaseModel):
    resume_id: int
    job_title: str
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


# ==================== HEALTH ====================
@app.get("/health")
async def health_check():
    llm_status = get_llm_status()
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "active_llm_provider": llm_status["active_provider"],
        "groq": llm_status["groq"],
        "ollama": llm_status["ollama"],
    }

@app.post("/api/setup")
async def setup_system():
    try:
        init_db()
        search_service = get_search_service()
        return success_response(
            data={"database": "initialized", "faiss_index": "ready", "vectors": search_service.index.ntotal},
            message="System setup complete"
        )
    except Exception as e:
        logger.error(f"Setup error: {str(e)}")
        return error_response(500, "Setup failed", str(e))


# ==================== AUTHENTICATION ====================
@app.post("/api/auth/register", response_model=dict)
async def register(request: UserRegisterRequest, db: Session = Depends(get_db)):
    try:
        result = register_user(db, request)
        if result["error"]:
            return error_response(400, result["error"])
        if not result["user"]:
            return error_response(400, "Registration failed")

        user_data = result["user"]
        # user_data is a UserResponse pydantic model — convert to dict
        user_dict = user_data.model_dump() if hasattr(user_data, 'model_dump') else user_data.dict()

        # Get actual user from DB for token generation
        from auth import get_user_by_email
        db_user = get_user_by_email(db, request.email)
        access_token = create_access_token(db_user.id)
        refresh_token = create_refresh_token(db_user.id)

        logger.info(f"New user registered: {request.email}")
        return success_response(
            data={
                "user": user_dict,
                "access_token": access_token,
                "refresh_token": refresh_token,
                "token_type": "bearer"
            },
            message="Registration successful"
        )
    except Exception as e:
        logger.error(f"Registration error: {str(e)}")
        return error_response(500, "Registration failed", str(e))


@app.post("/api/auth/login", response_model=dict)
async def login(request: UserLoginRequest, db: Session = Depends(get_db)):
    try:
        user = login_user(db, request)
        if not user:
            return error_response(401, "Invalid credentials")

        access_token = create_access_token(user.id)
        refresh_token = create_refresh_token(user.id)

        user_dict = UserResponse.from_orm(user)
        user_dict = user_dict.model_dump() if hasattr(user_dict, 'model_dump') else user_dict.dict()

        logger.info(f"User logged in: {request.email}")
        return success_response(
            data={
                "access_token": access_token,
                "refresh_token": refresh_token,
                "token_type": "bearer",
                "user": user_dict
            },
            message="Login successful"
        )
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        return error_response(500, "Login failed", str(e))


@app.post("/api/auth/refresh", response_model=dict)
async def refresh_token(request: RefreshTokenRequest):
    user_id = verify_token(request.refresh_token)
    if not user_id:
        return error_response(401, "Invalid refresh token")
    return success_response(data={
        "access_token": create_access_token(user_id),
        "token_type": "bearer"
    })


@app.get("/api/auth/me", response_model=dict)
async def get_profile(current_user: User = Depends(get_current_user)):
    try:
        user_resp = UserResponse.from_orm(current_user)
        user_dict = user_resp.model_dump() if hasattr(user_resp, 'model_dump') else user_resp.dict()
        return success_response(data=user_dict)
    except Exception as e:
        logger.error(f"Profile error: {str(e)}")
        return error_response(500, "Error fetching profile")


# ==================== RESUME MANAGEMENT ====================
@app.post("/api/resumes/upload")
async def upload_resume(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        temp_path = f"temp_{file.filename}"
        try:
            contents = await file.read()
            with open(temp_path, "wb") as f:
                f.write(contents)

            service = ResumeService()
            processed_data = service.process_resume(temp_path)
            if not processed_data:
                return error_response(400, "Failed to process resume")

            success, storage_path = service.save_resume_file(temp_path, file.filename)
            if not success:
                return error_response(400, "Failed to save resume")

            resume = service.create_resume_record(db, current_user.id, file.filename, storage_path, processed_data)
            if not resume:
                return error_response(500, "Failed to create resume record")

            search_service = get_search_service()
            search_service.add_resume_to_index(resume.id, processed_data["extracted_text"])
            search_service.save_index()

            logger.info(f"Resume uploaded: {file.filename} (ID: {resume.id})")
            return success_response(
                data={
                    "resume_id": resume.id,
                    "candidate_name": resume.candidate_name,
                    "candidate_email": resume.candidate_email,
                    "candidate_phone": resume.candidate_phone,
                    "skills": safe_json_loads(resume.skills),
                    "experience_years": resume.experience_years,
                    "text_length": len(processed_data["extracted_text"])
                },
                message="Resume uploaded successfully"
            )
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)
    except Exception as e:
        logger.error(f"Upload error: {str(e)}")
        return error_response(500, "Upload failed", str(e))


@app.post("/api/resumes/upload-batch")
async def upload_resumes_batch(
    files: List[UploadFile] = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Upload multiple resumes at once."""
    results = {"successful": [], "failed": []}

    service = ResumeService()
    search_service = get_search_service()
    new_ids = []
    new_texts = []

    for file in files:
        temp_path = f"temp_{file.filename}"
        try:
            contents = await file.read()
            with open(temp_path, "wb") as f:
                f.write(contents)

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
            new_texts.append(processed_data["extracted_text"])

            results["successful"].append({
                "resume_id": resume.id,
                "candidate_name": resume.candidate_name,
                "file": file.filename
            })
        except Exception as e:
            results["failed"].append({"file": file.filename, "error": str(e)})
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    # Batch add to search index
    if new_ids:
        search_service.add_resumes_batch(new_ids, new_texts)
        search_service.save_index()

    return success_response(
        data=results,
        message=f"Uploaded {len(results['successful'])} of {len(files)} resumes"
    )


@app.get("/api/resumes")
async def list_resumes(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        resumes = ResumeService.get_user_resumes(db, current_user.id)
        resume_list = [
            {
                "id": r.id,
                "candidate_name": r.candidate_name,
                "candidate_email": r.candidate_email,
                "candidate_phone": r.candidate_phone,
                "skills": safe_json_loads(r.skills),
                "experience_years": r.experience_years,
                "created_at": r.created_at.isoformat()
            }
            for r in resumes
        ]
        return success_response(data=resume_list)
    except Exception as e:
        logger.error(f"List resumes error: {str(e)}")
        return error_response(500, "Error fetching resumes")


@app.get("/api/resumes/{resume_id}")
async def get_resume(resume_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        resume = ResumeService.get_resume_by_id(db, resume_id, current_user.id)
        if not resume:
            return error_response(404, "Resume not found")
        return success_response(data={
            "id": resume.id,
            "candidate_name": resume.candidate_name,
            "candidate_email": resume.candidate_email,
            "candidate_phone": resume.candidate_phone,
            "skills": safe_json_loads(resume.skills),
            "experience_years": resume.experience_years,
            "education": safe_json_loads(resume.education),
            "extracted_text": resume.extracted_text[:2000] if resume.extracted_text else "",
            "created_at": resume.created_at.isoformat()
        })
    except Exception as e:
        logger.error(f"Get resume error: {str(e)}")
        return error_response(500, "Error fetching resume")


@app.delete("/api/resumes/{resume_id}")
async def delete_resume(resume_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        success = ResumeService.delete_resume(db, resume_id, current_user.id)
        if not success:
            return error_response(404, "Resume not found")
        return success_response(message="Resume deleted successfully")
    except Exception as e:
        logger.error(f"Delete resume error: {str(e)}")
        return error_response(500, "Error deleting resume")


# ==================== SEMANTIC SEARCH ====================
@app.post("/api/search")
async def semantic_search(request: SearchRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        search_service = get_search_service()
        results = search_service.search_with_scoring(
            query=request.query,
            required_skills=request.required_skills,
            top_k=request.top_k,
            db=db,
            user_id=current_user.id,
            min_experience=request.min_experience,
            nice_to_have_skills=request.nice_to_have_skills,
            nice_to_have_experience=request.nice_to_have_experience
        )

        search_history = SearchHistory(
            user_id=current_user.id,
            query=request.query,
            required_skills=safe_json_dumps(request.required_skills),
            min_experience=request.min_experience,
            results_count=len(results)
        )
        db.add(search_history)
        db.commit()

        return success_response(data=results, message=f"Found {len(results)} candidates")
    except Exception as e:
        logger.error(f"Search error: {str(e)}")
        return error_response(500, "Search failed", str(e))


# ==================== AI FEATURES ====================
@app.post("/api/ai/analyze-match")
async def analyze_candidate_match_endpoint(payload: dict, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        resume_id = payload.get("resume_id")
        job_description = payload.get("job_description")
        if not resume_id or not job_description:
            return error_response(400, "resume_id and job_description are required")

        resume = ResumeService.get_resume_by_id(db, resume_id, current_user.id)
        if not resume:
            return error_response(404, "Resume not found")

        request = MatchAnalysisRequest(
            candidate_resume=resume.extracted_text,
            job_description=job_description,
            candidate_name=resume.candidate_name
        )
        analysis = analyze_candidate_match(request)
        if not analysis:
            return error_response(500, "Failed to analyze match")

        match = AICandidateMatch(
            resume_id=resume_id, user_id=current_user.id,
            job_description=job_description,
            strengths=safe_json_dumps(analysis.strengths),
            weaknesses=safe_json_dumps(analysis.weaknesses),
            missing_skills=safe_json_dumps(analysis.missing_skills),
            recommendation=analysis.recommendation,
            match_score=analysis.match_score,
            explanation=analysis.explanation
        )
        db.add(match)
        db.commit()

        return success_response(data={
            "recommendation": analysis.recommendation,
            "match_score": analysis.match_score,
            "explanation": analysis.explanation,
            "strengths": analysis.strengths,
            "weaknesses": analysis.weaknesses,
            "missing_skills": analysis.missing_skills
        })
    except Exception as e:
        logger.error(f"Match analysis error: {str(e)}")
        return error_response(500, "Analysis failed", str(e))


@app.post("/api/ai/generate-questions")
async def generate_interview_questions_endpoint(payload: GenerateInterviewQuestionsPayload, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        resume = ResumeService.get_resume_by_id(db, payload.resume_id, current_user.id)
        if not resume:
            return error_response(404, "Resume not found")

        candidate_level = payload.candidate_level
        if not candidate_level:
            years = resume.experience_years or 0
            candidate_level = "fresher" if years < 2 else ("intermediate" if years < 5 else "experienced")

        request = InterviewQuestionsRequest(
            candidate_resume=resume.extracted_text,
            job_title=payload.job_title,
            candidate_name=resume.candidate_name,
            candidate_level=candidate_level
        )
        questions = generate_interview_questions(request)
        if not questions:
            return error_response(500, "Failed to generate questions")

        interview = InterviewQuestions(
            resume_id=payload.resume_id, user_id=current_user.id,
            job_title=payload.job_title,
            technical_questions=safe_json_dumps(questions.technical_questions),
            behavioral_questions=safe_json_dumps(questions.behavioral_questions),
            practical_tasks=safe_json_dumps(questions.practical_tasks)
        )
        db.add(interview)
        db.commit()

        return success_response(data={
            "technical_questions": questions.technical_questions,
            "behavioral_questions": questions.behavioral_questions,
            "practical_tasks": questions.practical_tasks
        })
    except Exception as e:
        logger.error(f"Question generation error: {str(e)}")
        return error_response(500, "Generation failed", str(e))


@app.post("/api/ai/generate-email")
async def generate_email_endpoint(payload: GenerateOutreachEmailPayload, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        resume = ResumeService.get_resume_by_id(db, payload.resume_id, current_user.id)
        if not resume:
            return error_response(404, "Resume not found")

        request = OutreachEmailRequest(
            candidate_name=resume.candidate_name or "Candidate",
            job_title=payload.job_title, email_type=payload.email_type,
            company_name=payload.company_name, contact_person=payload.contact_person,
            interview_date=payload.interview_date, interview_time=payload.interview_time,
            interview_location=payload.interview_location
        )
        email, raw = generate_outreach_email(request)
        if not email:
            return error_response(500, "Failed to generate email", raw or "no response")

        outreach = OutreachEmail(
            resume_id=payload.resume_id, user_id=current_user.id,
            email_type=payload.email_type, job_title=payload.job_title,
            subject_line=email.subject_line, email_body=email.email_body
        )
        db.add(outreach)
        db.commit()

        return success_response(data={
            "subject_line": email.subject_line,
            "email_body": email.email_body,
            "candidate_email": resume.candidate_email
        })
    except Exception as e:
        logger.error(f"Email generation error: {str(e)}")
        return error_response(500, "Generation failed", str(e))


@app.post("/api/email/send")
async def send_email_endpoint(payload: SendEmailPayload, current_user: User = Depends(get_current_user)):
    """Send an email via SMTP."""
    # Force reload of dotenv in case the user updated .env without restarting the app
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'), override=True)
    
    smtp_server = os.getenv("SMTP_SERVER")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USERNAME")
    smtp_pass = os.getenv("SMTP_PASSWORD")
    sender = os.getenv("SENDER_EMAIL", smtp_user)

    if not smtp_server or not smtp_user or not smtp_pass:
        return error_response(400, "Email sending not configured. Set SMTP_SERVER, SMTP_USERNAME, SMTP_PASSWORD in .env")

    try:
        msg = MIMEMultipart()
        msg["From"] = sender
        
        # Handle multiple emails safely
        to_emails = [e.strip() for e in payload.to_email.split(',')] if ',' in payload.to_email else [payload.to_email.strip()]
        msg["To"] = ", ".join(to_emails)
        
        # Remove any newlines from subject to prevent header injection errors
        clean_subject = "".join(payload.subject.splitlines())
        msg["Subject"] = clean_subject
        
        # Convert plain text to styled HTML for proper formatting in email clients
        paragraphs = payload.body.split("\n\n")
        html_paragraphs = "".join(f"<p style='margin: 0 0 12px 0; line-height: 1.6;'>{p.replace(chr(10), '<br>')}</p>" for p in paragraphs if p.strip())
        html_body = f"""
        <html>
        <body style="font-family: 'Segoe UI', Arial, sans-serif; font-size: 14px; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
            {html_paragraphs}
        </body>
        </html>
        """
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

        logger.info(f"Email sent to {payload.to_email}")
        return success_response(message="Email sent successfully")
    except Exception as e:
        logger.error(f"Email send error: {str(e)}")
        return error_response(500, f"Failed to send email: {str(e)}")


@app.post("/api/ai/generate-job-description")
async def generate_jd_endpoint(request: JobDescriptionRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        jd = generate_job_description(request)
        if not jd:
            return error_response(500, "Failed to generate JD")

        job = JobDescription(
            user_id=current_user.id, role_title=request.job_title,
            role_shorthand=request.job_shorthand,
            generated_description=jd.job_description,
            required_skills=safe_json_dumps(jd.required_skills),
            nice_to_have_skills=safe_json_dumps(jd.nice_to_have_skills)
        )
        db.add(job)
        db.commit()

        return success_response(data={
            "job_description": jd.job_description,
            "required_skills": jd.required_skills,
            "nice_to_have_skills": jd.nice_to_have_skills
        })
    except Exception as e:
        logger.error(f"JD generation error: {str(e)}")
        return error_response(500, "Generation failed", str(e))


# ==================== DASHBOARD ====================
@app.get("/api/dashboard/stats")
async def get_dashboard_stats(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        stats = ResumeService.get_resume_statistics(db, current_user.id)
        recent_searches = db.query(SearchHistory).filter(
            SearchHistory.user_id == current_user.id
        ).order_by(SearchHistory.created_at.desc()).limit(5).all()

        return success_response(data={
            "total_resumes": stats["total_resumes"],
            "avg_experience": stats["avg_experience"],
            "top_skills": stats["top_skills"],
            "experience_distribution": stats["experience_distribution"],
            "recent_searches": [
                {"query": s.query, "results_count": s.results_count, "created_at": s.created_at.isoformat()}
                for s in recent_searches
            ]
        })
    except Exception as e:
        logger.error(f"Dashboard stats error: {str(e)}")
        return error_response(500, "Error fetching stats")


# ==================== ERROR HANDLERS ====================
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    return JSONResponse(status_code=exc.status_code, content=error_response(exc.status_code, exc.detail))

@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    logger.error(f"Unhandled exception: {str(exc)}")
    return JSONResponse(status_code=500, content=error_response(500, "Internal server error", str(exc)))


@app.get("/")
async def root():
    return {"app": "AI Semantic Hiring Assistant", "version": "1.0.0", "docs": "/docs", "status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    logger.info(f"Starting AI HR SaaS backend on port {port}")
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
