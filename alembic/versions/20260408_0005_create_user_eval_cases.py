"""create user_eval_cases table

Revision ID: 20260408_0005
Revises: 20260408_0004
Create Date: 2026-04-08

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260408_0005"
down_revision: Union[str, None] = "20260408_0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_eval_cases",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("trace_id", sa.String(length=64), nullable=False),
        sa.Column("feedback_id", sa.String(length=36), nullable=False),
        sa.Column("document_id", sa.String(length=36), nullable=True),
        sa.Column("pipeline_run_id", sa.String(length=36), nullable=True),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column("human_decision", sa.String(length=32), nullable=False),
        sa.Column("human_comment", sa.Text(), nullable=True),
        sa.Column("expected_root_cause_span_id", sa.String(length=64), nullable=True),
        sa.Column("expected_root_cause_span_name", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["feedback_id"], ["analysis_feedback.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "trace_id", name="uq_user_eval_cases_user_trace"),
    )
    op.create_index(op.f("ix_user_eval_cases_user_id"), "user_eval_cases", ["user_id"], unique=False)
    op.create_index(op.f("ix_user_eval_cases_trace_id"), "user_eval_cases", ["trace_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_user_eval_cases_trace_id"), table_name="user_eval_cases")
    op.drop_index(op.f("ix_user_eval_cases_user_id"), table_name="user_eval_cases")
    op.drop_table("user_eval_cases")
