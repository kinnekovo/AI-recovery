"""add traceable stage clinical assessment metadata

Revision ID: 0030_clinical_stage_metadata
Revises: 0029_eval_write_retry
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
revision = "0030_clinical_stage_metadata"
down_revision = "0029_eval_write_retry"
branch_labels = None
depends_on = None

def upgrade():
    cols = [
      sa.Column("instrument_name", sa.String(120)), sa.Column("instrument_version", sa.String(80)), sa.Column("language_locale", sa.String(40)), sa.Column("localization_version", sa.String(80)), sa.Column("assessment_stage", sa.String(32)),
      sa.Column("administered_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id")), sa.Column("administrator_role", sa.String(80)), sa.Column("qualification_note", sa.Text()),
      sa.Column("raw_item_results", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")), sa.Column("subscale_results", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")), sa.Column("total_result", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")), sa.Column("missing_items", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")), sa.Column("score_unit", sa.String(40)), sa.Column("administration_mode", sa.String(20)), sa.Column("device_and_environment", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")), sa.Column("duration_seconds", sa.Integer()), sa.Column("protocol_deviations", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")), sa.Column("protocol_deviation_reasons", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")), sa.Column("comparison_baseline_session_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("assessment_sessions.id")), sa.Column("comparability_status", sa.String(32)), sa.Column("non_comparable_reasons", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb"))]
    for col in cols: op.add_column("assessment_sessions", col)
def downgrade():
    for name in ["non_comparable_reasons","comparability_status","comparison_baseline_session_id","protocol_deviation_reasons","protocol_deviations","duration_seconds","device_and_environment","administration_mode","score_unit","missing_items","total_result","subscale_results","raw_item_results","qualification_note","administrator_role","administered_by_user_id","assessment_stage","localization_version","language_locale","instrument_version","instrument_name"]: op.drop_column("assessment_sessions", name)
