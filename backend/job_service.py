
import secrets
import numpy as np
from typing import List, Dict, Optional
from sqlalchemy import func
from sqlalchemy.orm import Session
from models import Job, Application, Resume
from utils import logger, safe_json_dumps, safe_json_loads, SimpleCache
from scoring_service import ScoringService
from observability import traceable








_ranking_cache = SimpleCache(ttl_seconds=30)


def _ranking_cache_key(job_id: int) -> str:
    return f"job_applications_ranked_{job_id}"


class JobService:
    SLUG_ALPHABET = "abcdefghijkmnpqrstuvwxyz23456789"  

    @classmethod
    def _generate_slug(cls) -> str:
        return "".join(secrets.choice(cls.SLUG_ALPHABET) for _ in range(8))

    @classmethod
    def create_job(
        cls,
        db: Session,
        user_id: int,
        title: str,
        description: str,
        location: Optional[str] = None,
        experience_min: Optional[float] = None,
        required_skills: Optional[List[str]] = None,
    ) -> Job:
        slug = cls._generate_slug()
        while db.query(Job).filter(Job.public_slug == slug).first():
            slug = cls._generate_slug()
        job = Job(
            user_id=user_id,
            public_slug=slug,
            title=title,
            description=description,
            location=location,
            experience_min=experience_min,
            required_skills=safe_json_dumps(required_skills or []),
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        return job

    @staticmethod
    def get_user_jobs(db: Session, user_id: int) -> List[Job]:
        return db.query(Job).filter(Job.user_id == user_id).order_by(Job.created_at.desc()).all()

    @staticmethod
    def get_application_counts(db: Session, job_ids: List[int]) -> Dict[int, int]:
        
        if not job_ids:
            return {}
        rows = (
            db.query(Application.job_id, func.count(Application.id))
            .filter(Application.job_id.in_(job_ids))
            .group_by(Application.job_id)
            .all()
        )
        return {job_id: count for job_id, count in rows}

    @staticmethod
    def get_job_by_id(db: Session, job_id: int, user_id: int) -> Optional[Job]:
        return db.query(Job).filter(Job.id == job_id, Job.user_id == user_id).first()

    @staticmethod
    def get_public_job(db: Session, slug: str) -> Optional[Job]:
        return db.query(Job).filter(Job.public_slug == slug, Job.status == "open").first()

    @staticmethod
    def set_job_status(db: Session, job_id: int, user_id: int, status: str) -> Optional[Job]:
        job = JobService.get_job_by_id(db, job_id, user_id)
        if not job:
            return None
        job.status = status
        db.commit()
        db.refresh(job)
        return job

    @staticmethod
    def find_existing_resume_by_email(db: Session, user_id: int, email: Optional[str]) -> Optional[Resume]:
        
        
        
        if not email:
            return None
        return (
            db.query(Resume)
            .filter(Resume.user_id == user_id, Resume.candidate_email.ilike(email.strip()))
            .first()
        )

    @staticmethod
    def invalidate_ranking_cache(job_id: int) -> None:
        _ranking_cache.delete(_ranking_cache_key(job_id))

    @staticmethod
    def create_or_update_application(db: Session, job: Job, resume: Resume, source: str = "form") -> Application:
        existing = (
            db.query(Application)
            .filter(Application.job_id == job.id, Application.resume_id == resume.id)
            .first()
        )
        if existing:
            
            
            existing.source = source
            db.commit()
            db.refresh(existing)
            application = existing
        else:
            application = Application(job_id=job.id, resume_id=resume.id, source=source, status="received")
            db.add(application)
            db.commit()
            db.refresh(application)
        JobService.invalidate_ranking_cache(job.id)
        return application

    @staticmethod
    @traceable(name="rank_applications", run_type="chain")
    def rank_applications(db: Session, job: Job, search_service, use_cache: bool = True) -> List[Dict]:
        
        cache_key = _ranking_cache_key(job.id)
        if use_cache:
            cached = _ranking_cache.get(cache_key)
            if cached is not None:
                return cached

        applications = db.query(Application).filter(Application.job_id == job.id).all()
        if not applications:
            _ranking_cache.set(cache_key, [])
            return []

        job_embedding = search_service.encode_text(
            search_service.build_job_embedding_text(job.description, safe_json_loads(job.required_skills, []))
        )
        required_skills = safe_json_loads(job.required_skills, [])

        results = []
        ready_apps = []  
        for app in applications:
            resume = app.resume
            if not resume:
                continue

            
            
            
            
            
            if resume.processing_error:
                processing_status = "failed"
            elif not resume.is_processed:
                processing_status = "pending"
            else:
                processing_status = "ready"

            if processing_status != "ready":
                results.append({
                    "application_id": app.id,
                    "resume_id": resume.id,
                    "candidate_name": resume.candidate_name,
                    "candidate_email": resume.candidate_email,
                    "candidate_phone": resume.candidate_phone,
                    "experience_years": resume.experience_years,
                    "status": app.status,
                    "source": app.source,
                    "applied_at": app.applied_at.isoformat() if app.applied_at else None,
                    "processing_status": processing_status,
                    "processing_error": resume.processing_error,
                    "final_score": 0.0, "semantic_similarity": 0.0, "experience_match": 0.0,
                    "skill_overlap": 0.0, "matched_skills": [], "missing_skills": [],
                    "recommendation": "Processing" if processing_status == "pending" else "Failed to process",
                })
                continue

            ready_apps.append((app, resume, safe_json_loads(resume.skills, [])))

        
        
        
        
        
        
        
        texts = [
            search_service.build_resume_embedding_text(skills, resume.experience_years, resume.extracted_text)
            for _app, resume, skills in ready_apps
        ]
        batch_embeddings = search_service.encode_texts_batch(texts) if texts else None

        for i, (app, resume, candidate_skills) in enumerate(ready_apps):
            similarity = 0.0
            if texts[i].strip():
                similarity = float(np.dot(job_embedding, batch_embeddings[i].reshape(1, -1).T)[0][0])

            scores = ScoringService.score_candidate(
                semantic_similarity=max(0.0, similarity),
                candidate_skills=candidate_skills,
                required_skills=required_skills,
                candidate_experience=resume.experience_years,
                required_min_experience=job.experience_min,
            )
            app.match_score = scores["final_score"]

            results.append({
                "application_id": app.id,
                "resume_id": resume.id,
                "candidate_name": resume.candidate_name,
                "candidate_email": resume.candidate_email,
                "candidate_phone": resume.candidate_phone,
                "experience_years": resume.experience_years,
                "status": app.status,
                "source": app.source,
                "applied_at": app.applied_at.isoformat() if app.applied_at else None,
                "processing_status": "ready",
                "processing_error": None,
                "recommendation": ScoringService.get_recommendation(scores["final_score"]),
                **scores,
            })

        db.commit()
        results.sort(key=lambda r: r["final_score"], reverse=True)
        for i, r in enumerate(results, start=1):
            r["rank"] = i

        _ranking_cache.set(cache_key, results)
        return results

    @staticmethod
    def update_application_status(db: Session, application_id: int, user_id: int, status: str) -> Optional[Application]:
        application = (
            db.query(Application)
            .join(Job, Application.job_id == Job.id)
            .filter(Application.id == application_id, Job.user_id == user_id)
            .first()
        )
        if not application:
            return None
        application.status = status
        db.commit()
        db.refresh(application)
        JobService.invalidate_ranking_cache(application.job_id)
        return application

