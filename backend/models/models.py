"""
Database models for the AI HR SaaS platform.
Uses SQLAlchemy for ORM with PostgreSQL and pgvector.
Optimized for scalability with proper indexing and cascading deletes.
"""

from datetime import datetime

import numpy as np
from sqlalchemy import Column, Integer, String, Text, Float, DateTime, Boolean, LargeBinary, ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.types import TypeDecorator

from core.config import EMBEDDING_DIM

Base = declarative_base()


class EmbeddingType(TypeDecorator):
    """pgvector's Vector(384) on PostgreSQL. Python always sees a numpy float32 array."""

    impl = LargeBinary
    cache_ok = True

    def load_dialect_impl(self, dialect):
        from pgvector.sqlalchemy import Vector
        return dialect.type_descriptor(Vector(EMBEDDING_DIM))

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        arr = np.asarray(value, dtype=np.float32).reshape(-1)
        if arr.shape[0] != EMBEDDING_DIM:
            raise ValueError(f"expected a {EMBEDDING_DIM}-d embedding, got {arr.shape[0]}")
        return arr.tolist()

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return np.asarray(value, dtype=np.float32)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    username = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    first_name = Column(String(255))
    last_name = Column(String(255))
    company = Column(String(255), index=True)
    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    resumes = relationship("Resume", back_populates="user", cascade="all, delete-orphan", lazy="select")
    searches = relationship("SearchHistory", back_populates="user", cascade="all, delete-orphan", lazy="select")
    candidate_matches = relationship("AICandidateMatch", back_populates="user", cascade="all, delete-orphan", lazy="select")
    interview_questions = relationship("InterviewQuestions", back_populates="user", cascade="all, delete-orphan", lazy="select")
    outreach_emails = relationship("OutreachEmail", back_populates="user", cascade="all, delete-orphan", lazy="select")
    job_descriptions = relationship("JobDescription", back_populates="user", cascade="all, delete-orphan", lazy="select")
    analytics = relationship("AnalyticsDashboard", back_populates="user", cascade="all, delete-orphan", uselist=False, lazy="select")
    jobs = relationship("Job", back_populates="user", cascade="all, delete-orphan", lazy="select")

    def __repr__(self):
        return f"<User(id={self.id}, email={self.email}, username={self.username})>"

    @property
    def full_name(self):
        return f"{self.first_name or ''} {self.last_name or ''}".strip() or "Unknown"

    def resume_count(self):
        return len(self.resumes) if self.resumes else 0


class Resume(Base):
    __tablename__ = "resumes"
    __table_args__ = (
        Index('idx_resume_user_created', 'user_id', 'created_at'),
        Index('idx_resume_candidate_email', 'candidate_email'),
        Index('idx_resume_processed', 'is_processed'),
        Index('idx_resume_user_hash', 'user_id', 'content_hash'),
        Index('idx_resume_user_processed_exp', 'user_id', 'is_processed', 'experience_years'),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    file_name = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False, unique=True)
    candidate_name = Column(String(255), index=True)
    candidate_email = Column(String(255), index=True)
    candidate_phone = Column(String(32))
    extracted_text = Column(Text)
    experience_years = Column(Float)
    skills = Column(Text)  # JSON string of skills
    education = Column(Text)  # JSON string of education
    storage_backend = Column(String(20), default="local")  # local | cloudinary; file_path holds the storage key
    mime_type = Column(String(100))
    size_bytes = Column(Integer)
    content_hash = Column(String(64), index=True)  # sha256 of the uploaded file, used for per-tenant dedup
    name_confidence = Column(Float)
    extraction_meta = Column(Text)  # JSON: per-field confidence, ocr/ner flags, unrecognised skill candidates
    processed_at = Column(DateTime)
    is_processed = Column(Boolean, default=False, index=True)
    processing_error = Column(Text)  # set if background parsing/embedding failed (see pipeline_service.py)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="resumes", lazy="select")
    search_results = relationship("SearchResult", back_populates="resume", cascade="all, delete-orphan", lazy="select")
    candidate_matches = relationship("AICandidateMatch", back_populates="resume", cascade="all, delete-orphan", lazy="select")
    interview_questions = relationship("InterviewQuestions", back_populates="resume", cascade="all, delete-orphan", lazy="select")
    outreach_emails = relationship("OutreachEmail", back_populates="resume", cascade="all, delete-orphan", lazy="select")
    applications = relationship("Application", back_populates="resume", cascade="all, delete-orphan", lazy="select")
    chunks = relationship("ResumeChunk", back_populates="resume", cascade="all, delete-orphan", lazy="select")

    def __repr__(self):
        return f"<Resume(id={self.id}, candidate={self.candidate_name}, processed={self.is_processed})>"

    @property
    def processing_status(self):
        if self.processing_error:
            return "failed"
        return "ready" if self.is_processed else "pending"

    @property
    def is_complete(self):
        return all([self.candidate_name, self.candidate_email, self.extracted_text])

    def to_dict(self):
        return {
            "id": self.id,
            "candidate_name": self.candidate_name,
            "candidate_email": self.candidate_email,
            "candidate_phone": self.candidate_phone,
            "experience_years": self.experience_years,
            "skills": self.skills,
            "education": self.education,
            "is_processed": self.is_processed,
            "processing_status": self.processing_status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class ResumeChunk(Base):
    """One embedded slice of a resume. `user_id` is the tenant (each HR account
    is its own tenant) and is denormalised here on purpose so a vector query can
    filter by tenant without a join."""
    __tablename__ = "resume_chunks"
    __table_args__ = (
        UniqueConstraint('resume_id', 'chunk_index', name='uq_chunk_resume_index'),
        Index('idx_chunk_user_resume', 'user_id', 'resume_id'),
    )

    id = Column(Integer, primary_key=True, index=True)
    resume_id = Column(Integer, ForeignKey("resumes.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    chunk_index = Column(Integer, nullable=False)
    chunk_text = Column(Text, nullable=False)
    embedding = Column(EmbeddingType, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    resume = relationship("Resume", back_populates="chunks", lazy="select")


class SearchHistory(Base):
    __tablename__ = "search_history"
    __table_args__ = (
        Index('idx_search_user_created', 'user_id', 'created_at'),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    query = Column(Text, nullable=False)
    job_title = Column(String(255), index=True)
    required_skills = Column(Text)
    min_experience = Column(Float)
    results_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    user = relationship("User", back_populates="searches", lazy="select")
    results = relationship("SearchResult", backref="search_history", cascade="all, delete-orphan", lazy="select")

    def __repr__(self):
        return f"<SearchHistory(id={self.id}, job_title={self.job_title}, results={self.results_count})>"

    def to_dict(self):
        return {
            "id": self.id,
            "query": self.query,
            "job_title": self.job_title,
            "required_skills": self.required_skills,
            "min_experience": self.min_experience,
            "results_count": self.results_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class SearchResult(Base):
    __tablename__ = "search_results"
    __table_args__ = (
        Index('idx_resume_id', 'resume_id'),
        Index('idx_final_score', 'final_score'),
    )

    id = Column(Integer, primary_key=True, index=True)
    search_history_id = Column(Integer, ForeignKey("search_history.id", ondelete="CASCADE"), index=True, nullable=False)
    resume_id = Column(Integer, ForeignKey("resumes.id", ondelete="CASCADE"), index=True, nullable=False)
    semantic_similarity = Column(Float, default=0.0)
    experience_match = Column(Float, default=0.0)
    skill_overlap = Column(Float, default=0.0)
    final_score = Column(Float, default=0.0, index=True)
    rank = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)

    resume = relationship("Resume", back_populates="search_results", lazy="select")

    def __repr__(self):
        return f"<SearchResult(id={self.id}, resume_id={self.resume_id}, score={self.final_score:.2f})>"

    def to_dict(self):
        return {
            "id": self.id,
            "resume_id": self.resume_id,
            "semantic_similarity": round(self.semantic_similarity, 3),
            "experience_match": round(self.experience_match, 3),
            "skill_overlap": round(self.skill_overlap, 3),
            "final_score": round(self.final_score, 3),
            "rank": self.rank,
        }


class AICandidateMatch(Base):
    __tablename__ = "ai_candidate_matches"
    __table_args__ = (
        Index('idx_match_user_resume', 'user_id', 'resume_id'),
        Index('idx_match_recommendation', 'recommendation'),
    )

    id = Column(Integer, primary_key=True, index=True)
    resume_id = Column(Integer, ForeignKey("resumes.id", ondelete="CASCADE"), index=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    job_description = Column(Text, nullable=False)
    strengths = Column(Text)
    weaknesses = Column(Text)
    missing_skills = Column(Text)
    recommendation = Column(String(50), index=True)
    match_score = Column(Float, default=0.0, index=True)
    explanation = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    user = relationship("User", back_populates="candidate_matches", lazy="select")
    resume = relationship("Resume", back_populates="candidate_matches", lazy="select")

    def __repr__(self):
        return f"<AICandidateMatch(candidate={self.resume_id}, recommendation={self.recommendation}, score={self.match_score})>"

    def to_dict(self):
        return {
            "id": self.id,
            "resume_id": self.resume_id,
            "recommendation": self.recommendation,
            "match_score": round(self.match_score, 2),
            "strengths": self.strengths,
            "weaknesses": self.weaknesses,
            "missing_skills": self.missing_skills,
            "explanation": self.explanation,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class InterviewQuestions(Base):
    __tablename__ = "interview_questions"
    __table_args__ = (
        Index('idx_interview_user_resume', 'user_id', 'resume_id'),
    )

    id = Column(Integer, primary_key=True, index=True)
    resume_id = Column(Integer, ForeignKey("resumes.id", ondelete="CASCADE"), index=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    job_title = Column(String(255), index=True)
    technical_questions = Column(Text)
    behavioral_questions = Column(Text)
    practical_tasks = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    user = relationship("User", back_populates="interview_questions", lazy="select")
    resume = relationship("Resume", back_populates="interview_questions", lazy="select")

    def __repr__(self):
        return f"<InterviewQuestions(resume_id={self.resume_id}, job={self.job_title})>"

    def to_dict(self):
        return {
            "id": self.id,
            "resume_id": self.resume_id,
            "job_title": self.job_title,
            "technical_questions": self.technical_questions,
            "behavioral_questions": self.behavioral_questions,
            "practical_tasks": self.practical_tasks,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class OutreachEmail(Base):
    __tablename__ = "outreach_emails"
    __table_args__ = (
        Index('idx_email_user_resume', 'user_id', 'resume_id'),
        Index('idx_email_type', 'email_type'),
        Index('idx_email_sent', 'sent'),
    )

    id = Column(Integer, primary_key=True, index=True)
    resume_id = Column(Integer, ForeignKey("resumes.id", ondelete="CASCADE"), index=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    email_type = Column(String(50), index=True)
    job_title = Column(String(255))
    subject_line = Column(String(500))
    email_body = Column(Text)
    sent = Column(Boolean, default=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    user = relationship("User", back_populates="outreach_emails", lazy="select")
    resume = relationship("Resume", back_populates="outreach_emails", lazy="select")

    def __repr__(self):
        return f"<OutreachEmail(resume_id={self.resume_id}, type={self.email_type}, sent={self.sent})>"

    def to_dict(self):
        return {
            "id": self.id,
            "resume_id": self.resume_id,
            "email_type": self.email_type,
            "job_title": self.job_title,
            "subject_line": self.subject_line,
            "email_body": self.email_body,
            "sent": self.sent,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class JobDescription(Base):
    __tablename__ = "job_descriptions"
    __table_args__ = (
        Index('idx_user_id', 'user_id'),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    role_title = Column(String(255), nullable=False, index=True)
    role_shorthand = Column(Text)
    generated_description = Column(Text, nullable=False)
    required_skills = Column(Text)
    nice_to_have_skills = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    user = relationship("User", back_populates="job_descriptions", lazy="select")

    def __repr__(self):
        return f"<JobDescription(id={self.id}, role={self.role_title})>"

    def to_dict(self):
        return {
            "id": self.id,
            "role_title": self.role_title,
            "role_shorthand": self.role_shorthand,
            "generated_description": self.generated_description,
            "required_skills": self.required_skills,
            "nice_to_have_skills": self.nice_to_have_skills,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Job(Base):
    """A job posting created by an HR user. Exposed publicly via public_slug
    so candidates can apply without a HireAI account (GET/POST /api/public/jobs/{slug})."""
    __tablename__ = "jobs"
    __table_args__ = (
        Index('idx_job_user_created', 'user_id', 'created_at'),
        Index('idx_job_status', 'status'),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    public_slug = Column(String(32), unique=True, index=True, nullable=False)
    title = Column(String(255), nullable=False, index=True)
    location = Column(String(255))
    experience_min = Column(Float)
    description = Column(Text, nullable=False)
    required_skills = Column(Text)  # JSON list
    status = Column(String(20), default="open", index=True)  # open | closed
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="jobs", lazy="select")
    applications = relationship("Application", back_populates="job", cascade="all, delete-orphan", lazy="select")

    def __repr__(self):
        return f"<Job(id={self.id}, title={self.title}, status={self.status})>"

    def to_dict(self):
        from core.utils import safe_json_loads
        return {
            "id": self.id,
            "public_slug": self.public_slug,
            "title": self.title,
            "location": self.location,
            "experience_min": self.experience_min,
            "description": self.description,
            "required_skills": safe_json_loads(self.required_skills, []),
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Application(Base):
    """Links a Resume (candidate) to a Job. A candidate can apply to several jobs,
    so each (job, resume) pair gets its own row rather than duplicating the resume."""
    __tablename__ = "applications"
    __table_args__ = (
        UniqueConstraint('job_id', 'resume_id', name='uq_application_job_resume'),
        Index('idx_application_job', 'job_id'),
        Index('idx_application_status', 'status'),
        Index('idx_application_job_status', 'job_id', 'status'),
    )

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id", ondelete="CASCADE"), index=True, nullable=False)
    resume_id = Column(Integer, ForeignKey("resumes.id", ondelete="CASCADE"), index=True, nullable=False)
    status = Column(String(20), default="received", index=True)
    # received | screened | shortlisted | rejected | interview | hired
    source = Column(String(20), default="form")  # form | email | manual
    match_score = Column(Float)
    applied_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    job = relationship("Job", back_populates="applications", lazy="select")
    resume = relationship("Resume", back_populates="applications", lazy="select")

    def __repr__(self):
        return f"<Application(job_id={self.job_id}, resume_id={self.resume_id}, status={self.status})>"

    def to_dict(self):
        return {
            "id": self.id,
            "job_id": self.job_id,
            "resume_id": self.resume_id,
            "status": self.status,
            "source": self.source,
            "match_score": round(self.match_score, 3) if self.match_score is not None else None,
            "applied_at": self.applied_at.isoformat() if self.applied_at else None,
        }


class AnalyticsDashboard(Base):
    __tablename__ = "analytics_dashboard"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True, nullable=False)
    total_resumes = Column(Integer, default=0)
    total_searches = Column(Integer, default=0)
    avg_match_score = Column(Float, default=0.0)
    top_skills = Column(Text)
    experience_distribution = Column(Text)
    total_candidates_hired = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, index=True)

    user = relationship("User", back_populates="analytics", lazy="select")

    def __repr__(self):
        return f"<AnalyticsDashboard(user_id={self.user_id}, resumes={self.total_resumes})>"

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "total_resumes": self.total_resumes,
            "total_searches": self.total_searches,
            "avg_match_score": round(self.avg_match_score, 2),
            "top_skills": self.top_skills,
            "experience_distribution": self.experience_distribution,
            "total_candidates_hired": self.total_candidates_hired,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class RefreshToken(Base):
    """Server-side record of every refresh token issued. Tokens rotate on use:
    the presented row is revoked and a new one is created in the same family.
    Presenting an already-revoked token means it leaked, so the whole family
    is revoked."""
    __tablename__ = "refresh_tokens"
    __table_args__ = (
        Index('idx_refresh_user', 'user_id'),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    jti = Column(String(64), unique=True, index=True, nullable=False)
    family_id = Column(String(64), index=True, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    revoked_at = Column(DateTime)
    replaced_by = Column(String(64))
    user_agent = Column(String(255))
    created_at = Column(DateTime, default=datetime.utcnow)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index('idx_audit_user_created', 'user_id', 'created_at'),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    action = Column(String(64), index=True, nullable=False)
    resource_type = Column(String(32))
    resource_id = Column(String(64))
    ip_address = Column(String(64))
    meta = Column(Text)  # small JSON blob, never resume contents
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
