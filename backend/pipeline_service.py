

import os
import numpy as np
from typing import Optional, Tuple

from utils import logger, safe_json_dumps, safe_json_loads
from scoring_service import ScoringService
from observability import traceable


def pipeline_thread_id(job_public_slug: str, email: str) -> str:
    return f"job:{job_public_slug}:{email.strip().lower()}"


@traceable(name="application_intake", run_type="chain")
def submit_application(
    *, db, job, resume_service, uploaded_file_path: str, resume_filename: str,
    full_name: str, email: str, phone: Optional[str],
) -> Tuple["Resume", "Application", bool]:  
    
    from job_service import JobService

    ok, storage_path = resume_service.save_resume_file(uploaded_file_path, resume_filename)
    if not ok:
        raise ValueError("Failed to save resume file")

    existing = JobService.find_existing_resume_by_email(db, job.user_id, email)
    if existing:
        
        
        
        
        existing.candidate_name = full_name
        if phone:
            existing.candidate_phone = phone
        existing.file_name = resume_filename
        existing.file_path = storage_path
        existing.is_processed = False
        existing.processing_error = None
        db.commit()
        db.refresh(existing)
        resume, is_new_resume = existing, False
    else:
        resume = resume_service.create_pending_resume_record(
            db, job.user_id, resume_filename, storage_path, full_name, email, phone
        )
        if not resume:
            raise ValueError("Failed to create candidate record")
        is_new_resume = True

    application = JobService.create_or_update_application(db, job, resume, source="form")
    return resume, application, is_new_resume


@traceable(name="application_pipeline_async", run_type="chain")
def process_application_async(*, application_id: int, resume_id: int, job_id: int, temp_file_path: str) -> None:
    
    from database import SessionLocal
    from models import Resume, Application, Job
    from resume_service import ResumeService
    from search_service import get_search_service
    from job_service import JobService

    db = SessionLocal()
    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        resume = db.query(Resume).filter(Resume.id == resume_id).first()
        application = db.query(Application).filter(Application.id == application_id).first()
        if not job or not resume or not application:
            logger.error(f"Background application processing aborted: missing row "
                         f"(job={job_id}, resume={resume_id}, application={application_id})")
            return

        try:
            resume_service = ResumeService()
            processed = resume_service.process_resume(temp_file_path)
            if not processed:
                raise ValueError("Could not extract text from this resume — likely a scanned/image-only PDF")
            extracted_text = processed.get("extracted_text", "")
            metadata = processed.get("metadata", {})

            resume.extracted_text = extracted_text
            resume.experience_years = metadata.get("experience_years")
            resume.skills = safe_json_dumps(metadata.get("skills", []))
            resume.education = safe_json_dumps(metadata.get("education", []))
            resume.is_processed = True
            resume.processing_error = None
            db.commit()

            search_service = get_search_service()
            embedding_text = search_service.build_resume_embedding_text(
                metadata.get("skills", []), metadata.get("experience_years"), extracted_text
            )
            search_service.remove_resume(resume.id)  
            search_service.add_resume_to_index(resume.id, embedding_text)
            search_service.save_index()

            similarity = 0.0
            if extracted_text.strip():
                job_embedding = search_service.encode_text(
                    search_service.build_job_embedding_text(job.description, safe_json_loads(job.required_skills, []))
                )
                resume_embedding = search_service.encode_text(embedding_text)
                similarity = float(np.dot(job_embedding, resume_embedding.T)[0][0])
            scores = ScoringService.score_candidate(
                semantic_similarity=max(0.0, similarity),
                candidate_skills=metadata.get("skills", []),
                required_skills=safe_json_loads(job.required_skills, []),
                candidate_experience=metadata.get("experience_years"),
                required_min_experience=job.experience_min,
            )
            application.match_score = scores["final_score"]
            db.commit()

            JobService.invalidate_ranking_cache(job.id)

        except Exception as e:
            logger.error(f"Background application processing failed (application_id={application_id}): {e}")
            try:
                resume.is_processed = False
                resume.processing_error = str(e)
                db.commit()
                JobService.invalidate_ranking_cache(job.id)
            except Exception:
                db.rollback()
    finally:
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)
        db.close()
