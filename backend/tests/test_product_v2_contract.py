from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

from pydantic import ValidationError

from app.database.base import Base, import_models
from app.main import app
from app.modules.product_v2.comparability import build_comparable_set, trend_fact
from app.modules.product_v2.schema import ExerciseRuleCreate, TrainingPlanDraftCreate


def metric(value, *, key="same-context", source_type="attempt", eligible=True, status="measured", offset=0):
    return SimpleNamespace(
        id=uuid4(),
        value=value,
        comparison_key=key,
        source_type=source_type,
        decision_eligible=eligible,
        status=status,
        quality={"source_status": "mock" if source_type in {"mock", "demo"} else "real"},
        measured_at=datetime.now(timezone.utc) + timedelta(days=offset),
    )


def test_comparability_excludes_mock_and_mismatched_context():
    first = metric(60, offset=0)
    second = metric(70, offset=1)
    mock = metric(99, source_type="demo", offset=2)
    different = metric(80, key="different", offset=3)
    result = build_comparable_set([first, second, mock, different])
    assert result.status == "partially_comparable"
    assert result.included_measurement_ids == [str(first.id), str(second.id)]
    reasons = {reason for row in result.excluded for reason in row["reason_codes"]}
    assert "mock_excluded" in reasons
    assert "comparison_key_mismatch" in reasons


def test_trend_engine_only_consumes_comparable_set():
    rows = [metric(60, offset=0), metric(70, offset=1), metric(80, offset=2)]
    comparable = build_comparable_set(rows)
    trend = trend_fact(rows, comparable)
    assert trend["status"] == "measured"
    assert trend["sample_count"] == 3
    assert trend["delta"] == 20
    assert trend["slope"] == 10


def test_training_plan_schema_requires_unique_exercise_order():
    rule = ExerciseRuleCreate(task_template_id=uuid4(), exercise_type="repeat", order_index=0)
    try:
        TrainingPlanDraftCreate(
            rehabilitation_goal_id=uuid4(),
            stage_focus="日常表达",
            exercise_rules=[rule, rule.model_copy(update={"task_template_id": uuid4()})],
        )
    except ValidationError as exc:
        assert "order_index must be unique" in str(exc)
    else:
        raise AssertionError("duplicate order_index must be rejected")


def test_product_reset_tables_are_registered():
    import_models()
    required = {
        "rehabilitation_goals",
        "training_plan_versions",
        "training_plan_exercise_rules",
        "clinical_evidence",
        "clinical_metrics",
        "clinical_observations",
        "clinical_recommendations",
        "patient_milestones",
        "attention_items",
        "stage_reviews",
        "therapist_decisions",
        "training_session_summaries",
    }
    assert required <= set(Base.metadata.tables)


def test_product_v2_application_routes_are_registered():
    paths = {route.path for route in app.routes}
    required = {
        "/api/v2/patient/home",
        "/api/v2/patient/progress",
        "/api/v2/patient/training-sessions/start-or-resume",
        "/api/v2/therapist/workbench",
        "/api/v2/therapist/patients/{patient_user_id}/workspace",
        "/api/v2/therapist/training-sessions/{session_id}",
        "/api/v2/therapist/stage-reviews/{review_id}/decisions",
    }
    assert required <= paths

