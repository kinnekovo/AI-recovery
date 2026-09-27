from datetime import date, datetime, timezone
from uuid import UUID

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.base import Base, import_models
from app.modules.attempts.model import AnalysisStatus, Attempt
from app.modules.assessment.model import AssessmentSession
from app.modules.product_v2 import service
from app.modules.product_v2.model import AttentionItem, EvidenceRecord, MetricRecord, TherapistDecision, TrainingPlanVersion
from app.modules.pronunciation.model import PronunciationAnalysisResult, PronunciationSegment
from app.modules.scenario_dialogues import service as scenario_service
from app.modules.product_v2.schema import (
    DecisionCreate,
    ExerciseRuleCreate,
    FormalAssessmentCreate,
    GoalCreate,
    StageReviewCreate,
    TrainingPlanDraftCreate,
)
from app.modules.scoring.model import AttemptAnalysisResult
from app.modules.training.model import SessionTask, TaskTemplate, TrainingType
from app.modules.users.model import OnboardingStatus, PatientProfile, TherapistPatientAssignment, User, UserRole


@compiles(JSONB, "sqlite")
def _jsonb_sqlite(_type, _compiler, **_kwargs):
    return "JSON"


@pytest.fixture()
def product_db():
    import_models()
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    with SessionLocal() as db:
        therapist = User(username="v2-therapist", password_hash="x", role=UserRole.therapist)
        patient = User(username="v2-patient", password_hash="x", role=UserRole.patient)
        stranger = User(username="v2-stranger", password_hash="x", role=UserRole.therapist)
        db.add_all([therapist, patient, stranger]); db.flush()
        profile = PatientProfile(user_id=patient.id, onboarding_status=OnboardingStatus.ready, timezone="Asia/Shanghai")
        db.add(profile); db.flush()
        db.add(TherapistPatientAssignment(therapist_user_id=therapist.id, patient_profile_id=profile.id, status="active"))
        repeat = TaskTemplate(task_type=TrainingType.repeat, title="复述", instruction="请复述", target_text="我要一杯水", scoring_config={"version": "repeat-v1"})
        scenario = TaskTemplate(
            task_type=TrainingType.scenario,
            title="点餐",
            instruction="完成点餐",
            target_text="表达需求",
            scene_prompt="你在餐厅",
            scoring_config={
                "mode": "functional_scenario",
                "version": "scenario-v1",
                "goal_requirements": ["need"],
                "required_information_units": [
                    {"id": "need", "label": "饮水需求", "keywords": ["水"]}
                ],
                "minimum_patient_turns": 1,
                "maximum_patient_turns": 3,
            },
        )
        db.add_all([repeat, scenario]); db.commit()
        yield db, therapist, patient, stranger, profile, repeat, scenario
    engine.dispose()


def create_active_plan(db, therapist, patient, repeat, scenario):
    goal = service.create_goal(db, therapist, patient.id, GoalCreate(category="functional", description="在点餐中完整表达"))
    plan = service.create_plan_draft(
        db,
        therapist,
        patient.id,
        TrainingPlanDraftCreate(
            rehabilitation_goal_id=UUID(goal["id"]),
            stage_focus="完整表达",
            forms=["repeat", "scenario"],
            exercise_rules=[
                ExerciseRuleCreate(task_template_id=repeat.id, exercise_type="repeat", order_index=0),
                ExerciseRuleCreate(task_template_id=scenario.id, exercise_type="scenario", order_index=1),
            ],
        ),
    )
    return goal, service.publish_plan(db, therapist, patient.id, UUID(plan["id"]))


def test_goal_plan_version_publish_and_single_active_plan(product_db):
    db, therapist, patient, _, profile, repeat, scenario = product_db
    goal, first = create_active_plan(db, therapist, patient, repeat, scenario)
    assert first["status"] == "active"
    assert [rule["exercise_type"] for rule in first["exercise_rules"]] == ["repeat", "scenario"]
    second = service.create_plan_draft(db, therapist, patient.id, TrainingPlanDraftCreate(
        rehabilitation_goal_id=UUID(goal["id"]), stage_focus="更独立地表达", supersedes_id=UUID(first["id"]),
        exercise_rules=[ExerciseRuleCreate(task_template_id=repeat.id, exercise_type="repeat", order_index=0)],
    ))
    second = service.publish_plan(db, therapist, patient.id, UUID(second["id"]))
    old = db.get(TrainingPlanVersion, UUID(first["id"]))
    assert second["version_number"] == 2
    assert old.status == "superseded"
    assert db.scalar(select(TrainingPlanVersion).where(TrainingPlanVersion.patient_profile_id == profile.id, TrainingPlanVersion.status == "active")).id == UUID(second["id"])


def test_patient_home_canonical_states(product_db):
    db, therapist, patient, _, profile, repeat, scenario = product_db
    waiting = service.patient_home(db, patient)
    assert waiting["state"] == "waiting_for_plan"
    assert waiting["today_session"] is None
    assert waiting["primary_action"] is None

    profile.onboarding_status = OnboardingStatus.pending_agent
    db.commit()
    assert service.patient_home(db, patient)["state"] == "onboarding_required"

    profile.onboarding_status = OnboardingStatus.ready
    db.commit()
    create_active_plan(db, therapist, patient, repeat, scenario)
    assert service.patient_home(db, patient)["state"] == "ready_to_train"

    session = service.start_or_resume(db, patient, "formal", None)
    assert service.patient_home(db, patient)["state"] == "in_progress"
    service.session_command(db, patient, UUID(session["id"]), "pause")
    assert service.patient_home(db, patient)["state"] == "paused"
    service.session_command(db, patient, UUID(session["id"]), "resume")
    for exercise in session["exercises"]:
        service.task_command(db, patient, UUID(session["id"]), UUID(exercise["id"]), "skip")
    service.session_command(db, patient, UUID(session["id"]), "complete")
    completed = service.patient_home(db, patient)
    assert completed["state"] == "completed"
    assert completed["primary_action"]["action"] == "view_summary"


def test_patient_home_plan_update_and_stage_review_states(product_db):
    db, therapist, patient, _, _, repeat, scenario = product_db
    goal, active = create_active_plan(db, therapist, patient, repeat, scenario)
    session = service.start_or_resume(db, patient, "formal", None)
    draft = service.create_plan_draft(
        db,
        therapist,
        patient.id,
        TrainingPlanDraftCreate(
            rehabilitation_goal_id=UUID(goal["id"]),
            stage_focus="新阶段重点",
            supersedes_id=UUID(active["id"]),
            exercise_rules=[
                ExerciseRuleCreate(task_template_id=repeat.id, exercise_type="repeat", order_index=0)
            ],
        ),
    )
    service.publish_plan(db, therapist, patient.id, UUID(draft["id"]))
    updated = service.patient_home(db, patient)
    assert updated["state"] == "plan_updated"
    assert updated["today_session"]["id"] == session["id"]
    assert updated["primary_action"]["action"] == "resume_session"

    # A draft StageReview is surfaced when there is no current daily session,
    # without preventing the patient from starting the active plan.
    for exercise in session["exercises"]:
        service.task_command(db, patient, UUID(session["id"]), UUID(exercise["id"]), "skip")
    service.session_command(db, patient, UUID(session["id"]), "complete")
    service.create_stage_review(db, therapist, patient.id, StageReviewCreate())
    pending = service.patient_home(db, patient)
    assert pending["state"] == "stage_review_pending"
    assert pending["primary_action"]["action"] == "start_session"


def test_start_resume_timezone_formal_extra_and_state_machine(product_db):
    db, therapist, patient, _, _, repeat, scenario = product_db
    _, plan = create_active_plan(db, therapist, patient, repeat, scenario)
    first = service.start_or_resume(db, patient, "formal", None)
    resumed = service.start_or_resume(db, patient, "formal", None)
    extra = service.start_or_resume(db, patient, "extra_practice", UUID(plan["id"]))
    assert first["id"] == resumed["id"]
    assert first["local_session_date"] == date.today().isoformat()
    assert extra["id"] != first["id"] and extra["session_kind"] == "extra_practice"
    progress = service.patient_progress(db, patient)
    independence = next(item for item in progress["comparable_trends"] if item["code"] == "independence")
    assert independence["label"] == "独立完成度"
    paused = service.session_command(db, patient, UUID(first["id"]), "pause")
    assert paused["status"] == "paused"
    assert service.session_command(db, patient, UUID(first["id"]), "resume")["status"] == "in_progress"
    for exercise in first["exercises"]:
        service.task_command(db, patient, UUID(first["id"]), UUID(exercise["id"]), "skip")
    completed = service.session_command(db, patient, UUID(first["id"]), "complete")
    assert completed["status"] == "completed"
    summary = service.session_summary(db, patient, UUID(first["id"]))
    assert summary["facts"]["skipped_exercises"] == 2


def test_daily_plan_is_stable_and_extra_pool_is_separate(product_db):
    db, therapist, patient, _, _, repeat, scenario = product_db
    create_active_plan(db, therapist, patient, repeat, scenario)
    first_home = service.patient_home(db, patient)
    second_home = service.patient_home(db, patient)
    assert first_home["daily_plan"]["id"] == second_home["daily_plan"]["id"]
    assert first_home["daily_plan"]["estimated_duration_seconds"] <= 600
    assert len(first_home["extra_practice"]["repeat"]) == 10
    assert len(first_home["extra_practice"]["scenario"]) == 3
    extra = service.start_or_resume(db, patient, "extra_practice", None, [repeat.id])
    assert extra["session_kind"] == "extra_practice"
    assert len(extra["exercises"]) == 1


def test_attention_dedup_resolution_and_assignment_authorization(product_db):
    db, therapist, patient, stranger, profile, repeat, scenario = product_db
    _, _ = create_active_plan(db, therapist, patient, repeat, scenario)
    first = service.create_attention(db, profile.id, "help", "explicit", "需要帮助", "same-key", [], priority="normal")
    second = service.create_attention(db, profile.id, "help", "explicit", "需要帮助", "same-key", [], priority="normal")
    db.commit()
    assert first.id == second.id
    with pytest.raises(HTTPException) as exc:
        service.set_attention_status(db, stranger, first.id, "acknowledged")
    assert exc.value.status_code == 403
    acknowledged = service.set_attention_status(db, therapist, first.id, "acknowledged")
    assert acknowledged["status"] == "acknowledged"
    assert service.set_attention_status(db, therapist, first.id, "resolved", "已复核")["status"] == "resolved"


def test_completed_scenario_materializes_evidence_and_metrics(product_db, monkeypatch):
    db, therapist, patient, _, _, repeat, scenario = product_db
    monkeypatch.setattr(
        "app.integrations.llm.scenario_semantics.extract_evidence",
        lambda *_args, **_kwargs: None,
    )
    create_active_plan(db, therapist, patient, repeat, scenario)
    session = service.start_or_resume(db, patient, "formal", None)
    scenario_task = next(item for item in session["exercises"] if item["exercise_type"] == "scenario")
    dialogue = scenario_service.create_dialogue(db, patient, UUID(scenario_task["id"]))
    completed = scenario_service.add_patient_turn(db, patient, dialogue.id, "我要一杯水")
    assert completed.status == "completed"

    refreshed = service.get_patient_session(db, patient, UUID(session["id"]))
    projected_task = next(item for item in refreshed["exercises"] if item["exercise_type"] == "scenario")
    assert projected_task["status"] == "completed"
    assert db.scalar(
        select(EvidenceRecord).where(EvidenceRecord.source_type == "scenario_dialogue")
    ) is not None
    metrics = list(
        db.scalars(select(MetricRecord).where(MetricRecord.source_type == "scenario_dialogue"))
    )
    assert {item.code for item in metrics} >= {
        "functional_goal",
        "information_units",
        "response_effectiveness",
        "relevance_and_organization",
        "independence",
        "repair_ability",
    }


def test_completed_tencent_soe_repeat_projects_evidence_and_metrics(product_db):
    db, therapist, patient, _, _, repeat, scenario = product_db
    create_active_plan(db, therapist, patient, repeat, scenario)
    session = service.start_or_resume(db, patient, "formal", None)
    task = db.get(SessionTask, UUID(session["exercises"][0]["id"]))
    attempt = Attempt(
        session_task_id=task.id,
        attempt_no=1,
        terminal_state="completed",
        technical_validity="valid",
        measurement_eligibility="eligible",
        completed_at=datetime.now(timezone.utc),
        audio_quality="pass",
        analysis_status=AnalysisStatus.completed,
    )
    db.add(attempt)
    db.flush()
    db.add(
        AttemptAnalysisResult(
            attempt_id=attempt.id,
            asr_text="我要一杯水",
            acoustic_metrics={},
            semantic_metrics={
                "asr_provider": "tencent",
                "asr_fallback_used": False,
                "process_monitoring": {
                    "details": {
                        "independence_score": 75,
                        "independence_evidence": {"prompt_level": 1, "requested_help": False, "start_latency_ms": 800},
                        "quality_status": "pass",
                        "loudness_unit": "dBFS",
                        "input_sources": {"asr_provider": "tencent", "acoustic_provider": "local"},
                        "evaluation_source": "system_rule",
                        "provider_version": "rehab-process-v2",
                    }
                },
            },
            raw_model_output={},
            provider_version="rehab-process-v2",
        )
    )
    analysis = PronunciationAnalysisResult(
        attempt_id=attempt.id,
        provider="tencent_soe",
        provider_version="soe-new-wss-v1",
        evaluation_mode="sentence",
        status="completed",
        overall_accuracy=91,
        fluency=0.86,
        completion=0.95,
        suggested_score=90,
        confidence=0.95,
        coverage=1.0,
        raw_provider_output={"PronAccuracy": 91},
    )
    db.add(analysis)
    db.flush()
    db.add_all(
        [
            PronunciationSegment(
                analysis_id=analysis.id,
                level="word",
                ordinal=0,
                match_type="substitution",
                accuracy=72,
                tone_correct=False,
            ),
            PronunciationSegment(
                analysis_id=analysis.id,
                level="word",
                ordinal=1,
                match_type="matched",
                accuracy=100,
                tone_correct=True,
            ),
            PronunciationSegment(
                analysis_id=analysis.id,
                level="phoneme",
                ordinal=0,
                match_type="matched",
                accuracy=80,
            ),
            PronunciationSegment(
                analysis_id=analysis.id,
                level="phoneme",
                ordinal=1,
                match_type="matched",
                accuracy=100,
            ),
        ]
    )
    db.commit()

    service.project_attempt(db, attempt.id)

    evidence = db.scalar(
        select(EvidenceRecord).where(
            EvidenceRecord.source_type == "attempt",
            EvidenceRecord.source_id == attempt.id,
            EvidenceRecord.evidence_type == "pronunciation_bundle",
        )
    )
    metrics = list(
        db.scalars(
            select(MetricRecord).where(
                MetricRecord.source_type.in_(["attempt", "attempt_pronunciation"]),
                MetricRecord.source_id == attempt.id,
            )
        )
    )
    assert evidence is not None
    assert evidence.provider == "tencent_soe"
    assert {item.code for item in metrics} == {
        "pronunciation_accuracy",
        "pronunciation_fluency",
        "pronunciation_completion",
        "phoneme_accuracy",
        "tone_accuracy",
        "pronunciation_mismatch_count",
        "independence",
    }
    assert all(item.decision_eligible is False for item in metrics if item.code != "independence")
    independence = next(item for item in metrics if item.code == "independence")
    assert independence.value == 75
    assert independence.decision_eligible is True


def test_stage_review_decision_creates_unpublished_plan_version(product_db, monkeypatch):
    db, therapist, patient, _, _, repeat, scenario = product_db
    _, plan = create_active_plan(db, therapist, patient, repeat, scenario)
    monkeypatch.setattr(
        "app.modules.evaluation_runs.clinical_stage_v3.write_clinical_stage_run",
        lambda *_: None,
    )
    service.create_formal_assessment(
        db,
        therapist,
        patient.id,
        FormalAssessmentCreate(
            instrument_name="CADL",
            instrument_version="zh-v1",
            score_unit="points",
            administration_mode="in_person",
            metrics={"cadl_score": 82},
        ),
    )
    review = service.create_stage_review(db, therapist, patient.id, StageReviewCreate(therapist_notes="阶段复核"))
    assert review["formal_assessments"][0]["instrument_name"] == "CADL"
    assert review["formal_assessments"][0]["measured_metrics"] == ["cadl_score"]
    decision = service.create_decision(db, therapist, UUID(review["id"]), DecisionCreate(decision_type="create_new_training_plan_version", reason="继续但调整重点", payload={"stage_focus": "减少提示"}))
    draft = db.get(TrainingPlanVersion, UUID(decision["resulting_training_plan_version_id"]))
    assert draft.status == "draft"
    assert draft.source_decision_id == UUID(decision["id"])
    assert db.get(TrainingPlanVersion, UUID(plan["id"])).status == "active"
    assert db.scalar(select(TherapistDecision).where(TherapistDecision.id == UUID(decision["id"]))) is not None


def test_formal_assessment_is_separate_and_never_accepts_wab_reliability(product_db, monkeypatch):
    db, therapist, patient, _, profile, repeat, scenario = product_db
    monkeypatch.setattr("app.modules.evaluation_runs.clinical_stage_v3.write_clinical_stage_run", lambda *_: None)
    result = service.create_formal_assessment(db, therapist, patient.id, FormalAssessmentCreate(
        instrument_name="CADL", instrument_version="zh-v1", score_unit="points", administration_mode="in_person",
        metrics={"cadl_score": 82, "wab_reliability": 99}, missing_items=["wab_reliability"],
    ))
    assert result["metrics"] == {"cadl_score": 82.0}
    assert result["unsupported_metrics"] == ["wab_reliability"]
    assert result["clinical_stage"] == "internal_shadow"

    # Legacy/imported assessment payloads can contain an explicit JSON null.
    # The professional panel must not render that as a measured value.
    assessment = db.scalar(
        select(AssessmentSession).where(AssessmentSession.patient_profile_id == profile.id)
    )
    assessment.metrics = {"cadl_score": None}
    db.commit()
    create_active_plan(db, therapist, patient, repeat, scenario)
    session = service.start_or_resume(db, patient, "formal", None)
    panel = service.professional_metric_panel(db, profile.id, UUID(session["id"]))
    assert "cadl_score" not in {item["code"] for item in panel}
    assert "wab_reliability" not in {item["code"] for item in panel}

    with pytest.raises(HTTPException) as exc:
        service.create_formal_assessment(
            db,
            therapist,
            patient.id,
            FormalAssessmentCreate(
                instrument_name="UNKNOWN",
                instrument_version="v1",
                score_unit="points",
                administration_mode="in_person",
                metrics={"invented_clinical_score": 100},
            ),
        )
    assert exc.value.status_code == 422
