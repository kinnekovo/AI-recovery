from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.core.response import api_success
from app.database.session import get_db
from app.modules.assessment.model import AssessmentReviewStatus, AssessmentType
from app.modules.assessment.schema import AssessmentCreate, AssessmentReviewUpdate, ClinicalSourceUpdate
from app.modules.profiles.service import get_patient_ability_profile
from app.modules.profile_v2 import service as profile_v2_service
from app.modules.profile_v2.schema import ProfileSnapshotRead, ProfileEvidenceLinkRead
from app.modules.policy_v2 import service as policy_v2_service
from app.modules.policy_v2.schema import PolicyDecisionRead, PolicyFeedbackCreate, PolicyObservationCreate
from app.modules.policy_validation import service as validation_service
from app.modules.therapist import service
from app.modules.therapist.report_export import render_stage_report_html
from app.modules.training.schema import TrainingRecommendationReviewUpdate
from app.modules.training.service import (
    create_task_template,
    create_strategy_feedback,
    get_phase3_demo_status,
    get_patient_recommendation_effects,
    get_patient_recommendation_for_therapist,
    list_task_templates,
    save_patient_recommendation_review,
    update_task_template,
)
from app.modules.therapist.schema import (
    RecommendationNoteCreate,
    ScenarioExpressionReviewUpdate,
    TherapistPatientAssignmentCreate,
)
from app.modules.pronunciation.schema import IntelligibilityReviewCreate, PronunciationRevisionCreate
from app.modules.pronunciation import service as pronunciation_service
from app.modules.scenario_dialogues import service as scenario_dialogue_service
from app.modules.scenario_dialogues.schema import ScenarioDialogueReviewUpdate
from app.modules.training.model import TrainingType
from app.modules.training.schema import StrategyFeedbackCreate, TaskTemplateCreate, TaskTemplateUpdate
from app.modules.users.model import User
from app.modules.users.service import require_therapist

router = APIRouter(prefix="/therapist", tags=["therapist"])

@router.post("/policy-v2/validation/datasets")
def create_policy_validation_dataset(name: str, version: str, current_user: User=Depends(require_therapist), db: Session=Depends(get_db)):
    row=validation_service.create_dataset(db,current_user,name,version);return api_success({"id":str(row.id),"status":row.status,"version":row.version})
@router.post("/policy-v2/validation/datasets/{dataset_id}/decisions/{decision_id}")
def add_policy_validation_decision(dataset_id: UUID,decision_id: UUID,current_user: User=Depends(require_therapist),db: Session=Depends(get_db)):
    try:validation_service.add_decision(db,dataset_id,decision_id)
    except ValueError as e:raise HTTPException(status_code=409,detail=str(e)) from e
    return api_success({"dataset_id":str(dataset_id),"decision_id":str(decision_id)})
@router.post("/policy-v2/validation/datasets/{dataset_id}/freeze")
def freeze_policy_validation_dataset(dataset_id: UUID,current_user: User=Depends(require_therapist),db: Session=Depends(get_db)):
    try:r=validation_service.freeze(db,dataset_id)
    except ValueError as e:raise HTTPException(status_code=409,detail=str(e)) from e
    return api_success({"id":str(r.id),"status":r.status})
@router.post("/policy-v2/validation/datasets/{dataset_id}/runs")
def run_policy_validation(dataset_id: UUID,current_user: User=Depends(require_therapist),db: Session=Depends(get_db)):
    try:r=validation_service.run_validation(db,dataset_id)
    except ValueError as e:raise HTTPException(status_code=409,detail=str(e)) from e
    return api_success({"id":str(r.id),"promotion_status":r.promotion_status,"reason_codes":r.reason_codes,"report":r.report})
@router.get("/policy-v2/validation/registry")
def policy_validation_registry(policy_version: str|None=None,rules_version: str|None=None,current_user: User=Depends(require_therapist),db: Session=Depends(get_db)):
    rows=validation_service.registry(db,policy_version,rules_version);return api_success([{"policy_version":x.policy_version,"rules_version":x.rules_version,"validation_status":x.validation_status,"latest_validation_run_id":str(x.latest_validation_run_id) if x.latest_validation_run_id else None,"reason_codes":x.status_reason_codes} for x in rows])


def _patient_profile_id(db: Session, patient_user_id: UUID) -> UUID:
    profile = db.scalar(select(service.PatientProfile).where(service.PatientProfile.user_id == patient_user_id))
    if not profile:
        raise HTTPException(status_code=404, detail="患者档案不存在")
    return profile.id


@router.get("/patients/{patient_user_id}/profile")
def profile_v2(patient_user_id: UUID, current_user: User = Depends(require_therapist), db: Session = Depends(get_db)):
    service.require_therapist_patient_access(db, current_user, patient_user_id)
    snapshot = profile_v2_service.get_latest_profile(db, _patient_profile_id(db, patient_user_id))
    if not snapshot: raise HTTPException(status_code=404, detail="尚未生成 Profile V2 快照")
    return api_success(ProfileSnapshotRead.model_validate(snapshot).model_dump(mode="json"))


@router.get("/patients/{patient_user_id}/profile/history")
def profile_v2_history(patient_user_id: UUID, current_user: User = Depends(require_therapist), db: Session = Depends(get_db)):
    service.require_therapist_patient_access(db, current_user, patient_user_id)
    rows = profile_v2_service.list_history(db, _patient_profile_id(db, patient_user_id))
    return api_success([ProfileSnapshotRead.model_validate(row).model_dump(mode="json") for row in rows])


@router.get("/patients/{patient_user_id}/profile/{snapshot_id}/evidence")
def profile_v2_evidence(patient_user_id: UUID, snapshot_id: UUID, current_user: User = Depends(require_therapist), db: Session = Depends(get_db)):
    service.require_therapist_patient_access(db, current_user, patient_user_id)
    snapshot = db.get(profile_v2_service.PatientProfileSnapshot, snapshot_id)
    if not snapshot or snapshot.patient_profile_id != _patient_profile_id(db, patient_user_id): raise HTTPException(status_code=404, detail="画像快照不存在")
    return api_success([ProfileEvidenceLinkRead.model_validate(row).model_dump(mode="json") for row in profile_v2_service.evidence_for_snapshot(db, snapshot_id)])


@router.post("/patients/{patient_user_id}/profile/rebuild")
def rebuild_profile_v2(patient_user_id: UUID, current_user: User = Depends(require_therapist), db: Session = Depends(get_db)):
    service.require_therapist_patient_access(db, current_user, patient_user_id)
    snapshot = profile_v2_service.build_profile(db, _patient_profile_id(db, patient_user_id))
    return api_success(ProfileSnapshotRead.model_validate(snapshot).model_dump(mode="json"))


@router.post("/patients/{patient_user_id}/policy-v2/shadow")
def generate_policy_v2_shadow(patient_user_id: UUID, current_user: User = Depends(require_therapist), db: Session = Depends(get_db)):
    service.require_therapist_patient_access(db, current_user, patient_user_id)
    row=policy_v2_service.generate_shadow(db,_patient_profile_id(db,patient_user_id))
    return api_success(PolicyDecisionRead.model_validate(row).model_dump(mode="json"))


@router.get("/patients/{patient_user_id}/policy-v2/latest")
def latest_policy_v2_shadow(patient_user_id: UUID, current_user: User = Depends(require_therapist), db: Session = Depends(get_db)):
    service.require_therapist_patient_access(db,current_user,patient_user_id); row=policy_v2_service.latest(db,_patient_profile_id(db,patient_user_id))
    if not row: raise HTTPException(status_code=404,detail="尚未生成 Policy V2 shadow 决策")
    return api_success(PolicyDecisionRead.model_validate(row).model_dump(mode="json"))


@router.get("/patients/{patient_user_id}/policy-v2/history")
def policy_v2_history(patient_user_id: UUID,current_user: User=Depends(require_therapist),db: Session=Depends(get_db)):
    service.require_therapist_patient_access(db,current_user,patient_user_id)
    return api_success([PolicyDecisionRead.model_validate(x).model_dump(mode="json") for x in policy_v2_service.history(db,_patient_profile_id(db,patient_user_id))])


@router.get("/patients/{patient_user_id}/policy-v2/analytics")
def policy_v2_analytics(patient_user_id: UUID,current_user: User=Depends(require_therapist),db: Session=Depends(get_db)):
    service.require_therapist_patient_access(db,current_user,patient_user_id);return api_success(policy_v2_service.analytics(db,_patient_profile_id(db,patient_user_id)))


@router.get("/patients/{patient_user_id}/policy-v2/{decision_id}")
def policy_v2_detail(patient_user_id: UUID,decision_id: UUID,current_user: User=Depends(require_therapist),db: Session=Depends(get_db)):
    service.require_therapist_patient_access(db,current_user,patient_user_id);row=policy_v2_service.detail(db,decision_id)
    if not row or row.patient_profile_id!=_patient_profile_id(db,patient_user_id):raise HTTPException(status_code=404,detail="Policy 决策不存在")
    return api_success(PolicyDecisionRead.model_validate(row).model_dump(mode="json"))


@router.get("/patients/{patient_user_id}/policy-v2/{decision_id}/explanation")
def policy_v2_explanation(patient_user_id: UUID,decision_id: UUID,current_user: User=Depends(require_therapist),db: Session=Depends(get_db)):
    service.require_therapist_patient_access(db,current_user,patient_user_id);row=policy_v2_service.detail(db,decision_id)
    if not row or row.patient_profile_id!=_patient_profile_id(db,patient_user_id):raise HTTPException(status_code=404,detail="Policy 决策不存在")
    return api_success(policy_v2_service.explanation(db,decision_id))


@router.post("/patients/{patient_user_id}/policy-v2/{decision_id}/feedback")
def policy_v2_feedback(patient_user_id: UUID,decision_id: UUID,payload: PolicyFeedbackCreate,current_user: User=Depends(require_therapist),db: Session=Depends(get_db)):
    service.require_therapist_patient_access(db,current_user,patient_user_id); row=policy_v2_service.detail(db,decision_id)
    if not row or row.patient_profile_id!=_patient_profile_id(db,patient_user_id):raise HTTPException(status_code=404,detail="Policy 决策不存在")
    feedback=policy_v2_service.add_feedback(db,decision_id,current_user.id,payload);return api_success({"id":str(feedback.id),"review_round":feedback.review_round,"agreement":feedback.agreement})


@router.post("/patients/{patient_user_id}/policy-v2/{decision_id}/observe")
def policy_v2_observe(patient_user_id: UUID,decision_id: UUID,payload: PolicyObservationCreate,current_user: User=Depends(require_therapist),db: Session=Depends(get_db)):
    service.require_therapist_patient_access(db,current_user,patient_user_id);row=policy_v2_service.detail(db,decision_id)
    if not row or row.patient_profile_id!=_patient_profile_id(db,patient_user_id):raise HTTPException(status_code=404,detail="Policy 决策不存在")
    try: observation=policy_v2_service.observe_policy_outcome(db,decision_id,payload.training_session_id)
    except ValueError as exc: raise HTTPException(status_code=409,detail=str(exc)) from exc
    return api_success({"id":str(observation.id),"focus_match":observation.focus_match,"difficulty_match":observation.difficulty_match,"reassessment_match":observation.reassessment_match})




@router.patch("/scenario-dialogues/{dialogue_id}/review")
def review_scenario_dialogue(
    dialogue_id: UUID,
    payload: ScenarioDialogueReviewUpdate,
    current_user: User = Depends(require_therapist),
    db: Session = Depends(get_db),
):
    result = scenario_dialogue_service.review_evaluation(db, current_user, dialogue_id, payload)
    return api_success(result.model_dump(mode="json"))


@router.get("/patients/{patient_user_id}/scenario-dialogues")
def patient_scenario_dialogues(
    patient_user_id: UUID,
    current_user: User = Depends(require_therapist),
    db: Session = Depends(get_db),
):
    result = scenario_dialogue_service.list_dialogues_for_therapist(db, current_user, patient_user_id)
    return api_success([item.model_dump(mode="json") for item in result])


@router.get("/scenario-dialogues/{dialogue_id}")
def scenario_dialogue_detail(
    dialogue_id: UUID,
    current_user: User = Depends(require_therapist),
    db: Session = Depends(get_db),
):
    result = scenario_dialogue_service.get_dialogue_for_therapist(db, current_user, dialogue_id)
    return api_success(result.model_dump(mode="json"))


def require_pronunciation_access(db: Session, current_user: User, analysis_id: UUID) -> None:
    attempt_id = pronunciation_service.get_analysis_attempt_id(db, analysis_id)
    attempt = db.get(service.Attempt, attempt_id)
    task = db.get(service.SessionTask, attempt.session_task_id) if attempt else None
    session = db.get(service.TrainingSession, task.training_session_id) if task else None
    if not session:
        raise HTTPException(status_code=404, detail="精细发音评估上下文不存在")
    profile = db.get(service.PatientProfile, session.patient_profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="患者档案不存在")
    service.require_therapist_patient_access(db, current_user, profile.user_id)


@router.get("/patients")
def patients(
    current_user: User = Depends(require_therapist),
    db: Session = Depends(get_db),
):
    result = service.list_patients(db, current_user)
    return api_success([item.model_dump(mode="json") for item in result])


@router.post("/patient-assignments")
def create_patient_assignment(
    payload: TherapistPatientAssignmentCreate,
    current_user: User = Depends(require_therapist),
    db: Session = Depends(get_db),
):
    result = service.create_patient_assignment(db, current_user, payload.therapist_user_id, payload.patient_user_id)
    return api_success(result.model_dump(mode="json"))


@router.delete("/patient-assignments/{assignment_id}")
def revoke_patient_assignment(
    assignment_id: UUID,
    current_user: User = Depends(require_therapist),
    db: Session = Depends(get_db),
):
    result = service.revoke_patient_assignment(db, current_user, assignment_id)
    return api_success(result.model_dump(mode="json"))


@router.get("/trial-quality")
def trial_quality(
    current_user: User = Depends(require_therapist),
    db: Session = Depends(get_db),
):
    result = service.get_trial_quality(db)
    return api_success(result.model_dump(mode="json"))


@router.get("/task-templates")
def task_templates(
    training_type: TrainingType | None = None,
    include_inactive: bool = False,
    current_user: User = Depends(require_therapist),
    db: Session = Depends(get_db),
):
    result = list_task_templates(db, training_type=training_type, include_inactive=include_inactive)
    return api_success([item.model_dump(mode="json") for item in result])


@router.post("/task-templates")
def create_template(
    payload: TaskTemplateCreate,
    current_user: User = Depends(require_therapist),
    db: Session = Depends(get_db),
):
    result = create_task_template(db, payload)
    return api_success(result.model_dump(mode="json"))


@router.patch("/task-templates/{template_id}")
def update_template(
    template_id: UUID,
    payload: TaskTemplateUpdate,
    current_user: User = Depends(require_therapist),
    db: Session = Depends(get_db),
):
    result = update_task_template(db, template_id, payload)
    return api_success(result.model_dump(mode="json"))


@router.post("/patients/{patient_user_id}/assessments")
def create_assessment(
    patient_user_id: UUID,
    payload: AssessmentCreate,
    current_user: User = Depends(require_therapist),
    db: Session = Depends(get_db),
):
    service.require_therapist_patient_access(db, current_user, patient_user_id)
    result = service.create_patient_assessment(db, current_user, patient_user_id, payload)
    return api_success(result.model_dump(mode="json"))


@router.get("/patients/{patient_user_id}/assessments")
def history(
    patient_user_id: UUID,
    assessment_type: AssessmentType | None = None,
    review_status: AssessmentReviewStatus | None = None,
    current_user: User = Depends(require_therapist),
    db: Session = Depends(get_db),
):
    service.require_therapist_patient_access(db, current_user, patient_user_id)
    result = service.list_patient_assessments(db, patient_user_id, assessment_type, review_status)
    return api_success([item.model_dump(mode="json") for item in result])


@router.patch("/patients/{patient_user_id}/assessments/{assessment_id}/review")
def review_assessment(
    patient_user_id: UUID,
    assessment_id: UUID,
    payload: AssessmentReviewUpdate,
    current_user: User = Depends(require_therapist),
    db: Session = Depends(get_db),
):
    service.require_therapist_patient_access(db, current_user, patient_user_id)
    result = service.review_patient_assessment(db, current_user, patient_user_id, assessment_id, payload)
    return api_success(result.model_dump(mode="json"))


@router.patch("/patients/{patient_user_id}/assessments/{assessment_id}/clinical-source")
def update_clinical_source(patient_user_id: UUID, assessment_id: UUID, payload: ClinicalSourceUpdate, current_user: User = Depends(require_therapist), db: Session = Depends(get_db)):
    service.require_therapist_patient_access(db, current_user, patient_user_id)
    return api_success(service.update_clinical_source(db, current_user, patient_user_id, assessment_id, payload).model_dump(mode="json"))


@router.get("/patients/{patient_user_id}/assessments/{assessment_id}/clinical-stage")
def clinical_stage_detail(patient_user_id: UUID, assessment_id: UUID, current_user: User = Depends(require_therapist), db: Session = Depends(get_db)):
    service.require_therapist_patient_access(db, current_user, patient_user_id)
    return api_success(service.clinical_stage_detail(db, patient_user_id, assessment_id))


@router.get("/patients/{patient_user_id}/assessments/{assessment_id}/clinical-stage/preview")
def clinical_stage_preview(patient_user_id: UUID, assessment_id: UUID, current_user: User = Depends(require_therapist), db: Session = Depends(get_db)):
    service.require_therapist_patient_access(db, current_user, patient_user_id)
    return api_success(service.clinical_stage_detail(db, patient_user_id, assessment_id)["canonical_preview"])


@router.get("/patients/{patient_user_id}/assessments/{assessment_id}/clinical-stage/comparison/{other_id}")
def clinical_stage_comparison(patient_user_id: UUID, assessment_id: UUID, other_id: UUID, current_user: User = Depends(require_therapist), db: Session = Depends(get_db)):
    service.require_therapist_patient_access(db, current_user, patient_user_id)
    return api_success(service.compare_clinical_stage(db, patient_user_id, assessment_id, other_id))


@router.get("/patients/{patient_user_id}/ability-profile")
def ability_profile(
    patient_user_id: UUID,
    current_user: User = Depends(require_therapist),
    db: Session = Depends(get_db),
):
    service.require_therapist_patient_access(db, current_user, patient_user_id)
    result = get_patient_ability_profile(db, patient_user_id)
    return api_success(result.model_dump(mode="json"))


@router.get("/patients/{patient_user_id}/training-recommendation")
def training_recommendation(
    patient_user_id: UUID,
    current_user: User = Depends(require_therapist),
    db: Session = Depends(get_db),
):
    service.require_therapist_patient_access(db, current_user, patient_user_id)
    result = get_patient_recommendation_for_therapist(db, patient_user_id)
    return api_success(result.model_dump(mode="json"))


@router.get("/patients/{patient_user_id}/training-records")
def training_records(
    patient_user_id: UUID,
    current_user: User = Depends(require_therapist),
    db: Session = Depends(get_db),
):
    service.require_therapist_patient_access(db, current_user, patient_user_id)
    result = service.list_patient_training_records(db, patient_user_id)
    return api_success([item.model_dump(mode="json") for item in result])


@router.get("/patients/{patient_user_id}/attempts/{attempt_id}/scenario-review")
def scenario_review(
    patient_user_id: UUID,
    attempt_id: UUID,
    current_user: User = Depends(require_therapist),
    db: Session = Depends(get_db),
):
    result = service.get_scenario_expression_review(db, current_user, patient_user_id, attempt_id)
    return api_success(result.model_dump(mode="json"))


@router.patch("/patients/{patient_user_id}/attempts/{attempt_id}/scenario-review")
def update_scenario_review(
    patient_user_id: UUID,
    attempt_id: UUID,
    payload: ScenarioExpressionReviewUpdate,
    current_user: User = Depends(require_therapist),
    db: Session = Depends(get_db),
):
    result = service.review_scenario_expression(db, current_user, patient_user_id, attempt_id, payload)
    return api_success(result.model_dump(mode="json"))


@router.get("/patients/{patient_user_id}/pronunciation/inter-rater-agreement")
def pronunciation_inter_rater_agreement(
    patient_user_id: UUID,
    current_user: User = Depends(require_therapist),
    db: Session = Depends(get_db),
):
    service.require_therapist_patient_access(db, current_user, patient_user_id)
    result = service.get_patient_inter_rater_agreement(db, patient_user_id)
    return api_success(result.model_dump(mode="json"))


@router.get("/patients/{patient_user_id}/training-trends")
def training_trends(
    patient_user_id: UUID,
    current_user: User = Depends(require_therapist),
    db: Session = Depends(get_db),
):
    service.require_therapist_patient_access(db, current_user, patient_user_id)
    result = service.get_patient_training_trends(db, patient_user_id)
    return api_success(result.model_dump(mode="json"))


@router.get("/patients/{patient_user_id}/stage-report")
def stage_report(
    patient_user_id: UUID,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    current_user: User = Depends(require_therapist),
    db: Session = Depends(get_db),
):
    service.require_therapist_patient_access(db, current_user, patient_user_id)
    result = service.get_patient_stage_report(db, patient_user_id, date_from, date_to)
    return api_success(result.model_dump(mode="json"))


@router.get("/patients/{patient_user_id}/stage-report/export", response_class=HTMLResponse)
def stage_report_export(
    patient_user_id: UUID,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    current_user: User = Depends(require_therapist),
    db: Session = Depends(get_db),
):
    service.require_therapist_patient_access(db, current_user, patient_user_id)
    result = service.get_patient_stage_report(db, patient_user_id, date_from, date_to)
    return HTMLResponse(render_stage_report_html(result))


@router.get("/patients/{patient_user_id}/recommendation-note")
def recommendation_note(
    patient_user_id: UUID,
    current_user: User = Depends(require_therapist),
    db: Session = Depends(get_db),
):
    service.require_therapist_patient_access(db, current_user, patient_user_id)
    result = service.get_latest_recommendation_note(db, patient_user_id)
    return api_success(result.model_dump(mode="json"))


@router.post("/patients/{patient_user_id}/recommendation-note")
def save_recommendation_note(
    patient_user_id: UUID,
    payload: RecommendationNoteCreate,
    current_user: User = Depends(require_therapist),
    db: Session = Depends(get_db),
):
    service.require_therapist_patient_access(db, current_user, patient_user_id)
    result = service.save_recommendation_note(db, current_user, patient_user_id, payload.note)
    return api_success(result.model_dump(mode="json"))


@router.post(
    "/patients/{patient_user_id}/training-recommendation/review",
    deprecated=True,
    summary="Deprecated: legacy recommendation review compatibility endpoint",
    description="保留用于兼容 Phase 3 历史数据。当前推荐主路径由算法策略生成，治疗师仅通过 recommendation-note 做自然语言补充。",
)
def review_training_recommendation(
    patient_user_id: UUID,
    payload: TrainingRecommendationReviewUpdate,
    current_user: User = Depends(require_therapist),
    db: Session = Depends(get_db),
):
    service.require_therapist_patient_access(db, current_user, patient_user_id)
    result = save_patient_recommendation_review(db, current_user, patient_user_id, payload)
    return api_success(result.model_dump(mode="json"))


@router.get("/patients/{patient_user_id}/training-recommendation/effects")
def training_recommendation_effects(
    patient_user_id: UUID,
    current_user: User = Depends(require_therapist),
    db: Session = Depends(get_db),
):
    service.require_therapist_patient_access(db, current_user, patient_user_id)
    result = get_patient_recommendation_effects(db, patient_user_id)
    return api_success(result.model_dump(mode="json"))


@router.post(
    "/patients/{patient_user_id}/training-recommendation/strategy-feedback",
    deprecated=True,
    summary="Deprecated: legacy strategy feedback compatibility endpoint",
    description="保留用于兼容 Phase 3 历史策略反馈。当前趋势归因和自适应推荐由 recommendation_policy 生成。",
)
def strategy_feedback(
    patient_user_id: UUID,
    payload: StrategyFeedbackCreate,
    current_user: User = Depends(require_therapist),
    db: Session = Depends(get_db),
):
    service.require_therapist_patient_access(db, current_user, patient_user_id)
    result = create_strategy_feedback(db, current_user, patient_user_id, payload)
    return api_success(result.model_dump(mode="json"))


@router.get("/phase3/demo-status")
def phase3_demo_status(
    current_user: User = Depends(require_therapist),
    db: Session = Depends(get_db),
):
    result = get_phase3_demo_status(db)
    return api_success(result.model_dump(mode="json"))


@router.get("/pronunciation/{analysis_id}")
def pronunciation_detail(
    analysis_id: UUID,
    current_user: User = Depends(require_therapist),
    db: Session = Depends(get_db),
):
    require_pronunciation_access(db, current_user, analysis_id)
    attempt_id = pronunciation_service.get_analysis_attempt_id(db, analysis_id)
    return api_success(pronunciation_service.get_attempt_pronunciation(db, attempt_id).model_dump(mode="json"))


@router.post("/pronunciation/{analysis_id}/revisions")
def add_pronunciation_revision(
    analysis_id: UUID,
    payload: PronunciationRevisionCreate,
    current_user: User = Depends(require_therapist),
    db: Session = Depends(get_db),
):
    require_pronunciation_access(db, current_user, analysis_id)
    return api_success(pronunciation_service.add_revision(db, analysis_id, current_user, payload).model_dump(mode="json"))


@router.post("/pronunciation/{analysis_id}/intelligibility-reviews")
def add_intelligibility_review(
    analysis_id: UUID,
    payload: IntelligibilityReviewCreate,
    current_user: User = Depends(require_therapist),
    db: Session = Depends(get_db),
):
    require_pronunciation_access(db, current_user, analysis_id)
    return api_success(
        pronunciation_service.add_intelligibility_review(db, analysis_id, current_user, payload).model_dump(mode="json")
    )


@router.post("/pronunciation/{analysis_id}/complete-review")
def complete_pronunciation_review(
    analysis_id: UUID,
    current_user: User = Depends(require_therapist),
    db: Session = Depends(get_db),
):
    require_pronunciation_access(db, current_user, analysis_id)
    return api_success(pronunciation_service.complete_review(db, analysis_id, current_user).model_dump(mode="json"))


@router.get("/patients/{patient_user_id}/assessments/compare")
def compare(
    patient_user_id: UUID,
    baseline_id: UUID | None = None,
    current_id: UUID | None = None,
    current_user: User = Depends(require_therapist),
    db: Session = Depends(get_db),
):
    service.require_therapist_patient_access(db, current_user, patient_user_id)
    result = service.compare_patient_assessments(db, patient_user_id, baseline_id, current_id)
    return api_success(result.model_dump(mode="json"))
