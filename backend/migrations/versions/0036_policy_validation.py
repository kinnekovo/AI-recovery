"""add Policy V2 validation evidence tables
Revision ID: 0036_policy_validation
Revises: 0035_policy_shadow_guard
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
revision="0036_policy_validation";down_revision="0035_policy_shadow_guard";branch_labels=None;depends_on=None
U=postgresql.UUID(as_uuid=True);J=sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()),"postgresql")
def upgrade():
 op.create_table("policy_validation_datasets",sa.Column("id",U,primary_key=True),sa.Column("name",sa.String(160),nullable=False),sa.Column("version",sa.String(64),nullable=False),sa.Column("status",sa.String(16),nullable=False),sa.Column("created_by_user_id",U,sa.ForeignKey("users.id"),nullable=False),sa.Column("created_at",sa.DateTime(timezone=True),nullable=False),sa.Column("updated_at",sa.DateTime(timezone=True),nullable=False),sa.UniqueConstraint("name","version",name="uq_policy_validation_dataset"))
 op.create_table("policy_validation_dataset_items",sa.Column("id",U,primary_key=True),sa.Column("dataset_id",U,sa.ForeignKey("policy_validation_datasets.id",ondelete="RESTRICT"),nullable=False),sa.Column("policy_decision_id",U,sa.ForeignKey("policy_decisions.id",ondelete="RESTRICT"),nullable=False),sa.Column("snapshot",J,nullable=False),sa.UniqueConstraint("dataset_id","policy_decision_id",name="uq_policy_validation_item"))
 op.create_table("policy_validation_runs",sa.Column("id",U,primary_key=True),sa.Column("dataset_id",U,sa.ForeignKey("policy_validation_datasets.id",ondelete="RESTRICT"),nullable=False),sa.Column("policy_version",sa.String(64),nullable=False),sa.Column("rules_version",sa.String(64),nullable=False),sa.Column("validation_policy_version",sa.String(64),nullable=False),sa.Column("input_fingerprint",sa.String(64),nullable=False),sa.Column("report",J,nullable=False),sa.Column("promotion_status",sa.String(48),nullable=False),sa.Column("reason_codes",J,nullable=False))
 op.create_table("policy_validation_registry",sa.Column("id",U,primary_key=True),sa.Column("policy_version",sa.String(64),nullable=False),sa.Column("rules_version",sa.String(64),nullable=False),sa.Column("validation_status",sa.String(48),nullable=False),sa.Column("latest_validation_run_id",U,sa.ForeignKey("policy_validation_runs.id",ondelete="RESTRICT")),sa.Column("status_reason_codes",J,nullable=False),sa.Column("created_at",sa.DateTime(timezone=True),nullable=False),sa.Column("updated_at",sa.DateTime(timezone=True),nullable=False),sa.UniqueConstraint("policy_version","rules_version",name="uq_policy_validation_registry"))
def downgrade():
 op.drop_table("policy_validation_registry");op.drop_table("policy_validation_runs");op.drop_table("policy_validation_dataset_items");op.drop_table("policy_validation_datasets")
