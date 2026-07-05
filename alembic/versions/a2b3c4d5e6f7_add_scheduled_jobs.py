"""add_scheduled_jobs

Revision ID: a2b3c4d5e6f7
Revises: f1b2c3d4e5f6
Create Date: 2026-07-04 16:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a2b3c4d5e6f7"
down_revision: Union[str, Sequence[str], None] = "f1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "scheduled_jobs",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("queue_id", sa.String(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("cron_expr", sa.String(100), nullable=False),
        sa.Column("job_type", sa.String(100), nullable=False),
        sa.Column("job_payload", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("last_fired_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["queue_id"], ["queues.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_scheduled_jobs_queue", "scheduled_jobs", ["queue_id"])
    op.create_index("idx_scheduled_jobs_next_run", "scheduled_jobs", ["next_run_at"])


def downgrade() -> None:
    op.drop_index("idx_scheduled_jobs_next_run", "scheduled_jobs")
    op.drop_index("idx_scheduled_jobs_queue", "scheduled_jobs")
    op.drop_table("scheduled_jobs")
