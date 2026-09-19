"""add immutable canonical evaluation-run foundation

Revision ID: 0027_evaluation_runs_v3
Revises: 0026_r0_algorithm_safety
Create Date: 2026-09-19
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0027_evaluation_runs_v3"
down_revision = "0026_r0_algorithm_safety"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "evaluation_runs",
        sa.Column("patient_profile_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("patient_profiles.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("domain", sa.String(length=40), nullable=False),
        sa.Column("source_type", sa.String(length=40), nullable=False),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("algorithm_version", sa.String(length=120), nullable=False),
        sa.Column("config_snapshot", postgresql.JSONB(), nullable=False),
        sa.Column("input_provenance", postgresql.JSONB(), nullable=False),
        sa.Column("quality_gate", postgresql.JSONB(), nullable=False),
        sa.Column("result_status", sa.String(length=32), nullable=False),
        sa.Column("profile_eligibility", sa.Boolean(), nullable=False),
        sa.Column("profile_ineligibility_reasons", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("limitations", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("adoption_status", sa.String(length=20), nullable=False, server_default="candidate"),
        sa.Column("supersedes_run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("evaluation_runs.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("domain IN ('repeat', 'functional_communication', 'clinical_stage')", name="ck_evaluation_runs_domain"),
        sa.CheckConstraint("source_type IN ('attempt', 'dialogue_session', 'assessment_session')", name="ck_evaluation_runs_source_type"),
        sa.CheckConstraint("result_status IN ('formal', 'provisional', 'review_required', 'unscorable')", name="ck_evaluation_runs_result_status"),
        sa.CheckConstraint("adoption_status IN ('candidate', 'adopted', 'superseded')", name="ck_evaluation_runs_adoption_status"),
    )
    op.create_index("ix_evaluation_runs_patient_profile_id", "evaluation_runs", ["patient_profile_id"])
    op.create_index("ix_evaluation_runs_source_domain", "evaluation_runs", ["source_type", "source_id", "domain"])
    op.create_index(
        "uq_evaluation_runs_one_adopted_source_domain",
        "evaluation_runs",
        ["source_type", "source_id", "domain"],
        unique=True,
        postgresql_where=sa.text("adoption_status = 'adopted'"),
    )

    op.create_table(
        "evaluation_dimension_results",
        sa.Column("evaluation_run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("evaluation_runs.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("dimension_code", sa.String(length=100), nullable=False),
        sa.Column("value", sa.Float(), nullable=True),
        sa.Column("level", sa.String(length=80), nullable=True),
        sa.Column("unit", sa.String(length=40), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("measurement_quality", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("evidence_snapshot", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("limitations", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("evaluation_run_id", "dimension_code", name="uq_evaluation_dimension_run_code"),
        sa.CheckConstraint("status IN ('measured', 'not_observed', 'unavailable', 'not_applicable')", name="ck_evaluation_dimension_results_status"),
    )
    op.create_index("ix_evaluation_dimension_results_evaluation_run_id", "evaluation_dimension_results", ["evaluation_run_id"])
    op.create_index("ix_evaluation_dimension_results_run_dimension", "evaluation_dimension_results", ["evaluation_run_id", "dimension_code"])

    op.create_table(
        "evaluation_review_revisions",
        sa.Column("evaluation_run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("evaluation_runs.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("dimension_result_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("evaluation_dimension_results.id", ondelete="SET NULL"), nullable=True),
        sa.Column("review_action", sa.String(length=32), nullable=False),
        sa.Column("automatic_value_snapshot", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("revised_value_snapshot", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("evidence_override", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("reviewer_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("recomputed_run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("evaluation_runs.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("review_action IN ('confirmed', 'corrected', 'unjudgeable')", name="ck_evaluation_review_revisions_action"),
    )
    op.create_index("ix_evaluation_review_revisions_evaluation_run_id", "evaluation_review_revisions", ["evaluation_run_id"])

    # Algorithm payloads and dimension rows are append-only.  The sole permitted
    # run mutation is the audited candidate->adopted / adopted->superseded state
    # transition performed by the transactional adoption service.
    op.execute(
        """
        CREATE FUNCTION protect_evaluation_run_immutability() RETURNS trigger AS $$
        BEGIN
            IF TG_OP = 'DELETE' THEN
                RAISE EXCEPTION 'evaluation_runs are append-only';
            END IF;
            IF NEW.patient_profile_id IS DISTINCT FROM OLD.patient_profile_id
               OR NEW.domain IS DISTINCT FROM OLD.domain
               OR NEW.source_type IS DISTINCT FROM OLD.source_type
               OR NEW.source_id IS DISTINCT FROM OLD.source_id
               OR NEW.algorithm_version IS DISTINCT FROM OLD.algorithm_version
               OR NEW.config_snapshot IS DISTINCT FROM OLD.config_snapshot
               OR NEW.input_provenance IS DISTINCT FROM OLD.input_provenance
               OR NEW.quality_gate IS DISTINCT FROM OLD.quality_gate
               OR NEW.result_status IS DISTINCT FROM OLD.result_status
               OR NEW.profile_eligibility IS DISTINCT FROM OLD.profile_eligibility
               OR NEW.profile_ineligibility_reasons IS DISTINCT FROM OLD.profile_ineligibility_reasons
               OR NEW.limitations IS DISTINCT FROM OLD.limitations THEN
                RAISE EXCEPTION 'evaluation run result payload is immutable';
            END IF;
            IF OLD.adoption_status = 'candidate' AND NEW.adoption_status = 'adopted' THEN
                RETURN NEW;
            ELSIF OLD.adoption_status = 'adopted' AND NEW.adoption_status = 'superseded'
                  AND NEW.supersedes_run_id IS NOT DISTINCT FROM OLD.supersedes_run_id THEN
                RETURN NEW;
            END IF;
            RAISE EXCEPTION 'invalid evaluation run adoption transition';
        END;
        $$ LANGUAGE plpgsql;
        CREATE TRIGGER trg_protect_evaluation_runs
        BEFORE UPDATE OR DELETE ON evaluation_runs
        FOR EACH ROW EXECUTE FUNCTION protect_evaluation_run_immutability();

        CREATE FUNCTION prevent_evaluation_child_mutation() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'evaluation result audit rows are append-only';
        END;
        $$ LANGUAGE plpgsql;
        CREATE TRIGGER trg_protect_evaluation_dimension_results
        BEFORE UPDATE OR DELETE ON evaluation_dimension_results
        FOR EACH ROW EXECUTE FUNCTION prevent_evaluation_child_mutation();
        CREATE TRIGGER trg_protect_evaluation_review_revisions
        BEFORE UPDATE OR DELETE ON evaluation_review_revisions
        FOR EACH ROW EXECUTE FUNCTION prevent_evaluation_child_mutation();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER trg_protect_evaluation_review_revisions ON evaluation_review_revisions")
    op.execute("DROP TRIGGER trg_protect_evaluation_dimension_results ON evaluation_dimension_results")
    op.execute("DROP TRIGGER trg_protect_evaluation_runs ON evaluation_runs")
    op.execute("DROP FUNCTION prevent_evaluation_child_mutation()")
    op.execute("DROP FUNCTION protect_evaluation_run_immutability()")
    op.drop_index("ix_evaluation_review_revisions_evaluation_run_id", table_name="evaluation_review_revisions")
    op.drop_table("evaluation_review_revisions")
    op.drop_index("ix_evaluation_dimension_results_run_dimension", table_name="evaluation_dimension_results")
    op.drop_index("ix_evaluation_dimension_results_evaluation_run_id", table_name="evaluation_dimension_results")
    op.drop_table("evaluation_dimension_results")
    op.drop_index("uq_evaluation_runs_one_adopted_source_domain", table_name="evaluation_runs")
    op.drop_index("ix_evaluation_runs_source_domain", table_name="evaluation_runs")
    op.drop_index("ix_evaluation_runs_patient_profile_id", table_name="evaluation_runs")
    op.drop_table("evaluation_runs")
