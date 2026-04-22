"""
Database models for the AI HR SaaS platform.
Uses SQLAlchemy for ORM with SQLite support and PostgreSQL compatibility.
Optimized for scalability with proper indexing and cascading deletes.
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, Float, DateTime, Boolean, LargeBinary, ForeignKey, Index, UniqueConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


class User(Base):
    """
    Recruiter user model for authentication.
    Optimized with indexes for fast lookups.
    """
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

    # Relationships with cascading deletes for data integrity
    resumes = relationship("Resume", back_populates="user", cascade="all, delete-orphan", lazy="select")
    searches = relationship("SearchHistory", back_populates="user", cascade="all, delete-orphan", lazy="select")
    candidate_matches = relationship("AICandidateMatch", back_populates="user", cascade="all, delete-orphan", lazy="select")
    interview_questions = relationship("InterviewQuestions", back_populates="user", cascade="all, delete-orphan", lazy="select")
    outreach_emails = relationship("OutreachEmail", back_populates="user", cascade="all, delete-orphan", lazy="select")
    job_descriptions = relationship("JobDescription", back_populates="user", cascade="all, delete-orphan", lazy="select")
    analytics = relationship("AnalyticsDashboard", back_populates="user", cascade="all, delete-orphan", uselist=False, lazy="select")

    def __repr__(self):
        return f"<User(id={self.id}, email={self.email}, username={self.username})>"

    @property
    def full_name(self):
        """Get user's full name."""
        return f"{self.first_name or ''} {self.last_name or ''}".strip() or "Unknown"

    def resume_count(self):
        """Get number of resumes for this user."""
        return len(self.resumes) if self.resumes else 0


class Resume(Base):
    """
    Resume model for storing resume metadata and embeddings index.
    Optimized with proper indexing and relationships.
    """
    __tablename__ = "resumes"
    __table_args__ = (
        Index('idx_resume_user_created', 'user_id', 'created_at'),
        Index('idx_resume_candidate_email', 'candidate_email'),
        Index('idx_resume_processed', 'is_processed'),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    file_name = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False, unique=True)
    candidate_name = Column(String(255), index=True)
    candidate_email = Column(String(255), index=True)
    candidate_phone = Column(String(20))
    extracted_text = Column(Text)
    experience_years = Column(Float)
    skills = Column(Text)  # JSON string of skills
    education = Column(Text)  # JSON string of education
    embedding_index = Column(Integer)  # Index in FAISS for quick lookup
    is_processed = Column(Boolean, default=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships with cascading deletes
    user = relationship("User", back_populates="resumes", lazy="select")
    search_results = relationship("SearchResult", back_populates="resume", cascade="all, delete-orphan", lazy="select")
    candidate_matches = relationship("AICandidateMatch", back_populates="resume", cascade="all, delete-orphan", lazy="select")
    interview_questions = relationship("InterviewQuestions", back_populates="resume", cascade="all, delete-orphan", lazy="select")
    outreach_emails = relationship("OutreachEmail", back_populates="resume", cascade="all, delete-orphan", lazy="select")

    def __repr__(self):
        return f"<Resume(id={self.id}, candidate={self.candidate_name}, processed={self.is_processed})>"

    @property
    def is_complete(self):
        """Check if resume has all essential information."""
        return all([self.candidate_name, self.candidate_email, self.extracted_text])

    def to_dict(self):
        """Convert resume to dictionary for API responses."""
        return {
            "id": self.id,
            "candidate_name": self.candidate_name,
            "candidate_email": self.candidate_email,
            "candidate_phone": self.candidate_phone,
            "experience_years": self.experience_years,
            "skills": self.skills,
            "education": self.education,
            "is_processed": self.is_processed,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class SearchHistory(Base):
    """
    Track search queries for analytics and caching.
    Optimized for historical tracking and analytics.
    """
    __tablename__ = "search_history"
    __table_args__ = (
        Index('idx_search_user_created', 'user_id', 'created_at'),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    query = Column(Text, nullable=False)
    job_title = Column(String(255), index=True)
    required_skills = Column(Text)  # JSON string
    min_experience = Column(Float)
    results_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    # Relationships
    user = relationship("User", back_populates="searches", lazy="select")
    results = relationship("SearchResult", backref="search_history", cascade="all, delete-orphan", lazy="select")

    def __repr__(self):
        return f"<SearchHistory(id={self.id}, job_title={self.job_title}, results={self.results_count})>"

    def to_dict(self):
        """Convert to dictionary."""
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
    """
    Store search results for analytics and history.
    Optimized with proper indexes for performance.
    """
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

    # Relationships
    resume = relationship("Resume", back_populates="search_results", lazy="select")

    def __repr__(self):
        return f"<SearchResult(id={self.id}, resume_id={self.resume_id}, score={self.final_score:.2f})>"

    def to_dict(self):
        """Convert to dictionary."""
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
    """
    Store AI-generated match analysis between candidate and job.
    Tracks recommendation and scoring for hiring decisions.
    """
    __tablename__ = "ai_candidate_matches"
    __table_args__ = (
        Index('idx_match_user_resume', 'user_id', 'resume_id'),
        Index('idx_match_recommendation', 'recommendation'),
    )

    id = Column(Integer, primary_key=True, index=True)
    resume_id = Column(Integer, ForeignKey("resumes.id", ondelete="CASCADE"), index=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    job_description = Column(Text, nullable=False)
    strengths = Column(Text)  # AI-generated
    weaknesses = Column(Text)  # AI-generated
    missing_skills = Column(Text)  # AI-generated (JSON array)
    recommendation = Column(String(50), index=True)  # Strong Hire / Consider / Reject
    match_score = Column(Float, default=0.0, index=True)
    explanation = Column(Text)  # AI-generated explanation
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    # Relationships
    user = relationship("User", back_populates="candidate_matches", lazy="select")
    resume = relationship("Resume", back_populates="candidate_matches", lazy="select")

    def __repr__(self):
        return f"<AICandidateMatch(candidate={self.resume_id}, recommendation={self.recommendation}, score={self.match_score})>"

    def to_dict(self):
        """Convert to dictionary."""
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
    """
    Store AI-generated interview questions.
    Tracks personalized questions for each candidate-job match.
    """
    __tablename__ = "interview_questions"
    __table_args__ = (
        Index('idx_interview_user_resume', 'user_id', 'resume_id'),
    )

    id = Column(Integer, primary_key=True, index=True)
    resume_id = Column(Integer, ForeignKey("resumes.id", ondelete="CASCADE"), index=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    job_title = Column(String(255), index=True)
    technical_questions = Column(Text)  # JSON array
    behavioral_questions = Column(Text)  # JSON array
    practical_tasks = Column(Text)  # JSON array
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    # Relationships
    user = relationship("User", back_populates="interview_questions", lazy="select")
    resume = relationship("Resume", back_populates="interview_questions", lazy="select")

    def __repr__(self):
        return f"<InterviewQuestions(resume_id={self.resume_id}, job={self.job_title})>"

    def to_dict(self):
        """Convert to dictionary."""
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
    """
    Store AI-generated outreach emails.
    Tracks candidate communications for recruiting workflow.
    """
    __tablename__ = "outreach_emails"
    __table_args__ = (
        Index('idx_email_user_resume', 'user_id', 'resume_id'),
        Index('idx_email_type', 'email_type'),
        Index('idx_email_sent', 'sent'),
    )

    id = Column(Integer, primary_key=True, index=True)
    resume_id = Column(Integer, ForeignKey("resumes.id", ondelete="CASCADE"), index=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    email_type = Column(String(50), index=True)  # interview_invite / rejection / cold_outreach
    job_title = Column(String(255))
    subject_line = Column(String(500))
    email_body = Column(Text)
    sent = Column(Boolean, default=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    # Relationships
    user = relationship("User", back_populates="outreach_emails", lazy="select")
    resume = relationship("Resume", back_populates="outreach_emails", lazy="select")

    def __repr__(self):
        return f"<OutreachEmail(resume_id={self.resume_id}, type={self.email_type}, sent={self.sent})>"

    def to_dict(self):
        """Convert to dictionary."""
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
    """
    Store AI-generated job descriptions.
    Templates for recruiting workflow optimization.
    """
    __tablename__ = "job_descriptions"
    __table_args__ = (
        Index('idx_user_id', 'user_id'),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    role_title = Column(String(255), nullable=False, index=True)
    role_shorthand = Column(Text)
    generated_description = Column(Text, nullable=False)
    required_skills = Column(Text)  # JSON array
    nice_to_have_skills = Column(Text)  # JSON array
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    # Relationships
    user = relationship("User", back_populates="job_descriptions", lazy="select")

    def __repr__(self):
        return f"<JobDescription(id={self.id}, role={self.role_title})>"

    def to_dict(self):
        """Convert to dictionary."""
        return {
            "id": self.id,
            "role_title": self.role_title,
            "role_shorthand": self.role_shorthand,
            "generated_description": self.generated_description,
            "required_skills": self.required_skills,
            "nice_to_have_skills": self.nice_to_have_skills,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class AnalyticsDashboard(Base):
    """
    Store aggregated analytics data per user.
    Optimized for dashboard display and reporting.
    """
    __tablename__ = "analytics_dashboard"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True, nullable=False)
    total_resumes = Column(Integer, default=0)
    total_searches = Column(Integer, default=0)
    avg_match_score = Column(Float, default=0.0)
    top_skills = Column(Text)  # JSON: {"skill": count}
    experience_distribution = Column(Text)  # JSON: {"0-2": count, "3-5": count, ...}
    total_candidates_hired = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, index=True)

    # Relationships
    user = relationship("User", back_populates="analytics", lazy="select")

    def __repr__(self):
        return f"<AnalyticsDashboard(user_id={self.user_id}, resumes={self.total_resumes})>"

    def to_dict(self):
        """Convert to dictionary."""
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
