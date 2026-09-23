"""Initial schema for HireAI V2 (PostgreSQL + pgvector)

Revision ID: 0001
Revises:
Create Date: 2026-09-21
"""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

EMBEDDING_DIM = 384


def _ix(table, *cols, unique=False, name=None):
    op.create_index(name or f"ix_{table}_{'_'.join(cols)}", table, list(cols), unique=unique)


def _id():
    return sa.Column("id", sa.Integer(), primary_key=True)


def _created(index=True):
    return sa.Column("created_at", sa.DateTime(), nullable=True)


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "users", _id(),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("username", sa.String(255), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("first_name", sa.String(255)), sa.Column("last_name", sa.String(255)),
        sa.Column("company", sa.String(255)),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true()),
        _created(), sa.Column("updated_at", sa.DateTime()),
    )
    _ix("users", "id"); _ix("users", "email", unique=True); _ix("users", "username", unique=True)
    _ix("users", "company"); _ix("users", "is_active"); _ix("users", "created_at")

    op.create_table(
        "resumes", _id(),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("file_name", sa.String(255), nullable=False),
        sa.Column("file_path", sa.String(500), nullable=False),
        sa.Column("candidate_name", sa.String(255)), sa.Column("candidate_email", sa.String(255)),
        sa.Column("candidate_phone", sa.String(32)),
        sa.Column("extracted_text", sa.Text()), sa.Column("experience_years", sa.Float()),
        sa.Column("skills", sa.Text()), sa.Column("education", sa.Text()),
        sa.Column("storage_backend", sa.String(20), server_default="local"),
        sa.Column("mime_type", sa.String(100)), sa.Column("size_bytes", sa.Integer()),
        sa.Column("content_hash", sa.String(64)), sa.Column("name_confidence", sa.Float()),
        sa.Column("extraction_meta", sa.Text()), sa.Column("processed_at", sa.DateTime()),
        sa.Column("is_processed", sa.Boolean(), server_default=sa.false()),
        sa.Column("processing_error", sa.Text()),
        _created(), sa.Column("updated_at", sa.DateTime()),
        sa.UniqueConstraint("file_path", name="uq_resumes_file_path"),
    )
    for col in ("id", "user_id", "candidate_name", "candidate_email", "content_hash", "is_processed", "created_at"):
        _ix("resumes", col)
    _ix("resumes", "user_id", "created_at", name="idx_resume_user_created")
    _ix("resumes", "candidate_email", name="idx_resume_candidate_email")
    _ix("resumes", "is_processed", name="idx_resume_processed")
    _ix("resumes", "user_id", "content_hash", name="idx_resume_user_hash")
    _ix("resumes", "user_id", "is_processed", "experience_years", name="idx_resume_user_processed_exp")

    op.create_table(
        "resume_chunks", _id(),
        sa.Column("resume_id", sa.Integer(), sa.ForeignKey("resumes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("chunk_text", sa.Text(), nullable=False),
        sa.Column("embedding", _vector_type(bind), nullable=False),
        _created(),
        sa.UniqueConstraint("resume_id", "chunk_index", name="uq_chunk_resume_index"),
    )
    _ix("resume_chunks", "id"); _ix("resume_chunks", "resume_id"); _ix("resume_chunks", "user_id")
    _ix("resume_chunks", "user_id", "resume_id", name="idx_chunk_user_resume")
    if bind.dialect.name == "postgresql":
        # Cosine HNSW. Fine to start with; benchmark recall/latency on real data before tuning m / ef_construction.
        op.execute(
            "CREATE INDEX idx_chunk_embedding_hnsw ON resume_chunks USING hnsw (embedding vector_cosine_ops)"
        )

    op.create_table(
        "search_history", _id(),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("query", sa.Text(), nullable=False), sa.Column("job_title", sa.String(255)),
        sa.Column("required_skills", sa.Text()), sa.Column("min_experience", sa.Float()),
        sa.Column("results_count", sa.Integer(), server_default="0"), _created(),
    )
    for col in ("id", "user_id", "job_title", "created_at"):
        _ix("search_history", col)
    _ix("search_history", "user_id", "created_at", name="idx_search_user_created")

    op.create_table(
        "search_results", _id(),
        sa.Column("search_history_id", sa.Integer(), sa.ForeignKey("search_history.id", ondelete="CASCADE"), nullable=False),
        sa.Column("resume_id", sa.Integer(), sa.ForeignKey("resumes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("semantic_similarity", sa.Float(), server_default="0"),
        sa.Column("experience_match", sa.Float(), server_default="0"),
        sa.Column("skill_overlap", sa.Float(), server_default="0"),
        sa.Column("final_score", sa.Float(), server_default="0"),
        sa.Column("rank", sa.Integer()), _created(),
    )
    for col in ("id", "search_history_id", "resume_id", "final_score"):
        _ix("search_results", col)
    _ix("search_results", "resume_id", name="idx_resume_id"); _ix("search_results", "final_score", name="idx_final_score")

    op.create_table(
        "ai_candidate_matches", _id(),
        sa.Column("resume_id", sa.Integer(), sa.ForeignKey("resumes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("job_description", sa.Text(), nullable=False),
        sa.Column("strengths", sa.Text()), sa.Column("weaknesses", sa.Text()), sa.Column("missing_skills", sa.Text()),
        sa.Column("recommendation", sa.String(50)), sa.Column("match_score", sa.Float(), server_default="0"),
        sa.Column("explanation", sa.Text()), _created(),
    )
    for col in ("id", "resume_id", "user_id", "recommendation", "match_score", "created_at"):
        _ix("ai_candidate_matches", col)
    _ix("ai_candidate_matches", "user_id", "resume_id", name="idx_match_user_resume")
    _ix("ai_candidate_matches", "recommendation", name="idx_match_recommendation")

    op.create_table(
        "interview_questions", _id(),
        sa.Column("resume_id", sa.Integer(), sa.ForeignKey("resumes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("job_title", sa.String(255)),
        sa.Column("technical_questions", sa.Text()), sa.Column("behavioral_questions", sa.Text()), sa.Column("practical_tasks", sa.Text()),
        _created(),
    )
    for col in ("id", "resume_id", "user_id", "job_title", "created_at"):
        _ix("interview_questions", col)
    _ix("interview_questions", "user_id", "resume_id", name="idx_interview_user_resume")

    op.create_table(
        "outreach_emails", _id(),
        sa.Column("resume_id", sa.Integer(), sa.ForeignKey("resumes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("email_type", sa.String(50)), sa.Column("job_title", sa.String(255)),
        sa.Column("subject_line", sa.String(500)), sa.Column("email_body", sa.Text()),
        sa.Column("sent", sa.Boolean(), server_default=sa.false()), _created(),
    )
    for col in ("id", "resume_id", "user_id", "email_type", "sent", "created_at"):
        _ix("outreach_emails", col)
    _ix("outreach_emails", "user_id", "resume_id", name="idx_email_user_resume")
    _ix("outreach_emails", "email_type", name="idx_email_type"); _ix("outreach_emails", "sent", name="idx_email_sent")

    op.create_table(
        "job_descriptions", _id(),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role_title", sa.String(255), nullable=False), sa.Column("role_shorthand", sa.Text()),
        sa.Column("generated_description", sa.Text(), nullable=False),
        sa.Column("required_skills", sa.Text()), sa.Column("nice_to_have_skills", sa.Text()), _created(),
    )
    for col in ("id", "user_id", "role_title", "created_at"):
        _ix("job_descriptions", col)
    _ix("job_descriptions", "user_id", name="idx_user_id")

    op.create_table(
        "jobs", _id(),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("public_slug", sa.String(32), nullable=False), sa.Column("title", sa.String(255), nullable=False),
        sa.Column("location", sa.String(255)), sa.Column("experience_min", sa.Float()),
        sa.Column("description", sa.Text(), nullable=False), sa.Column("required_skills", sa.Text()),
        sa.Column("status", sa.String(20), server_default="open"),
        _created(), sa.Column("updated_at", sa.DateTime()),
    )
    _ix("jobs", "id"); _ix("jobs", "user_id"); _ix("jobs", "public_slug", unique=True); _ix("jobs", "title")
    _ix("jobs", "status"); _ix("jobs", "created_at")
    _ix("jobs", "user_id", "created_at", name="idx_job_user_created"); _ix("jobs", "status", name="idx_job_status")

    op.create_table(
        "applications", _id(),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("resume_id", sa.Integer(), sa.ForeignKey("resumes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(20), server_default="received"),
        sa.Column("source", sa.String(20), server_default="form"),
        sa.Column("match_score", sa.Float()),
        sa.Column("applied_at", sa.DateTime()), sa.Column("updated_at", sa.DateTime()),
        sa.UniqueConstraint("job_id", "resume_id", name="uq_application_job_resume"),
    )
    for col in ("id", "job_id", "resume_id", "status", "applied_at"):
        _ix("applications", col)
    _ix("applications", "job_id", name="idx_application_job"); _ix("applications", "status", name="idx_application_status")
    _ix("applications", "job_id", "status", name="idx_application_job_status")

    op.create_table(
        "analytics_dashboard", _id(),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("total_resumes", sa.Integer(), server_default="0"), sa.Column("total_searches", sa.Integer(), server_default="0"),
        sa.Column("avg_match_score", sa.Float(), server_default="0"),
        sa.Column("top_skills", sa.Text()), sa.Column("experience_distribution", sa.Text()),
        sa.Column("total_candidates_hired", sa.Integer(), server_default="0"),
        _created(), sa.Column("updated_at", sa.DateTime()),
    )
    _ix("analytics_dashboard", "id"); _ix("analytics_dashboard", "user_id", unique=True)
    _ix("analytics_dashboard", "created_at"); _ix("analytics_dashboard", "updated_at")

    op.create_table(
        "refresh_tokens", _id(),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("jti", sa.String(64), nullable=False), sa.Column("family_id", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False), sa.Column("revoked_at", sa.DateTime()),
        sa.Column("replaced_by", sa.String(64)), sa.Column("user_agent", sa.String(255)), _created(),
    )
    _ix("refresh_tokens", "id"); _ix("refresh_tokens", "jti", unique=True); _ix("refresh_tokens", "family_id")
    _ix("refresh_tokens", "user_id", name="idx_refresh_user")

    op.create_table(
        "audit_logs", _id(),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("action", sa.String(64), nullable=False), sa.Column("resource_type", sa.String(32)),
        sa.Column("resource_id", sa.String(64)), sa.Column("ip_address", sa.String(64)),
        sa.Column("meta", sa.Text()), _created(),
    )
    _ix("audit_logs", "id"); _ix("audit_logs", "action"); _ix("audit_logs", "created_at")
    _ix("audit_logs", "user_id", "created_at", name="idx_audit_user_created")


def _vector_type(bind):
    if bind.dialect.name == "postgresql":
        from pgvector.sqlalchemy import Vector
        return Vector(EMBEDDING_DIM)
    return sa.LargeBinary()


def downgrade() -> None:
    for table in (
        "audit_logs", "refresh_tokens", "analytics_dashboard", "applications", "jobs", "job_descriptions",
        "outreach_emails", "interview_questions", "ai_candidate_matches", "search_results", "search_history",
        "resume_chunks", "resumes", "users",
    ):
        op.drop_table(table)
