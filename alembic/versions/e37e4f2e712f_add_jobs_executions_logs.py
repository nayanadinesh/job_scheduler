"""add_jobs_executions_logs

Revision ID: e37e4f2e712f
Revises: 0a7f70019fca
Create Date: 2026-07-04 13:40:49.928170

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e37e4f2e712f'
down_revision: Union[str, Sequence[str], None] = '0a7f70019fca'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "jobs",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("queue_id", sa.String(), nullable=False),
        sa.Column("type", sa.String(100), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("status", sa.String(20), nullable=False, server_default="queued"),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("run_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("dedup_key", sa.String(255), nullable=True),
        sa.Column("worker_id", sa.String(), nullable=True),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["queue_id"], ["queues.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_jobs_status", "jobs", ["status"])
    op.create_index("idx_jobs_queue_id", "jobs", ["queue_id"])
    # Partial indexes (Postgres-only, skipped on SQLite)
    op.create_index(
        "idx_jobs_ready", "jobs", ["queue_id", "priority", "run_at"],
        postgresql_where=sa.text("status IN ('queued', 'scheduled')"),
    )
    op.create_index(
        "idx_jobs_dedup", "jobs", ["queue_id", "dedup_key"],
        unique=True,
        postgresql_where=sa.text("dedup_key IS NOT NULL"),
    )

    op.create_table(
        "job_executions",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("job_id", sa.String(), nullable=False),
        sa.Column("attempt_no", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("worker_id", sa.String(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="running"),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_executions_job", "job_executions", ["job_id", "attempt_no"])

    op.create_table(
        "job_logs",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("job_id", sa.String(), nullable=False),
        sa.Column("execution_id", sa.String(), nullable=True),
        sa.Column("ts", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("level", sa.String(10), nullable=False, server_default="INFO"),
        sa.Column("message", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["execution_id"], ["job_executions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_logs_job", "job_logs", ["job_id", "ts"])


def downgrade() -> None:
    op.drop_table("job_logs")
    op.drop_table("job_executions")
    op.drop_index("idx_jobs_dedup", "jobs")
    op.drop_index("idx_jobs_ready", "jobs")
    op.drop_index("idx_jobs_queue_id", "jobs")
    op.drop_index("idx_jobs_status", "jobs")
    op.drop_table("jobs")
