"""add_workers

Revision ID: f1b2c3d4e5f6
Revises: e37e4f2e712f
Create Date: 2026-07-04 15:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "e37e4f2e712f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "workers",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("hostname", sa.String(255), nullable=False, server_default=""),
        sa.Column("queue_ids", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("last_heartbeat_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("stopped_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_workers_status", "workers", ["status"])


def downgrade() -> None:
    op.drop_index("idx_workers_status", "workers")
    op.drop_table("workers")
