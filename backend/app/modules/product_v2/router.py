from uuid import UUID

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.response import api_success
from app.database.session import get_db
from app.modules.attempts.schema import AttemptRead
from app.modules.product_v2 import service
from app.modules.product_v2.schema import (
    AttemptCreateV2,
    AttentionResolve,
    DailyPlanUpdate,
    DecisionCreate,
    FormalAssessmentCreate,
    GoalCreate,
    PatientSettingsUpdate,
    SessionCommand,
    SessionStart,
    StageReviewCreate,
    TrainingPlanDraftCreate,
)
from app.modules.users.model import User
from app.modules.users.service import require_patient, require_therapist
from app.integrations.acoustic_analysis.provider import get_acoustic_analysis_provider
from app.integrations.asr.provider import get_asr_provider
from app.integrations.llm.provider import get_llm_feedback_provider
from app.integrations.pronunciation_assessment.provider import get_pronunciation_provider
from app.integrations.tts.provider import get_tts_provider
from app.integrations.voice_clone.provider import get_voice_clone_provider


router = APIRouter(prefix="/v2", tags=["product-v2"])


@router.get("/patient/home")
def patient_home(current_user: User = Depends(require_patient), db: Session = Depends(get_db)):
    return api_success(service.patient_home(db, current_user))


@router.get("/patient/progress")
def patient_progress(current_user: User = Depends(require_patient), db: Session = Depends(get_db)):
    return api_success(service.patient_progress(db, current_user))


@router.get("/patient/settings")
def patient_settings(current_user: User = Depends(require_patient), db: Session = Depends(get_db)):
    profile = service.get_patient_profile(db, current_user)
    return api_success({"timezone": profile.timezone})


@router.patch("/patient/settings")
def update_patient_settings(payload: PatientSettingsUpdate, current_user: User = Depends(require_patient), db: Session = Depends(get_db)):
    profile = service.get_patient_profile(db, current_user)
    if not payload.timezone:
        return api_success({"timezone": profile.timezone})
    return api_success(service.update_patient_timezone(db, current_user, payload.timezone))


@router.post("/patient/training-sessions/start-or-resume")
def start_or_resume(payload: SessionStart, current_user: User = Depends(require_patient), db: Session = Depends(get_db)):
    return api_success(service.start_or_resume(db, current_user, payload.session_kind, payload.training_plan_version_id, payload.extra_pool_id))


@router.get("/patient/practice/extra-pool")
def extra_practice_pool(refresh: bool = False, current_user: User = Depends(require_patient), db: Session = Depends(get_db)):
    return api_success(service.patient_extra_practice_pool(db, current_user, force=refresh))


@router.get("/patient/training-sessions/{session_id}")
def get_training_session(session_id: UUID, current_user: User = Depends(require_patient), db: Session = Depends(get_db)):
    return api_success(service.get_patient_session(db, current_user, session_id))


@router.post("/patient/training-sessions/{session_id}/{command}")
def training_session_command(session_id: UUID, command: str, payload: SessionCommand, current_user: User = Depends(require_patient), db: Session = Depends(get_db)):
    return api_success(service.session_command(db, current_user, session_id, command, payload.reason))


@router.post("/patient/training-sessions/{session_id}/exercises/{task_id}/{command}")
def exercise_command(session_id: UUID, task_id: UUID, command: str, current_user: User = Depends(require_patient), db: Session = Depends(get_db)):
    return api_success(service.task_command(db, current_user, session_id, task_id, command))


@router.get("/patient/training-sessions/{session_id}/summary")
def training_session_summary(session_id: UUID, current_user: User = Depends(require_patient), db: Session = Depends(get_db)):
    return api_success(service.session_summary(db, current_user, session_id))


@router.post("/patient/attempts")
def create_attempt(payload: AttemptCreateV2, current_user: User = Depends(require_patient), db: Session = Depends(get_db)):
    row = service.create_attempt_v2(db, current_user, payload)
    return api_success(AttemptRead.model_validate(row).model_dump(mode="json"))


@router.post("/patient/attempts/{attempt_id}/audio")
def upload_attempt_audio(attempt_id: UUID, audio_file: UploadFile = File(...), current_user: User = Depends(require_patient), db: Session = Depends(get_db)):
    row = service.upload_attempt_audio(db, current_user, attempt_id, audio_file)
    return api_success(AttemptRead.model_validate(row).model_dump(mode="json"))


@router.post("/patient/attempts/{attempt_id}/analyze")
def analyze_attempt(attempt_id: UUID, current_user: User = Depends(require_patient), db: Session = Depends(get_db)):
    return api_success(service.analyze_attempt_v2(db, current_user, attempt_id))


@router.get("/therapist/workbench")
def workbench(current_user: User = Depends(require_therapist), db: Session = Depends(get_db)):
    return api_success(service.therapist_workbench(db, current_user))


@router.get("/therapist/patients/{patient_user_id}/workspace")
def patient_workspace(patient_user_id: UUID, current_user: User = Depends(require_therapist), db: Session = Depends(get_db)):
    return api_success(service.patient_workspace(db, current_user, patient_user_id))


@router.get("/therapist/training-sessions/{session_id}")
def therapist_training_session(session_id: UUID, current_user: User = Depends(require_therapist), db: Session = Depends(get_db)):
    return api_success(service.therapist_session_detail(db, current_user, session_id))


@router.get("/therapist/training-sessions/{session_id}/exercises/{task_id}")
def therapist_training_exercise(session_id: UUID, task_id: UUID, current_user: User = Depends(require_therapist), db: Session = Depends(get_db)):
    return api_success(service.therapist_exercise_detail(db, current_user, session_id, task_id))


@router.post("/therapist/patients/{patient_user_id}/rehabilitation-goals")
def create_rehabilitation_goal(patient_user_id: UUID, payload: GoalCreate, current_user: User = Depends(require_therapist), db: Session = Depends(get_db)):
    return api_success(service.create_goal(db, current_user, patient_user_id, payload))


@router.get("/therapist/patients/{patient_user_id}/training-plans")
def list_training_plans(patient_user_id: UUID, current_user: User = Depends(require_therapist), db: Session = Depends(get_db)):
    return api_success(service.list_plans(db, current_user, patient_user_id))


@router.get("/therapist/patients/{patient_user_id}/daily-plan")
def therapist_daily_plan(patient_user_id: UUID, current_user: User = Depends(require_therapist), db: Session = Depends(get_db)):
    return api_success(service.therapist_daily_plan(db, current_user, patient_user_id))


@router.patch("/therapist/patients/{patient_user_id}/daily-plan")
def update_therapist_daily_plan(patient_user_id: UUID, payload: DailyPlanUpdate, current_user: User = Depends(require_therapist), db: Session = Depends(get_db)):
    return api_success(service.update_therapist_daily_plan(db, current_user, patient_user_id, payload))


@router.post("/therapist/patients/{patient_user_id}/training-plans")
def create_training_plan(patient_user_id: UUID, payload: TrainingPlanDraftCreate, current_user: User = Depends(require_therapist), db: Session = Depends(get_db)):
    return api_success(service.create_plan_draft(db, current_user, patient_user_id, payload))


@router.post("/therapist/patients/{patient_user_id}/training-plans/{plan_id}/publish")
def publish_training_plan(patient_user_id: UUID, plan_id: UUID, current_user: User = Depends(require_therapist), db: Session = Depends(get_db)):
    return api_success(service.publish_plan(db, current_user, patient_user_id, plan_id))


@router.post("/therapist/attention-items/{item_id}/acknowledge")
def acknowledge_attention(item_id: UUID, current_user: User = Depends(require_therapist), db: Session = Depends(get_db)):
    return api_success(service.set_attention_status(db, current_user, item_id, "acknowledged"))


@router.post("/therapist/attention-items/{item_id}/resolve")
def resolve_attention(item_id: UUID, payload: AttentionResolve, current_user: User = Depends(require_therapist), db: Session = Depends(get_db)):
    return api_success(service.set_attention_status(db, current_user, item_id, payload.status, payload.resolution_note))


@router.post("/therapist/patients/{patient_user_id}/stage-reviews")
def create_stage_review(patient_user_id: UUID, payload: StageReviewCreate, current_user: User = Depends(require_therapist), db: Session = Depends(get_db)):
    return api_success(service.create_stage_review(db, current_user, patient_user_id, payload))


@router.get("/therapist/stage-reviews/{review_id}")
def get_stage_review(review_id: UUID, current_user: User = Depends(require_therapist), db: Session = Depends(get_db)):
    return api_success(service.stage_review_detail(db, current_user, review_id))


@router.post("/therapist/stage-reviews/{review_id}/decisions")
def create_therapist_decision(review_id: UUID, payload: DecisionCreate, current_user: User = Depends(require_therapist), db: Session = Depends(get_db)):
    return api_success(service.create_decision(db, current_user, review_id, payload))


@router.post("/therapist/patients/{patient_user_id}/formal-assessments")
def create_formal_assessment(patient_user_id: UUID, payload: FormalAssessmentCreate, current_user: User = Depends(require_therapist), db: Session = Depends(get_db)):
    return api_success(service.create_formal_assessment(db, current_user, patient_user_id, payload))


@router.get("/provider-matrix")
def provider_matrix(current_user: User = Depends(require_therapist)):
    settings = get_settings()
    runtime = {
        "ASR": type(get_asr_provider()).__name__,
        "Acoustic": type(get_acoustic_analysis_provider()).__name__,
        "Pronunciation": type(get_pronunciation_provider()).__name__,
        "Generic LLM Feedback": type(get_llm_feedback_provider()).__name__,
        "TTS": type(get_tts_provider()).__name__,
        "Voice Clone": type(get_voice_clone_provider()).__name__,
    }
    scenario_active = settings.llm_feedback_provider in {"openai", "openai_compatible", "external"} and bool(
        settings.llm_feedback_api_key and settings.llm_feedback_base_url and settings.llm_feedback_model
    )
    rows = [
        ("ASR", settings.asr_provider, runtime["ASR"], "TencentASRProvider" in runtime["ASR"], True, "configured provider with existing fallback metadata", "REAL AND ACTIVE" if "Tencent" in runtime["ASR"] else "MOCK TEST ONLY"),
        ("Acoustic", settings.acoustic_provider, runtime["Acoustic"], "LocalAcousticAnalysisProvider" in runtime["Acoustic"], True, "formal metrics reject mock source", "REAL AND ACTIVE" if "Local" in runtime["Acoustic"] else "MOCK TEST ONLY"),
        ("Pronunciation", settings.pronunciation_provider, runtime["Pronunciation"], "TencentSoeProvider" in runtime["Pronunciation"], True, "disabled result when configuration is missing", "REAL AND ACTIVE" if "TencentSoe" in runtime["Pronunciation"] else "DISABLED"),
        ("Generic LLM Feedback", settings.llm_feedback_provider, runtime["Generic LLM Feedback"], False, True, "factory remains mock-only; v2 summary uses deterministic template", "MOCK ONLY"),
        ("Scenario Semantics", settings.llm_feedback_provider, "OpenAICompatibleScenarioSemantics" if scenario_active else "disabled", scenario_active, True, "deterministic semantic fallback retains provenance", "REAL AND ACTIVE" if scenario_active else "REAL IMPLEMENTATION BUT NOT CONFIGURED"),
        ("TTS", settings.tts_provider, runtime["TTS"], "Mock" not in runtime["TTS"], True, "existing provider selection preserved", "REAL AND ACTIVE" if "Mock" not in runtime["TTS"] else "MOCK TEST ONLY"),
        ("Voice Clone", settings.vcl_provider, runtime["Voice Clone"], "TencentVCLProvider" in runtime["Voice Clone"], True, "existing provider selection preserved", "REAL AND ACTIVE" if "TencentVCL" in runtime["Voice Clone"] else "DISABLED"),
        ("Avatar", "aliyun" if settings.aliyun_avatar_enabled else "disabled", "AliyunAvatarProvider" if settings.aliyun_avatar_enabled else "disabled", settings.aliyun_avatar_enabled, True, "existing Aliyun implementation preserved", "REAL AND ACTIVE" if settings.aliyun_avatar_enabled else "DISABLED"),
    ]
    return api_success([
        {"capability": capability, "configured_provider": configured, "runtime_selected_provider": selected, "real_implementation_active": real, "mock_available": mock, "fallback_behavior": fallback, "used_by_v2": capability in {"ASR", "Acoustic", "Pronunciation", "Scenario Semantics"}, "verification_result": verification}
        for capability, configured, selected, real, mock, fallback, verification in rows
    ])
