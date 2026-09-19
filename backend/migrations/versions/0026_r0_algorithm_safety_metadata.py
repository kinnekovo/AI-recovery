"""add R0 process-evidence safety metadata

Revision ID: 0026_r0_algorithm_safety
Revises: 0025_replace_sadtalker_with_aliyun_avatar
Create Date: 2026-09-19
"""

from alembic import op
import sqlalchemy as sa


revision = "0026_r0_algorithm_safety"
down_revision = "0025_replace_sadtalker_with_aliyun_avatar"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("attempt_evaluations", sa.Column("unit", sa.String(length=40), nullable=True))
    op.add_column("attempt_evaluations", sa.Column("algorithm_version", sa.String(length=80), nullable=True))
    op.add_column("attempt_evaluations", sa.Column("quality_status", sa.String(length=32), nullable=True))
    op.add_column(
        "attempt_evaluations",
        sa.Column("decision_eligible", sa.Boolean(), server_default=sa.false(), nullable=False),
    )

    # Existing rows stay explicitly ineligible: their per-result unit/version was
    # not stored, so inferring it would silently reinterpret historical evidence.
    op.execute(
        sa.text(
            """
            UPDATE evaluation_metrics
            SET unit = 'dBFS',
                description = '有效发声片段的相对数字响度；未经设备校准，不等同于临床 dBA。',
                normal_range = CAST(:normal_range AS jsonb),
                updated_at = now()
            WHERE name = 'loudness'
            """
        ).bindparams(
            normal_range='{"min": -35, "max": -12, "unit": "dBFS", "domain": "repeat.voice_state", "maturity": "E1", "source": "engineering heuristic", "version": "r0-engineering-safety-v1"}'
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            """
            UPDATE evaluation_metrics
            SET unit = 'dBA',
                description = '训练录音的平均响度。',
                normal_range = CAST(:normal_range AS jsonb),
                updated_at = now()
            WHERE name = 'loudness'
            """
        ).bindparams(normal_range='{"min": 60, "max": 78}')
    )
    op.drop_column("attempt_evaluations", "decision_eligible")
    op.drop_column("attempt_evaluations", "quality_status")
    op.drop_column("attempt_evaluations", "algorithm_version")
    op.drop_column("attempt_evaluations", "unit")
