"""What a recruiter needs on the first screen: where the pipeline stands, which
candidates are waiting for a decision, which jobs are moving, and what is wrong
with the resume library. Every number comes from an indexed aggregate query; no
rows are loaded and nothing is scored here.
"""
from typing import Dict, List

from sqlalchemy import case, func, or_
from sqlalchemy.orm import Session

from core.config import NAME_CONFIDENCE_THRESHOLD
from models import Application, Job, Resume
from .scoring_service import ScoringService

PIPELINE_ORDER = ["received", "screened", "shortlisted", "interview", "hired", "rejected"]
# Applications still waiting for a recruiter's decision.
AWAITING_DECISION = ("received", "screened")
# Only candidates at least this good are surfaced as "worth a look first".
TOP_CANDIDATE_MIN_SCORE = 0.55
JOBS_SHOWN = 6
CANDIDATES_SHOWN = 5
RECENT_SHOWN = 6


def get_dashboard(db: Session, user_id: int) -> Dict:
    # ---- pipeline funnel (all jobs)
    status_rows = (
        db.query(Application.status, func.count(Application.id))
        .join(Job, Job.id == Application.job_id)
        .filter(Job.user_id == user_id)
        .group_by(Application.status)
        .all()
    )
    counts = {status: int(n) for status, n in status_rows}
    pipeline = [{"status": s, "count": counts.get(s, 0)} for s in PIPELINE_ORDER]
    total_applications = sum(counts.values())

    # ---- jobs
    job_counts = dict(
        db.query(Job.status, func.count(Job.id)).filter(Job.user_id == user_id).group_by(Job.status).all()
    )
    job_rows = (
        db.query(
            Job.id, Job.title, Job.location, Job.created_at,
            func.count(Application.id),
            func.sum(case((Application.status == "received", 1), else_=0)),
            func.sum(case((Application.status.in_(("shortlisted", "interview")), 1), else_=0)),
            func.max(Application.match_score),
        )
        .outerjoin(Application, Application.job_id == Job.id)
        .filter(Job.user_id == user_id, Job.status == "open")
        .group_by(Job.id)
        .order_by(func.sum(case((Application.status == "received", 1), else_=0)).desc(), Job.created_at.desc())
        .limit(JOBS_SHOWN)
        .all()
    )
    jobs: List[Dict] = [
        {
            "id": jid, "title": title, "location": location,
            "applicants": int(total or 0), "new": int(new or 0), "in_pipeline": int(in_pipe or 0),
            "top_score": round(top, 3) if top is not None else None,
        }
        for jid, title, location, _created, total, new, in_pipe, top in job_rows
    ]

    # ---- candidates waiting on a decision, best first
    top_rows = (
        db.query(
            Application.id, Application.job_id, Application.resume_id, Application.status, Application.match_score,
            Job.title, Resume.candidate_name,
        )
        .join(Job, Job.id == Application.job_id)
        .join(Resume, Resume.id == Application.resume_id)
        .filter(
            Job.user_id == user_id,
            Job.status == "open",
            Application.status.in_(AWAITING_DECISION),
            Application.match_score >= TOP_CANDIDATE_MIN_SCORE,
        )
        .order_by(Application.match_score.desc())
        .limit(CANDIDATES_SHOWN)
        .all()
    )
    top_candidates = [
        {
            "application_id": aid, "job_id": job_id, "resume_id": resume_id, "status": status,
            "score": round(score, 3), "recommendation": ScoringService.get_recommendation(score),
            "job_title": job_title, "candidate_name": name,
        }
        for aid, job_id, resume_id, status, score, job_title, name in top_rows
    ]

    # ---- resume library health, in one pass
    health = (
        db.query(
            func.count(Resume.id),
            func.sum(case((Resume.processing_error.is_(None) & Resume.is_processed.is_(False), 1), else_=0)),
            func.sum(case((Resume.processing_error.isnot(None), 1), else_=0)),
            func.sum(case((
                Resume.is_processed.is_(True)
                & or_(Resume.candidate_email.is_(None), Resume.name_confidence < NAME_CONFIDENCE_THRESHOLD),
                1,
            ), else_=0)),
        )
        .filter(Resume.user_id == user_id)
        .one()
    )
    total_resumes, processing, failed, needs_review = (int(x or 0) for x in health)

    return {
        "kpis": {
            "open_jobs": int(job_counts.get("open", 0)),
            "closed_jobs": int(job_counts.get("closed", 0)),
            "total_applications": total_applications,
            "awaiting_decision": sum(counts.get(s, 0) for s in AWAITING_DECISION),
            "in_interview_stage": counts.get("shortlisted", 0) + counts.get("interview", 0),
            "hired": counts.get("hired", 0),
            "library_size": total_resumes,
        },
        "pipeline": pipeline,
        "top_candidates": top_candidates,
        "jobs": jobs,
        "library": {"processing": processing, "failed": failed, "needs_review": needs_review},
    }
