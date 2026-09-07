"""add rehabilitation evaluation models

Revision ID: 0002_evaluation_models
Revises: 0001_initial_mvp
Create Date: 2026-08-08
"""
from datetime import datetime, timezone
import json
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


def _sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _insert_metric(
    *,
    name: str,
    category: str,
    description: str,
    unit: str,
    normal_range: dict,
    now: datetime,
) -> None:
    op.execute(
        sa.text(
            "\n".join(
                [
                    "INSERT INTO evaluation_metrics",
                    "(id, name, category, description, unit, normal_range, created_at, updated_at)",
                    "VALUES",
                    "(",
                    f"{_sql_literal(str(_metric_id(name)))}::uuid,",
                    f"{_sql_literal(name)},",
                    f"{_sql_literal(category)},",
                    f"{_sql_literal(description)},",
                    f"{_sql_literal(unit)},",
                    f"{_sql_literal(json.dumps(normal_range, ensure_ascii=False))}::jsonb,",
                    f"{_sql_literal(now.isoformat())}::timestamptz,",
                    f"{_sql_literal(now.isoformat())}::timestamptz",
                    ");",
                ]
            )
        )
    )


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
    metric_rows = [
        ("script_accuracy", "process", "正确发音字数 / 脚本总字数，用于衡量脚本输出完整性。", "%", {"target": 100, "operator": ">="}),
        ("error_count", "process", "无意义重复、超过3秒停顿、难以理解发音和插入语的总次数。", "次", {"target": 0, "operator": "=="}),
        ("speech_rate", "process", "有效交流字数 / 说话时间。", "字/min", {"min": 180, "max": 240}),
        ("loudness", "process", "训练录音的平均响度。", "dBA", {"min": 60, "max": 78}),
        ("wab_information", "long_term_effect", "WAB 自发言语信息量。", "分", {}),
        ("wab_fluency", "long_term_effect", "WAB 自发言语流利性。", "分", {}),
        ("wab_grammar", "long_term_effect", "WAB 自发言语语法能力。", "分", {}),
        ("wab_word_order", "long_term_effect", "WAB 自发言语语序。", "分", {}),
        ("wab_comprehensibility", "long_term_effect", "WAB 自发言语可懂度。", "分", {}),
        ("wab_repetition_comprehensibility", "long_term_effect", "WAB 复述可懂度。", "分", {}),
        ("cadl_score", "long_term_effect", "CADL 日常交流能力评分。", "分", {}),
        ("acceptance_score", "long_term_effect", "患者或家属对训练方式、智能体和交互流程的接受度。", "分", {}),
    ]
    for name, category, description, unit, normal_range in metric_rows:
        _insert_metric(
            name=name,
            category=category,
            description=description,
            unit=unit,
            normal_range=normal_range,
            now=now,
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
