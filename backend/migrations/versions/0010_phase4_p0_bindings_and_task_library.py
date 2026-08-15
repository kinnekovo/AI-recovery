"""phase4 p0 family bindings and task library

Revision ID: 0010_phase4_p0
Revises: 0009_phase3_close
Create Date: 2026-08-13
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0010_phase4_p0"
down_revision = "0009_phase3_close"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "family_patient_bindings",
        sa.Column("family_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("patient_profile_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("relationship_label", sa.String(length=40), nullable=False, server_default="家属"),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="active"),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["family_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["patient_profile_id"], ["patient_profiles.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("family_user_id", "patient_profile_id", name="uq_family_patient_binding"),
    )
    op.create_index(op.f("ix_family_patient_bindings_family_user_id"), "family_patient_bindings", ["family_user_id"])
    op.create_index(op.f("ix_family_patient_bindings_patient_profile_id"), "family_patient_bindings", ["patient_profile_id"])

    op.add_column("task_templates", sa.Column("tags", postgresql.JSONB(), nullable=False, server_default="[]"))
    op.add_column("task_templates", sa.Column("recommendation_weight", sa.Integer(), nullable=False, server_default="50"))
    op.add_column("task_templates", sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()))

    op.execute(
        """
        INSERT INTO family_patient_bindings (
            family_user_id,
            patient_profile_id,
            relationship_label,
            status,
            id,
            created_at,
            updated_at
        )
        SELECT family_user.id, first_profile.id, '家属', 'active', gen_random_uuid(), now(), now()
        FROM users AS family_user
        CROSS JOIN LATERAL (
            SELECT patient_profiles.id
            FROM patient_profiles
            JOIN users AS patient_user ON patient_user.id = patient_profiles.user_id
            WHERE patient_user.role = 'patient'
            ORDER BY patient_user.created_at ASC
            LIMIT 1
        ) AS first_profile
        WHERE family_user.role = 'family'
        ON CONFLICT ON CONSTRAINT uq_family_patient_binding DO NOTHING
        """
    )


def downgrade() -> None:
    op.drop_column("task_templates", "is_active")
    op.drop_column("task_templates", "recommendation_weight")
    op.drop_column("task_templates", "tags")
    op.drop_index(op.f("ix_family_patient_bindings_patient_profile_id"), table_name="family_patient_bindings")
    op.drop_index(op.f("ix_family_patient_bindings_family_user_id"), table_name="family_patient_bindings")
    op.drop_table("family_patient_bindings")
