"""add isolated policy validation failures
Revision ID: 0037_policy_validation_failures
Revises: 0036_policy_validation
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
revision="0037_policy_validation_failures";down_revision="0036_policy_validation";branch_labels=None;depends_on=None
def upgrade():op.create_table("policy_validation_failures",sa.Column("id",postgresql.UUID(as_uuid=True),primary_key=True),sa.Column("dataset_id",postgresql.UUID(as_uuid=True),sa.ForeignKey("policy_validation_datasets.id",ondelete="RESTRICT"),nullable=False),sa.Column("input_fingerprint",sa.String(64),nullable=False),sa.Column("failure_stage",sa.String(80),nullable=False),sa.Column("error_code",sa.String(80),nullable=False),sa.Column("retry_required",sa.Boolean(),nullable=False),sa.Column("retry_count",sa.Integer(),nullable=False),sa.Column("created_at",sa.DateTime(timezone=True),nullable=False),sa.Column("updated_at",sa.DateTime(timezone=True),nullable=False),sa.UniqueConstraint("dataset_id","input_fingerprint",name="uq_policy_validation_failure"))
def downgrade():op.drop_table("policy_validation_failures")
