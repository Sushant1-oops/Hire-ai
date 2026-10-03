import time

from core.database import SessionLocal
from core.observability import traceable
from core.utils import logger
from models import Application, Resume
from services.job_service import JobService
from services.resume_service import ResumeService
from services.search_service import index_resume
from services.storage_service import local_copy


@traceable(name="process_resume_job", run_type="chain")
def process_resume_job(resume_id: int) -> None:
    """Worker entry point: fetch the stored PDF, extract, embed, index, and score
    any applications that point at this resume. Idempotent (re-running replaces
    the chunks) and never raises for a bad resume: the failure is recorded on the
    row so the HR UI can show it instead of a spinner that never ends."""
    db = SessionLocal()
    started = time.perf_counter()
    try:
        resume = db.query(Resume).filter(Resume.id == resume_id).first()
        if not resume:
            logger.warning("process_resume_job: resume missing", extra={"event": "resume_missing", "resume_id": resume_id})
            return
        try:
            with local_copy(resume.storage_backend or "local", resume.file_path) as path:
                processed = ResumeService.parse_pdf(path)
            if not processed:
                raise ValueError("No text could be extracted. If this is a scanned PDF, OCR is not available on this server.")

            # Public applicants typed their own contact details into the form; those win over what we parse.
            from_public_form = db.query(Application.id).filter(Application.resume_id == resume.id).first() is not None
            ResumeService.apply_parsed(resume, processed, overwrite_contact=not from_public_form)
            index_resume(db, resume)
            resume.is_processed = True
            db.commit()

            try:
                JobService.rescore_resume_applications(db, resume)
            except Exception as e:
                # The resume itself is fine. Applications left without a score are
                # scored on the next read of the job's applicant list.
                db.rollback()
                logger.warning(f"scoring after processing failed for resume {resume_id}: {e}")
            logger.info(
                "resume processed",
                extra={"event": "resume_processed", "resume_id": resume_id, "duration_ms": round((time.perf_counter() - started) * 1000)},
            )
        except Exception as e:
            db.rollback()
            logger.error(f"resume processing failed: {e}", extra={"event": "resume_failed", "resume_id": resume_id})
            try:
                resume = db.query(Resume).filter(Resume.id == resume_id).first()
                if resume:
                    resume.is_processed = False
                    resume.processing_error = str(e)[:500]
                    db.commit()
            except Exception:
                db.rollback()
    finally:
        db.close()
