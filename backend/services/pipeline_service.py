from typing import Optional, Tuple

from sqlalchemy.orm import Session

from core.observability import traceable
from core.security import ValidatedUpload
from core.utils import logger
from models import Application, Job, Resume
from .job_service import JobService
from .queue_service import enqueue_resume_processing
from .resume_service import ResumeService
from .storage_service import StoredFile, get_storage


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
    """Fast synchronous half of a public application: record the candidate and the
    application, then hand the slow part (parse, embed, score) to the worker.
    Returns (resume, application, mode); mode is 'queued' or 'reused' (the identical
    file was already processed, so it is scored immediately).

    An anonymous form must never alter an existing candidate's record, because
    anyone can type anyone's email address. So:
      * the same PDF from the same email reuses the existing record (nothing changes);
      * a different PDF always becomes a NEW resume. If this job already has an
        application from that email, it is re-pointed at the new resume (the
        candidate resubmitted), and the old resume stays untouched in the library."""
    existing = JobService.find_existing_resume_by_email(db, job.user_id, email)
    mode = "queued"

    if existing is not None and existing.content_hash == upload.sha256:
        get_storage(stored.backend).delete(stored.key)  # drop the duplicate upload
        resume = existing
        if existing.is_processed:
            mode = "reused"
    else:
        resume = ResumeService.create_pending(
            db, job.user_id, upload.filename, stored, upload.sha256,
            candidate_name=full_name, candidate_email=email, candidate_phone=phone,
        )

    application = JobService.create_or_update_application(db, job, resume, source="form", replace_email=email)

    if mode == "reused":
        try:
            JobService.rescore_resume_applications(db, resume)
        except Exception as e:
            db.rollback()
            logger.warning(f"inline scoring failed, queueing full processing instead: {e}")
            mode = "queued"
    if mode == "queued":
        enqueue_resume_processing(resume.id)
    return resume, application, mode
