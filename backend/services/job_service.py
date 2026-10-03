"""Jobs, their applicants, and the ranking of those applicants.

Scores are computed once and stored on the application row (score_details), not
recomputed on every view. They are (re)computed when
  * a resume finishes processing (workers/tasks.py),
  * a job's requirements change (update_job clears them), or
  * a read finds a ready applicant without one (rank_applications fills the gap).
So opening a job's applicant list is a plain database read in the normal case.
"""
import secrets
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from sqlalchemy import case, func
from sqlalchemy.orm import Session

from ai.skills_extractor import SkillsExtractor
from core.observability import traceable
from core.utils import safe_json_dumps, safe_json_loads
from models import Application, Job, Resume, resume_status
from .scoring_service import ScoringService
from .search_service import semantic_for_job

MAX_REQUIRED_SKILLS = 40
_extractor = SkillsExtractor()

# Fields update_job is allowed to change.
_EDITABLE = {"title", "description", "location", "experience_min", "required_skills"}
# Changing any of these changes every applicant's score.
_SCORE_AFFECTING = {"description", "experience_min", "required_skills"}


def clean_required_skills(skills: Optional[List[str]], description: Optional[str] = None) -> List[str]:
    """Canonical, de-duplicated required skills. When none were given, they are
    read from the job description so a job is never left unable to score on skills."""
    cleaned = _extractor.normalize_list(skills or [], MAX_REQUIRED_SKILLS)
    if not cleaned and description:
        cleaned = _extractor.extract(description)[:MAX_REQUIRED_SKILLS]
    return cleaned


def score_payload(job: Job, resume: Resume, semantic: Dict) -> Dict:
    """The stored/served score breakdown for one resume against one job."""
    scores = ScoringService.score_candidate(
        semantic_similarity=semantic.get("semantic", 0.0),
        candidate_skills=safe_json_loads(resume.skills, []),
        required_skills=safe_json_loads(job.required_skills, []),
        candidate_experience=resume.experience_years,
        required_min_experience=job.experience_min,
        candidate_text=resume.extracted_text or "",
    )
    scores["recommendation"] = ScoringService.get_recommendation(scores["final_score"])
    return scores


class JobService:
    SLUG_ALPHABET = "abcdefghijkmnpqrstuvwxyz23456789"  # no ambiguous chars

    # ------------------------------------------------------------------ jobs

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
        while db.query(Job.id).filter(Job.public_slug == slug).first():
            slug = cls._generate_slug()
        job = Job(
            user_id=user_id,
            public_slug=slug,
            title=title.strip(),
            description=description.strip(),
            location=(location or "").strip() or None,
            experience_min=experience_min,
            required_skills=safe_json_dumps(clean_required_skills(required_skills, description)),
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        return job

    @staticmethod
    def get_user_jobs(db: Session, user_id: int) -> List[Job]:
        return db.query(Job).filter(Job.user_id == user_id).order_by(Job.created_at.desc()).all()

    @staticmethod
    def get_job_by_id(db: Session, job_id: int, user_id: int) -> Optional[Job]:
        return db.query(Job).filter(Job.id == job_id, Job.user_id == user_id).first()

    @staticmethod
    def get_public_job(db: Session, slug: str) -> Optional[Job]:
        return db.query(Job).filter(Job.public_slug == slug, Job.status == "open").first()

    @staticmethod
    def get_job_stats(db: Session, job_ids: List[int]) -> Dict[int, Dict]:
        """Applicant counts and the best score for many jobs in one grouped query."""
        if not job_ids:
            return {}
        rows = (
            db.query(
                Application.job_id,
                func.count(Application.id),
                func.sum(case((Application.status == "received", 1), else_=0)),
                func.sum(case((Application.status.in_(("shortlisted", "interview")), 1), else_=0)),
                func.max(Application.match_score),
            )
            .filter(Application.job_id.in_(job_ids))
            .group_by(Application.job_id)
            .all()
        )
        return {
            job_id: {
                "application_count": int(total or 0),
                "new_count": int(new or 0),
                "in_pipeline": int(pipeline or 0),
                "top_score": round(top, 3) if top is not None else None,
            }
            for job_id, total, new, pipeline, top in rows
        }

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
    def update_job(db: Session, job_id: int, user_id: int, changes: Dict) -> Optional[Job]:
        """Applies the fields present in `changes`. Anything that affects scoring
        clears every applicant's stored score so it is recomputed against the new requirements."""
        job = JobService.get_job_by_id(db, job_id, user_id)
        if not job:
            return None
        changes = {k: v for k, v in changes.items() if k in _EDITABLE}
        if "title" in changes:
            job.title = (changes["title"] or "").strip() or job.title
        if "description" in changes and changes["description"]:
            job.description = changes["description"].strip()
        if "location" in changes:
            job.location = (changes["location"] or "").strip() or None
        if "experience_min" in changes:
            job.experience_min = changes["experience_min"]
        if "required_skills" in changes:
            job.required_skills = safe_json_dumps(clean_required_skills(changes["required_skills"], job.description))
        if _SCORE_AFFECTING & changes.keys():
            JobService.invalidate_scores(db, job.id)
        db.commit()
        db.refresh(job)
        return job

    @staticmethod
    def delete_job(db: Session, job_id: int, user_id: int) -> bool:
        """Removes the job and its applications. The candidates' resumes stay in the library."""
        job = JobService.get_job_by_id(db, job_id, user_id)
        if not job:
            return False
        db.delete(job)  # cascades to applications
        db.commit()
        return True

    @staticmethod
    def invalidate_scores(db: Session, job_id: int) -> None:
        """Marks every applicant of a job as needing a fresh score. Caller commits."""
        db.query(Application).filter(Application.job_id == job_id).update(
            {Application.score_details: None, Application.scored_at: None, Application.match_score: None},
            synchronize_session=False,
        )

    @staticmethod
    def invalidate_resume_scores(db: Session, resume_ids: List[int]) -> None:
        """Same, for every application that points at one of these resumes. Caller commits."""
        if resume_ids:
            db.query(Application).filter(Application.resume_id.in_(resume_ids)).update(
                {Application.score_details: None, Application.scored_at: None, Application.match_score: None},
                synchronize_session=False,
            )

    @staticmethod
    def invalidate_user_scores(db: Session, user_id: int) -> None:
        """Clears stored scores for all of a tenant's applications (their vectors changed). Caller commits."""
        job_ids = db.query(Job.id).filter(Job.user_id == user_id).subquery()
        db.query(Application).filter(Application.job_id.in_(job_ids)).update(
            {Application.score_details: None, Application.scored_at: None, Application.match_score: None},
            synchronize_session=False,
        )

    # ---------------------------------------------------------- applications

    @staticmethod
    def find_existing_resume_by_email(db: Session, user_id: int, email: Optional[str]) -> Optional[Resume]:
        if not email:
            return None
        return (
            db.query(Resume)
            .filter(Resume.user_id == user_id, func.lower(Resume.candidate_email) == email.strip().lower())
            .order_by(Resume.created_at.desc())
            .first()
        )

    @staticmethod
    def create_or_update_application(
        db: Session, job: Job, resume: Resume, source: str = "form", replace_email: Optional[str] = None
    ) -> Application:
        """One application per (job, resume). If `replace_email` is given and this
        job already has an application from a different resume with that email, that
        application is re-pointed at this (newer) resume instead of creating a second
        row for the same person. Their pipeline status is reset: it is a new submission."""
        application = (
            db.query(Application).filter(Application.job_id == job.id, Application.resume_id == resume.id).first()
        )
        if application is None and replace_email:
            application = (
                db.query(Application)
                .join(Resume, Resume.id == Application.resume_id)
                .filter(Application.job_id == job.id, func.lower(Resume.candidate_email) == replace_email.strip().lower())
                .first()
            )
            if application is not None:
                application.resume_id = resume.id
                application.status = "received"
        if application is None:
            application = Application(job_id=job.id, resume_id=resume.id, source=source, status="received")
            db.add(application)
        else:
            application.source = source
            application.applied_at = datetime.utcnow()
        application.score_details = None
        application.scored_at = None
        application.match_score = None
        db.commit()
        db.refresh(application)
        return application

    @staticmethod
    def add_manual_application(db: Session, job: Job, resume_id: int) -> Optional[Application]:
        """HR adds a candidate from their own library to a job. None if the resume isn't theirs."""
        resume = db.query(Resume).filter(Resume.id == resume_id, Resume.user_id == job.user_id).first()
        if not resume:
            return None
        existing = db.query(Application).filter(Application.job_id == job.id, Application.resume_id == resume.id).first()
        if existing:
            return existing
        application = Application(job_id=job.id, resume_id=resume.id, source="manual", status="received")
        db.add(application)
        db.commit()
        db.refresh(application)
        if resume.is_processed:
            JobService._score_pairs(db, job, [(application, resume)])
            db.commit()
        return application

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
        return application

    @staticmethod
    def delete_application(db: Session, application_id: int, user_id: int) -> bool:
        application = (
            db.query(Application)
            .join(Job, Application.job_id == Job.id)
            .filter(Application.id == application_id, Job.user_id == user_id)
            .first()
        )
        if not application:
            return False
        db.delete(application)
        db.commit()
        return True

    # --------------------------------------------------------------- scoring

    @staticmethod
    def _score_pairs(db: Session, job: Job, pairs: List[Tuple[Application, Resume]]) -> None:
        """Scores (application, resume) pairs against `job` and stores the result.
        Caller commits."""
        if not pairs:
            return
        semantic = semantic_for_job(db, job, [resume.id for _app, resume in pairs])
        now = datetime.utcnow()
        for application, resume in pairs:
            payload = score_payload(job, resume, semantic.get(resume.id, {"semantic": 0.0}))
            application.score_details = safe_json_dumps(payload)
            application.match_score = payload["final_score"]
            application.scored_at = now

    @staticmethod
    def rescore_resume_applications(db: Session, resume: Resume) -> None:
        """Called by the worker once a resume is processed: scores every application
        that points at it, against that application's own job."""
        applications = db.query(Application).filter(Application.resume_id == resume.id).all()
        for application in applications:
            if application.job is not None:
                JobService._score_pairs(db, application.job, [(application, resume)])
        db.commit()

    @staticmethod
    @traceable(name="rank_applications", run_type="chain")
    def rank_applications(db: Session, job: Job) -> List[Dict]:
        """A job's applicants, best first. Reads stored scores; only applicants that
        are ready but have no stored score yet are scored here (and stored)."""
        rows = (
            db.query(
                Application,
                Resume.candidate_name.label("candidate_name"),
                Resume.candidate_email.label("candidate_email"),
                Resume.candidate_phone.label("candidate_phone"),
                Resume.experience_years.label("experience_years"),
                Resume.is_processed.label("is_processed"),
                Resume.processing_error.label("processing_error"),
            )
            .join(Resume, Resume.id == Application.resume_id)  # skips the (large) extracted_text column
            .filter(Application.job_id == job.id)
            .all()
        )

        unscored = [
            r.Application.id for r in rows
            if resume_status(r.is_processed, r.processing_error) == "ready" and not r.Application.score_details
        ]
        if unscored:
            pairs = (
                db.query(Application, Resume)
                .join(Resume, Resume.id == Application.resume_id)
                .filter(Application.id.in_(unscored))
                .all()
            )
            JobService._score_pairs(db, job, [(a, r) for a, r in pairs])
            db.commit()

        results: List[Dict] = []
        for row in rows:
            application = row.Application
            status = resume_status(row.is_processed, row.processing_error)
            item = {
                "application_id": application.id,
                "resume_id": application.resume_id,
                "candidate_name": row.candidate_name,
                "candidate_email": row.candidate_email,
                "candidate_phone": row.candidate_phone,
                "experience_years": row.experience_years,
                "status": application.status,
                "source": application.source,
                "applied_at": application.applied_at.isoformat() if application.applied_at else None,
                "processing_status": status,
                "processing_error": row.processing_error,
            }
            details = safe_json_loads(application.score_details, None) if status == "ready" else None
            if details:
                item.update(details)
            else:
                item.update({
                    "final_score": 0.0, "semantic_similarity": 0.0, "experience_match": 0.0, "skill_overlap": 0.0,
                    "matched_skills": [], "missing_skills": [], "unverified_skills": [],
                    "recommendation": "Processing" if status == "pending" else "Failed to process",
                })
            results.append(item)

        results.sort(key=lambda r: (r["processing_status"] != "ready", -r["final_score"], r["applied_at"] or ""))
        rank = 0
        for item in results:
            if item["processing_status"] == "ready":
                rank += 1
                item["rank"] = rank
            else:
                item["rank"] = None
        return results
