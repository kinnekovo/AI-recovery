"""therapist patient assignments

Revision ID: 0012_therapist_assign
Revises: 0011_agent_voice_clone
Create Date: 2026-09-03
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0012_therapist_assign"
down_revision = "0011_agent_voice_clone"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "therapist_patient_assignments",
        sa.Column("therapist_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("patient_profile_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="active"),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["patient_profile_id"], ["patient_profiles.id"]),
        sa.ForeignKeyConstraint(["therapist_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("therapist_user_id", "patient_profile_id", name="uq_therapist_patient_assignment"),
    )
    op.create_index(
        op.f("ix_therapist_patient_assignments_patient_profile_id"),
        "therapist_patient_assignments",
        ["patient_profile_id"],
    )
    op.create_index(
        op.f("ix_therapist_patient_assignments_therapist_user_id"),
        "therapist_patient_assignments",
        ["therapist_user_id"],
    )
    op.execute(
        """
        INSERT INTO therapist_patient_assignments (
            therapist_user_id,
            patient_profile_id,
            status,
            id,
            created_at,
            updated_at
        )
        SELECT therapist_user.id, patient_profiles.id, 'active', gen_random_uuid(), now(), now()
        FROM users AS therapist_user
        CROSS JOIN patient_profiles
        WHERE therapist_user.role = 'therapist'
        ON CONFLICT ON CONSTRAINT uq_therapist_patient_assignment DO NOTHING
        """
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_therapist_patient_assignments_therapist_user_id"), table_name="therapist_patient_assignments")
    op.drop_index(op.f("ix_therapist_patient_assignments_patient_profile_id"), table_name="therapist_patient_assignments")
    op.drop_table("therapist_patient_assignments")
