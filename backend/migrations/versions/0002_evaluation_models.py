"""add rehabilitation evaluation models

Revision ID: 0002_evaluation_models
Revises: 0001_initial_mvp
Create Date: 2026-08-08
"""
from datetime import datetime, timezone
import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0002_evaluation_models"
down_revision = "0001_initial_mvp"
branch_labels = None
depends_on = None


def _metric_id(name: str) -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_DNS, f"speech-agent.evaluation.metric.{name}")


def upgrade() -> None:
    metric_category = postgresql.ENUM("process", "long_term_effect", name="evaluation_metric_category", create_type=False)
    evaluation_source = postgresql.ENUM("mock_ai", "human", "clinician", name="evaluation_source", create_type=False)
    metric_category.create(op.get_bind(), checkfirst=True)
    evaluation_source.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "evaluation_metrics",
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("category", metric_category, nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("unit", sa.String(length=40), nullable=True),
        sa.Column("normal_range", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_index(op.f("ix_evaluation_metrics_category"), "evaluation_metrics", ["category"], unique=False)
    op.create_index(op.f("ix_evaluation_metrics_name"), "evaluation_metrics", ["name"], unique=True)

    op.create_table(
        "attempt_evaluations",
        sa.Column("attempt_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("metric_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("evaluation_source", evaluation_source, nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["attempt_id"], ["attempts.id"]),
        sa.ForeignKeyConstraint(["metric_id"], ["evaluation_metrics.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("attempt_id", "metric_id", "evaluation_source", name="uq_attempt_metric_source"),
    )
    op.create_index(op.f("ix_attempt_evaluations_attempt_id"), "attempt_evaluations", ["attempt_id"], unique=False)
    op.create_index(op.f("ix_attempt_evaluations_metric_id"), "attempt_evaluations", ["metric_id"], unique=False)

    now = datetime.now(timezone.utc)
    metrics_table = sa.table(
        "evaluation_metrics",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("name", sa.String),
        sa.column("category", metric_category),
        sa.column("description", sa.Text),
        sa.column("unit", sa.String),
        sa.column("normal_range", postgresql.JSONB),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    op.bulk_insert(
        metrics_table,
        [
            {
                "id": _metric_id("script_accuracy"),
                "name": "script_accuracy",
                "category": "process",
                "description": "正确发音字数 / 脚本总字数，用于衡量脚本输出完整性。",
                "unit": "%",
                "normal_range": {"target": 100, "operator": ">="},
                "created_at": now,
                "updated_at": now,
            },
            {
                "id": _metric_id("error_count"),
                "name": "error_count",
                "category": "process",
                "description": "无意义重复、超过3秒停顿、难以理解发音和插入语的总次数。",
                "unit": "次",
                "normal_range": {"target": 0, "operator": "=="},
                "created_at": now,
                "updated_at": now,
            },
            {
                "id": _metric_id("speech_rate"),
                "name": "speech_rate",
                "category": "process",
                "description": "有效交流字数 / 说话时间。",
                "unit": "字/min",
                "normal_range": {"min": 180, "max": 240},
                "created_at": now,
                "updated_at": now,
            },
            {
                "id": _metric_id("loudness"),
                "name": "loudness",
                "category": "process",
                "description": "训练录音的平均响度。",
                "unit": "dBA",
                "normal_range": {"min": 60, "max": 78},
                "created_at": now,
                "updated_at": now,
            },
            {
                "id": _metric_id("wab_information"),
                "name": "wab_information",
                "category": "long_term_effect",
                "description": "WAB 自发言语信息量。",
                "unit": "分",
                "normal_range": {},
                "created_at": now,
                "updated_at": now,
            },
            {
                "id": _metric_id("wab_fluency"),
                "name": "wab_fluency",
                "category": "long_term_effect",
                "description": "WAB 自发言语流利性。",
                "unit": "分",
                "normal_range": {},
                "created_at": now,
                "updated_at": now,
            },
            {
                "id": _metric_id("wab_grammar"),
                "name": "wab_grammar",
                "category": "long_term_effect",
                "description": "WAB 自发言语语法能力。",
                "unit": "分",
                "normal_range": {},
                "created_at": now,
                "updated_at": now,
            },
            {
                "id": _metric_id("wab_word_order"),
                "name": "wab_word_order",
                "category": "long_term_effect",
                "description": "WAB 自发言语语序。",
                "unit": "分",
                "normal_range": {},
                "created_at": now,
                "updated_at": now,
            },
            {
                "id": _metric_id("wab_comprehensibility"),
                "name": "wab_comprehensibility",
                "category": "long_term_effect",
                "description": "WAB 自发言语可懂度。",
                "unit": "分",
                "normal_range": {},
                "created_at": now,
                "updated_at": now,
            },
            {
                "id": _metric_id("wab_repetition_comprehensibility"),
                "name": "wab_repetition_comprehensibility",
                "category": "long_term_effect",
                "description": "WAB 复述可懂度。",
                "unit": "分",
                "normal_range": {},
                "created_at": now,
                "updated_at": now,
            },
            {
                "id": _metric_id("cadl_score"),
                "name": "cadl_score",
                "category": "long_term_effect",
                "description": "CADL 日常交流能力评分。",
                "unit": "分",
                "normal_range": {},
                "created_at": now,
                "updated_at": now,
            },
            {
                "id": _metric_id("acceptance_score"),
                "name": "acceptance_score",
                "category": "long_term_effect",
                "description": "患者或家属对训练方式、智能体和交互流程的接受度。",
                "unit": "分",
                "normal_range": {},
                "created_at": now,
                "updated_at": now,
            },
        ],
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_attempt_evaluations_metric_id"), table_name="attempt_evaluations")
    op.drop_index(op.f("ix_attempt_evaluations_attempt_id"), table_name="attempt_evaluations")
    op.drop_table("attempt_evaluations")
    op.drop_index(op.f("ix_evaluation_metrics_name"), table_name="evaluation_metrics")
    op.drop_index(op.f("ix_evaluation_metrics_category"), table_name="evaluation_metrics")
    op.drop_table("evaluation_metrics")
    sa.Enum(name="evaluation_source").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="evaluation_metric_category").drop(op.get_bind(), checkfirst=True)
