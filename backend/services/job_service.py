# job_service.py
import secrets
from typing import List, Dict, Optional
from sqlalchemy import func
from sqlalchemy.orm import Session
from .cache_service import Cache
from models import Job, Application, Resume
from core.utils import logger, safe_json_dumps, safe_json_loads
from .scoring_service import ScoringService
from .search_service import semantic_for_job
from core.observability import traceable

# Ranking a job's applicants re-encodes every applicant's resume text against
# the job description on every call — real CPU cost that grows with the
# applicant pool. A short TTL absorbs repeated dashboard views/polling
# without going stale for long; any real mutation (new application, a status
# change, background scoring finishing) invalidates it immediately instead
# of waiting out the TTL, so HR never sees a change they just made "not
# take effect".
_ranking_cache = Cache("job_ranking", 30)


def _ranking_cache_key(job_id: int) -> str:
    return f"job_applications_ranked_{job_id}"


class JobService:
    SLUG_ALPHABET = "abcdefghijkmnpqrstuvwxyz23456789"  # no ambiguous chars

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
        """One aggregate query for every job's application count, instead of
        loading each job's full `applications` relationship one at a time
        (an N+1 query that used to run on every /api/jobs list load)."""
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
        # Dedup key: same HR user + same candidate email. A candidate who has
        # already applied to one of this company's jobs gets their existing
        # resume record reused instead of a duplicate.
        if not email:
            return None
        return (
            db.query(Resume)
            .filter(Resume.user_id == user_id, func.lower(Resume.candidate_email) == email.strip().lower())
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
            # Same candidate applying again to the same job — treat as a fresh
            # submission (refreshes applied_at) without creating a duplicate row.
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
    def rank_applications(db: Session, job: Job, use_cache: bool = True) -> List[Dict]:
        """Scores every applicant against this job. Resume vectors are already
        stored (computed once by the worker), so ranking only embeds the job text
        and compares, instead of re-encoding every applicant on every view.
        Cached briefly per job (Redis when configured); any real change clears it."""
        cache_key = _ranking_cache_key(job.id)
        if use_cache:
            cached = _ranking_cache.get(cache_key)
            if cached is not None:
                return cached

        applications = db.query(Application).filter(Application.job_id == job.id).all()
        if not applications:
            _ranking_cache.set(cache_key, [])
            return []

        required_skills = safe_json_loads(job.required_skills, [])
        results = []
        ready = []
        for app in applications:
            resume = app.resume
            if not resume:
                continue
            processing_status = resume.processing_status
            base = {
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
            }
            if processing_status != "ready":
                results.append({
                    **base,
                    "processing_error": resume.processing_error,
                    "final_score": 0.0, "semantic_similarity": 0.0, "experience_match": 0.0,
                    "skill_overlap": 0.0, "matched_skills": [], "missing_skills": [],
                    "recommendation": "Processing" if processing_status == "pending" else "Failed to process",
                })
            else:
                ready.append((app, resume, base))

        semantic = semantic_for_job(db, job, [resume.id for _a, resume, _b in ready]) if ready else {}
        for app, resume, base in ready:
            sem = semantic.get(resume.id, {"semantic": 0.0})
            scores = ScoringService.score_candidate(
                semantic_similarity=sem["semantic"],
                candidate_skills=safe_json_loads(resume.skills, []),
                required_skills=required_skills,
                candidate_experience=resume.experience_years,
                required_min_experience=job.experience_min,
            )
            app.match_score = scores["final_score"]
            results.append({
                **base,
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

