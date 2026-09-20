"""Seed a safe Product Reset v1 demonstration dataset.

Synthetic measurements are explicitly tagged ``source_status=mock`` and are
not decision eligible. They therefore cannot enter formal progress trends,
clinical observations, attention triggers, StageReview facts, or plan decisions.
"""

import argparse
import json
import sys
from datetime import date, timedelta
from pathlib import Path

from sqlalchemy import select

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.database.base import utc_now
from app.database.session import SessionLocal
from app.modules.assessment.model import AssessmentReviewStatus, AssessmentSession, AssessmentType
from app.modules.evaluations.model import EvaluationSource
from app.modules.product_v2.model import (
    AttentionItem,
    EvidenceRecord,
    MetricRecord,
    Milestone,
    RehabilitationGoal,
    StageReview,
    TrainingPlanExerciseRule,
    TrainingPlanVersion,
)
from app.modules.training.model import SessionTask, TaskTemplate, TrainingSession, TrainingStatus, TrainingType
from app.modules.training.service import ensure_seed_tasks
from app.modules.users.model import OnboardingStatus, PatientProfile, TherapistPatientAssignment, User, UserRole


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed Product Reset v1 demo data.")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if args.dry_run:
        print(json.dumps({"demo_only": True, "therapist": "trial_therapist_01", "patients": ["trial_patient_01", "trial_patient_02"], "source_status": "mock", "formal_trend_eligible": False}, ensure_ascii=False, indent=2))
        return 0

    with SessionLocal() as db:
        therapist = db.scalar(select(User).where(User.username == "trial_therapist_01", User.role == UserRole.therapist))
        patients = list(db.scalars(select(User).where(User.username.in_(["trial_patient_01", "trial_patient_02"]), User.role == UserRole.patient).order_by(User.username)))
        if not therapist or len(patients) != 2:
            raise SystemExit("Run `python scripts/init_trial_data.py --patient-count 2` first.")
        ensure_seed_tasks(db)
        templates = list(db.scalars(select(TaskTemplate).where(TaskTemplate.is_active.is_(True)).order_by(TaskTemplate.created_at)))
        repeat = next((item for item in templates if item.task_type == TrainingType.repeat), None)
        scenario = next((item for item in templates if item.task_type == TrainingType.scenario), None)
        if not repeat or not scenario:
            raise SystemExit("Repeat and scenario task templates are required.")
        profiles = [db.scalar(select(PatientProfile).where(PatientProfile.user_id == patient.id)) for patient in patients]
        for profile in profiles:
            _ensure_assignment(db, therapist, profile)
        plan_a = _ensure_goal_plan(db, therapist, profiles[0], repeat, scenario, "在日常点餐中完整表达需求")
        plan_b = _ensure_goal_plan(db, therapist, profiles[1], repeat, scenario, "在社区场景中主动表达并回应追问")
        session_a = _ensure_completed_session(db, profiles[0], plan_a, repeat, days_ago=2)
        session_b = _ensure_completed_session(db, profiles[0], plan_a, repeat, days_ago=1)
        _ensure_mock_metric(db, profiles[0], session_a, 72.0, "demo-repeat-v1")
        _ensure_mock_metric(db, profiles[0], session_b, 78.0, "demo-repeat-v1")
        _ensure_milestone(db, profiles[0], session_b)
        _ensure_completed_session(db, profiles[1], plan_b, scenario, days_ago=1)
        _ensure_attention(db, profiles[1])
        assessment = _ensure_assessment(db, therapist, profiles[1])
        _ensure_stage_review(db, therapist, profiles[1], plan_b, assessment)
        db.commit()
        print(json.dumps({"demo_only": True, "source_status": "mock", "therapist": therapist.username, "patients": [item.username for item in patients], "formal_trend_eligible": False}, ensure_ascii=False, indent=2))
    return 0


def _ensure_assignment(db, therapist, profile):
    # Trial users must enter the Product v2 shell in the same ready state as a
    # patient who completed the legacy agent-selection onboarding.  Without
    # this, a valid formal plan is hidden behind the legacy onboarding gate.
    profile.onboarding_status = OnboardingStatus.ready
    row = db.scalar(select(TherapistPatientAssignment).where(TherapistPatientAssignment.therapist_user_id == therapist.id, TherapistPatientAssignment.patient_profile_id == profile.id))
    if not row:
        db.add(TherapistPatientAssignment(therapist_user_id=therapist.id, patient_profile_id=profile.id, status="active"))


def _ensure_goal_plan(db, therapist, profile, repeat, scenario, description):
    goal = db.scalar(select(RehabilitationGoal).where(RehabilitationGoal.patient_profile_id == profile.id, RehabilitationGoal.status == "active"))
    if not goal:
        goal = RehabilitationGoal(patient_profile_id=profile.id, created_by_user_id=therapist.id, category="functional_communication", description=description, status="active", is_primary=True, effective_from=date.today())
        db.add(goal); db.flush()
    plan = db.scalar(select(TrainingPlanVersion).where(TrainingPlanVersion.patient_profile_id == profile.id, TrainingPlanVersion.status == "active"))
    if not plan:
        plan = TrainingPlanVersion(patient_profile_id=profile.id, rehabilitation_goal_id=goal.id, version_number=1, status="active", stage_focus="完整表达与独立沟通", strategy_snapshot={"frequency":"daily","duration":15,"forms":["repeat","scenario"],"difficulty":"supported","prompt_policy":{"levels":3}}, effective_from=date.today(), published_by_user_id=therapist.id, published_at=utc_now())
        db.add(plan); db.flush()
        for index, template in enumerate((repeat, scenario)):
            db.add(TrainingPlanExerciseRule(training_plan_version_id=plan.id, task_template_id=template.id, exercise_type=template.task_type.value, order_index=index, target_repetitions=1, difficulty="supported", max_information_units=3, prompt_policy={"levels":3}, scene_scope={"demo_only":True}))
    return plan


def _ensure_completed_session(db, profile, plan, template, days_ago):
    day = date.today() - timedelta(days=days_ago)
    row = db.scalar(select(TrainingSession).where(TrainingSession.patient_profile_id == profile.id, TrainingSession.formal_training_plan_version_id == plan.id, TrainingSession.local_session_date == day))
    if row: return row
    row = TrainingSession(patient_profile_id=profile.id, formal_training_plan_version_id=plan.id, session_kind="formal", v2_status="completed", local_session_date=day, started_at=utc_now(), completed_at=utc_now(), summary_status="ready", technical_status="ready", training_type=template.task_type, status=TrainingStatus.completed)
    db.add(row); db.flush()
    db.add(SessionTask(training_session_id=row.id, task_template_id=template.id, order_index=0, prompt_level=0, status=TrainingStatus.completed, v2_status="completed", content_snapshot={"title":template.title,"demo_only":True}, instruction_snapshot=template.instruction, target_snapshot=template.target_text, exercise_type_snapshot=template.task_type.value, difficulty_snapshot="supported", prompt_policy_snapshot={"levels":3}, contract_version_snapshot="demo-v1"))
    return row


def _ensure_mock_metric(db, profile, session, value, comparison_key):
    if db.scalar(select(MetricRecord).where(MetricRecord.source_type == "demo", MetricRecord.source_id == session.id, MetricRecord.code == "script_accuracy")): return
    evidence = EvidenceRecord(patient_profile_id=profile.id, training_session_id=session.id, evidence_type="demo_seed", source_type="demo", source_id=session.id, source_status="mock", provider="demo_seed", provider_version="v1", quality_status="synthetic", payload={"label":"演示数据"}, measured_at=session.completed_at)
    db.add(evidence); db.flush()
    db.add(MetricRecord(patient_profile_id=profile.id, training_session_id=session.id, code="script_accuracy", value=value, status="measured", unit="%", measured_at=session.completed_at, measurement_context={"task_family":"repeat","demo_only":True}, source_type="demo", source_id=session.id, provider="demo_seed", algorithm="demo-v1", version="v1", quality={"source_status":"mock","label":"演示数据"}, evidence_ids=[str(evidence.id)], comparison_key=comparison_key, decision_eligible=False))


def _ensure_milestone(db, profile, session):
    if not db.scalar(select(Milestone).where(Milestone.patient_profile_id == profile.id, Milestone.dedup_key == "demo-first-independent")):
        db.add(Milestone(patient_profile_id=profile.id, code="demo_first_independent", title="演示：第一次独立完成", description="此里程碑仅用于演示界面，不进入正式临床决策。", dedup_key="demo-first-independent", trigger_facts={"session_id":str(session.id),"source_status":"mock"}, evidence_ids=[]))


def _ensure_attention(db, profile):
    if not db.scalar(select(AttentionItem).where(AttentionItem.patient_profile_id == profile.id, AttentionItem.dedup_key == "demo-help")):
        db.add(AttentionItem(patient_profile_id=profile.id, item_type="patient_help_request", trigger_code="demo_explicit_help", trigger_facts={"source_status":"mock"}, source_refs=[], evidence_ids=[], dedup_key="demo-help", priority="normal", summary="演示事项：患者在场景表达中请求治疗师帮助。", status="open"))


def _ensure_assessment(db, therapist, profile):
    row = db.scalar(select(AssessmentSession).where(AssessmentSession.patient_profile_id == profile.id, AssessmentSession.instrument_name == "DEMO-CADL"))
    if row: return row
    row = AssessmentSession(patient_profile_id=profile.id, assessment_type=AssessmentType.during, evaluation_source=EvaluationSource.human, review_status=AssessmentReviewStatus.confirmed.value, reviewed_by_user_id=therapist.id, reviewed_at=utc_now(), assessed_at=utc_now(), metrics={"cadl_score":None}, notes="演示用正式评估结构；没有伪造分数。", therapist_notes="demo-only", instrument_name="DEMO-CADL", instrument_version="v1", language_locale="zh-CN", assessment_stage="formal", administered_by_user_id=therapist.id, administrator_role="therapist", raw_item_results={}, subscale_results={}, total_result={}, missing_items=["all"], score_unit="points", administration_mode="in_person", protocol_deviations={}, protocol_deviation_reasons=[])
    db.add(row); db.flush(); return row


def _ensure_stage_review(db, therapist, profile, plan, assessment):
    if not db.scalar(select(StageReview).where(StageReview.patient_profile_id == profile.id)):
        db.add(StageReview(patient_profile_id=profile.id, training_plan_version_id=plan.id, created_by_user_id=therapist.id, status="draft", review_window={"demo_only":True}, facts_snapshot={"source_status":"mock","metrics":[],"trends":[]}, observation_ids=[], recommendation_ids=[], attention_item_ids=[], assessment_ids=[str(assessment.id)], clinical_stage_run_ids=[], therapist_notes="演示草稿；不包含临床结论。"))


if __name__ == "__main__":
    raise SystemExit(main())
