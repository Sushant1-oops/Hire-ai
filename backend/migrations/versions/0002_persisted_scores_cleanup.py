"""Persist per-application scores; drop two tables nothing used

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-02

* applications.score_details / scored_at: the score breakdown is computed once
  (when a resume finishes processing or its job changes) instead of on every
  view of a job's applicant list.
* applications.match_score gets an index (dashboard "top candidates" sorts on it).
* analytics_dashboard and search_results had models but no code that read or
  wrote them; they are dropped.

Every statement is idempotent: the API's startup schema sync may already have
added the new columns before this migration runs.
"""
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE applications ADD COLUMN IF NOT EXISTS score_details TEXT")
    op.execute("ALTER TABLE applications ADD COLUMN IF NOT EXISTS scored_at TIMESTAMP")
    op.execute("CREATE INDEX IF NOT EXISTS ix_applications_match_score ON applications (match_score)")
    op.execute("DROP TABLE IF EXISTS analytics_dashboard")
    op.execute("DROP TABLE IF EXISTS search_results")


def downgrade() -> None:
    # The two dropped tables held no data the application ever produced, so
    # they are not recreated.
    op.execute("DROP INDEX IF EXISTS ix_applications_match_score")
    op.execute("ALTER TABLE applications DROP COLUMN IF EXISTS scored_at")
    op.execute("ALTER TABLE applications DROP COLUMN IF EXISTS score_details")
