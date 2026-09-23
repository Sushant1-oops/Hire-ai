from typing import Optional, Tuple

from sqlalchemy.orm import Session

from .job_service import JobService
from models import Application, Job, Resume
from core.observability import traceable
from .queue_service import enqueue_resume_processing
from .resume_service import ResumeService
from core.security import ValidatedUpload
from .storage_service import StoredFile, get_storage
from core.utils import logger


@traceable(name="application_intake", run_type="chain")
def submit_application(
    db: Session,
    job: Job,
    upload: ValidatedUpload,
    stored: StoredFile,
    full_name: str,
    email: str,
    phone: Optional[str],
) -> Tuple[Resume, Application, str]:
    """Fast synchronous half of a public application: dedup by email inside the
    HR user's own pool, record the candidate and application, and hand the slow
    part (parse, embed, score) to the worker. Returns (resume, application, mode)
    where mode is 'queued' or 'reused' (identical file already processed)."""
    existing = JobService.find_existing_resume_by_email(db, job.user_id, email)
    old_file: Optional[Tuple[str, str]] = None
    mode = "queued"

    if existing and existing.content_hash == upload.sha256 and existing.is_processed:
        # Same person, same PDF, already parsed: keep what we have, drop the duplicate upload.
        get_storage(stored.backend).delete(stored.key)
        existing.candidate_name = full_name
        if phone:
            existing.candidate_phone = phone
        db.commit()
        resume, mode = existing, "reused"
    elif existing:
        old_file = (existing.storage_backend or "local", existing.file_path)
        existing.candidate_name = full_name
        if phone:
            existing.candidate_phone = phone
        existing.file_name = upload.filename
        existing.file_path = stored.key
        existing.storage_backend = stored.backend
        existing.size_bytes = stored.size
        existing.content_hash = upload.sha256
        existing.is_processed = False
        existing.processing_error = None
        db.commit()
        db.refresh(existing)
        resume = existing
    else:
        resume = ResumeService.create_pending(
            db, job.user_id, upload.filename, stored, upload.sha256,
            candidate_name=full_name, candidate_email=email, candidate_phone=phone,
        )

    application = JobService.create_or_update_application(db, job, resume, source="form")

    if old_file:
        try:
            get_storage(old_file[0]).delete(old_file[1])
        except Exception as e:
            logger.warning(f"could not remove replaced resume file: {e}")

    if mode == "reused":
        try:
            from tasks import _score_applications
            _score_applications(db, resume)
        except Exception as e:
            logger.warning(f"inline scoring failed, queueing full processing instead: {e}")
            mode = "queued"
    if mode == "queued":
        enqueue_resume_processing(resume.id)
    return resume, application, mode
