"""create pipeline_runs table

Revision ID: 20260408_0003
Revises: 20260408_0002
Create Date: 2026-04-08

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260408_0003"
down_revision: Union[str, None] = "20260408_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "pipeline_runs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("document_id", sa.String(length=36), nullable=False),
        sa.Column("trace_id", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_pipeline_runs_user_id"), "pipeline_runs", ["user_id"], unique=False)
    op.create_index(
        op.f("ix_pipeline_runs_document_id"), "pipeline_runs", ["document_id"], unique=False
    )
    op.create_index(
        op.f("ix_pipeline_runs_trace_id"), "pipeline_runs", ["trace_id"], unique=False
    )
    op.create_index(
        "ix_pipeline_runs_document_created",
        "pipeline_runs",
        ["document_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_pipeline_runs_document_created", table_name="pipeline_runs")
    op.drop_index(op.f("ix_pipeline_runs_trace_id"), table_name="pipeline_runs")
    op.drop_index(op.f("ix_pipeline_runs_document_id"), table_name="pipeline_runs")
    op.drop_index(op.f("ix_pipeline_runs_user_id"), table_name="pipeline_runs")
    op.drop_table("pipeline_runs")
