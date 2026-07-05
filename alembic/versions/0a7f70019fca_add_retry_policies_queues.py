"""add_retry_policies_queues

Revision ID: 0a7f70019fca
Revises: d423187148d7
Create Date: 2026-07-04 13:34:49.576762

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0a7f70019fca'
down_revision: Union[str, Sequence[str], None] = 'd423187148d7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "retry_policies",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("strategy", sa.String(20), nullable=False, server_default="exponential"),
        sa.Column("base_delay_s", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("max_delay_s", sa.Integer(), nullable=False, server_default="3600"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "queues",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("project_id", sa.String(), nullable=False),
        sa.Column("retry_policy_id", sa.String(), nullable=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("concurrency_limit", sa.Integer(), nullable=False, server_default="10"),
        sa.Column("is_paused", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["retry_policy_id"], ["retry_policies.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("queues")
    op.drop_table("retry_policies")
