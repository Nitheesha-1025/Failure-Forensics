"""create analysis_feedback table

Revision ID: 20260408_0004
Revises: 20260408_0003
Create Date: 2026-04-08

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260408_0004"
down_revision: Union[str, None] = "20260408_0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "analysis_feedback",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("trace_id", sa.String(length=64), nullable=False),
        sa.Column("decision", sa.String(length=32), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "trace_id", name="uq_analysis_feedback_user_trace"),
    )
    op.create_index(
        op.f("ix_analysis_feedback_user_id"), "analysis_feedback", ["user_id"], unique=False
    )
    op.create_index(
        op.f("ix_analysis_feedback_trace_id"), "analysis_feedback", ["trace_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_analysis_feedback_trace_id"), table_name="analysis_feedback")
    op.drop_index(op.f("ix_analysis_feedback_user_id"), table_name="analysis_feedback")
    op.drop_table("analysis_feedback")
