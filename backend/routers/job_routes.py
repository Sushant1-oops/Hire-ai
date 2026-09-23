from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

import core.audit as audit
from core.database import get_db
from auth.deps import get_current_user
from ai.extraction import normalize_phone
from services.job_service import JobService
from models import User
from services.pipeline_service import submit_application
from core.rate_limit import ip_limit
from core.security import UploadRejected, read_pdf_upload
from services.storage_service import StorageError, get_storage
from core.utils import fail, logger, safe_json_loads, success_response, validate_email

router = APIRouter(tags=["jobs"])

APPLICATION_STATUSES = {"received", "screened", "shortlisted", "rejected", "interview", "hired"}


class JobCreateRequest(BaseModel):
    title: str = Field(min_length=2, max_length=255)
    description: str = Field(min_length=10, max_length=20000)
    location: Optional[str] = Field(default=None, max_length=255)
    experience_min: Optional[float] = Field(default=None, ge=0, le=50)
    required_skills: Optional[List[str]] = None


class StatusUpdate(BaseModel):
    status: str


@router.post("/api/jobs")
def create_job(payload: JobCreateRequest, request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    job = JobService.create_job(
        db, current_user.id, title=payload.title, description=payload.description, location=payload.location,
        experience_min=payload.experience_min, required_skills=(payload.required_skills or [])[:40],
    )
    audit.record(db, "job_created", user_id=current_user.id, resource_type="job", resource_id=job.id, request=request)
    return success_response(data=job.to_dict(), message="Job created")


@router.get("/api/jobs")
def list_jobs(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    jobs = JobService.get_user_jobs(db, current_user.id)
    counts = JobService.get_application_counts(db, [job.id for job in jobs])
    return success_response(data=[{**job.to_dict(), "application_count": counts.get(job.id, 0)} for job in jobs])


@router.get("/api/jobs/{job_id}")
def get_job(job_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    job = JobService.get_job_by_id(db, job_id, current_user.id)
    if not job:
        return fail(404, "Job not found")
    count = JobService.get_application_counts(db, [job.id]).get(job.id, 0)
    return success_response(data={**job.to_dict(), "application_count": count})


@router.patch("/api/jobs/{job_id}/status")
def update_job_status(job_id: int, payload: StatusUpdate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if payload.status not in ("open", "closed"):
        return fail(400, "status must be 'open' or 'closed'")
    job = JobService.set_job_status(db, job_id, current_user.id, payload.status)
    if not job:
        return fail(404, "Job not found")
    return success_response(data=job.to_dict())


@router.get("/api/jobs/{job_id}/applications")
def get_job_applications(job_id: int, request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    job = JobService.get_job_by_id(db, job_id, current_user.id)
    if not job:
        return fail(404, "Job not found")
    ranked = JobService.rank_applications(db, job)
    return success_response(data={"job": job.to_dict(), "applications": ranked})


@router.patch("/api/applications/{application_id}/status")
def update_application_status(application_id: int, payload: StatusUpdate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if payload.status not in APPLICATION_STATUSES:
        return fail(400, f"status must be one of {sorted(APPLICATION_STATUSES)}")
    application = JobService.update_application_status(db, application_id, current_user.id, payload.status)
    if not application:
        return fail(404, "Application not found")
    return success_response(data=application.to_dict())


# ---- Public endpoints: no auth. A candidate knows only the public_slug. ----

@router.get("/api/public/jobs/{slug}", dependencies=[Depends(ip_limit("public_job", 120, 60))])
def get_public_job(slug: str, db: Session = Depends(get_db)):
    job = JobService.get_public_job(db, slug)
    if not job:
        return fail(404, "This job posting is no longer available")
    return success_response(data={
        "title": job.title, "location": job.location, "experience_min": job.experience_min,
        "description": job.description, "required_skills": safe_json_loads(job.required_skills, []),
    })


def _submit(db: Session, slug: str, upload, full_name: str, email: str, phone: Optional[str], request: Request):
    job = JobService.get_public_job(db, slug)
    if not job:
        return fail(404, "This job posting is no longer available")
    try:
        stored = get_storage().save_bytes(upload.data, job.user_id)
    except StorageError as e:
        logger.error(f"application file storage failed: {e}")
        return fail(502, "We couldn't store your resume. Please try again in a minute.")
    try:
        resume, application, _mode = submit_application(db, job, upload, stored, full_name, email, phone)
    except Exception as e:
        db.rollback()
        logger.error(f"application intake failed: {e}")
        try:
            get_storage(stored.backend).delete(stored.key)
        except Exception:
            pass
        return fail(500, "Failed to submit application")
    audit.record(db, "application_submitted", user_id=None, resource_type="application", resource_id=application.id,
                 request=request, job_id=job.id)
    return success_response(
        data={"application_id": application.id, "job_title": job.title},
        message="Application received. We're processing your resume now.",
    )


@router.post("/api/public/jobs/{slug}/apply", dependencies=[Depends(ip_limit("apply", 5, 600))])
async def apply_to_job(
    slug: str,
    request: Request,
    full_name: str = Form(..., max_length=200),
    email: str = Form(..., max_length=254),
    phone: Optional[str] = Form(None, max_length=40),
    resume: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    full_name, email = full_name.strip(), email.strip()
    if not full_name or not email:
        return fail(400, "Full name and email are required")
    if not validate_email(email):
        return fail(400, "Please enter a valid email address")
    clean_phone = normalize_phone(phone) if phone and phone.strip() else None
    if phone and phone.strip() and not clean_phone:
        return fail(400, "Please enter a valid phone number or leave it blank")
    try:
        upload = await read_pdf_upload(resume)
    except UploadRejected as e:
        return fail(400, str(e))
    return await run_in_threadpool(_submit, db, slug, upload, full_name, email, clean_phone, request)
