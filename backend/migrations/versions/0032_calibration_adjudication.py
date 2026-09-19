"""add calibration annotation adjudication marker
Revision ID: 0032_calibration_adjudication
Revises: 0031_calibration_promotion
"""
from alembic import op
import sqlalchemy as sa
revision="0032_calibration_adjudication";down_revision="0031_calibration_promotion";branch_labels=None;depends_on=None
def upgrade():op.add_column("reference_annotations",sa.Column("is_adjudicated",sa.Boolean(),nullable=False,server_default=sa.false()))
def downgrade():op.drop_column("reference_annotations","is_adjudicated")
