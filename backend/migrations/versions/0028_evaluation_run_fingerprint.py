"""add V3 evaluation-run input fingerprint

Revision ID: 0028_eval_run_fingerprint
Revises: 0027_evaluation_runs_v3
"""

from alembic import op
import sqlalchemy as sa


revision = "0028_eval_run_fingerprint"
down_revision = "0027_evaluation_runs_v3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("evaluation_runs", sa.Column("input_fingerprint", sa.String(length=64), nullable=True))
    op.create_index("ix_evaluation_runs_input_fingerprint", "evaluation_runs", ["input_fingerprint"])
    op.create_index(
        "uq_evaluation_runs_source_algorithm_fingerprint",
        "evaluation_runs",
        ["source_type", "source_id", "domain", "algorithm_version", "input_fingerprint"],
        unique=True,
        postgresql_where=sa.text("input_fingerprint IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_evaluation_runs_source_algorithm_fingerprint", table_name="evaluation_runs")
    op.drop_index("ix_evaluation_runs_input_fingerprint", table_name="evaluation_runs")
    op.drop_column("evaluation_runs", "input_fingerprint")
