import time

from core.database import SessionLocal
from models import Application, Resume
from core.observability import traceable
from services.resume_service import ResumeService
from services.search_service import index_resume, semantic_for_job
from services.scoring_service import ScoringService
from services.storage_service import local_copy
from core.utils import logger, safe_json_loads


def _score_applications(db, resume: Resume) -> None:
    from services.job_service import JobService

    skills = safe_json_loads(resume.skills, [])
    for application in db.query(Application).filter(Application.resume_id == resume.id).all():
        job = application.job
        if not job:
            continue
        sem = semantic_for_job(db, job, [resume.id]).get(resume.id, {"semantic": 0.0})
        scores = ScoringService.score_candidate(
            semantic_similarity=sem["semantic"],
            candidate_skills=skills,
            required_skills=safe_json_loads(job.required_skills, []),
            candidate_experience=resume.experience_years,
            required_min_experience=job.experience_min,
        )
        application.match_score = scores["final_score"]
        JobService.invalidate_ranking_cache(job.id)
    db.commit()


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

            from_public_form = db.query(Application).filter(Application.resume_id == resume.id).count() > 0
            ResumeService.apply_parsed(resume, processed, overwrite_contact=not from_public_form)
            index_resume(db, resume)
            resume.is_processed = True
            db.commit()

            _score_applications(db, resume)
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
                    from services.job_service import JobService
                    for application in db.query(Application).filter(Application.resume_id == resume_id).all():
                        JobService.invalidate_ranking_cache(application.job_id)
            except Exception:
                db.rollback()
    finally:
        db.close()
