from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.response import api_success
from app.database.session import get_db
from app.modules.assessment.model import AssessmentReviewStatus, AssessmentType
from app.modules.assessment.schema import AssessmentCreate, AssessmentReviewUpdate
from app.modules.profiles.service import get_patient_ability_profile
from app.modules.therapist import service
from app.modules.training.schema import TrainingRecommendationReviewUpdate
from app.modules.training.service import get_patient_recommendation_for_therapist, save_patient_recommendation_review
from app.modules.users.model import User
from app.modules.users.service import require_therapist

router = APIRouter(prefix="/therapist", tags=["therapist"])


@router.get("/patients")
def patients(
    current_user: User = Depends(require_therapist),
    db: Session = Depends(get_db),
):
    result = service.list_patients(db)
    return api_success([item.model_dump(mode="json") for item in result])


@router.post("/patients/{patient_user_id}/assessments")
def create_assessment(
    patient_user_id: UUID,
    payload: AssessmentCreate,
    current_user: User = Depends(require_therapist),
    db: Session = Depends(get_db),
):
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
    result = service.review_patient_assessment(db, current_user, patient_user_id, assessment_id, payload)
    return api_success(result.model_dump(mode="json"))


@router.get("/patients/{patient_user_id}/ability-profile")
def ability_profile(
    patient_user_id: UUID,
    current_user: User = Depends(require_therapist),
    db: Session = Depends(get_db),
):
    result = get_patient_ability_profile(db, patient_user_id)
    return api_success(result.model_dump(mode="json"))


@router.get("/patients/{patient_user_id}/training-recommendation")
def training_recommendation(
    patient_user_id: UUID,
    current_user: User = Depends(require_therapist),
    db: Session = Depends(get_db),
):
    result = get_patient_recommendation_for_therapist(db, patient_user_id)
    return api_success(result.model_dump(mode="json"))


@router.post("/patients/{patient_user_id}/training-recommendation/review")
def review_training_recommendation(
    patient_user_id: UUID,
    payload: TrainingRecommendationReviewUpdate,
    current_user: User = Depends(require_therapist),
    db: Session = Depends(get_db),
):
    result = save_patient_recommendation_review(db, current_user, patient_user_id, payload)
    return api_success(result.model_dump(mode="json"))


@router.get("/patients/{patient_user_id}/assessments/compare")
def compare(
    patient_user_id: UUID,
    baseline_id: UUID | None = None,
    current_id: UUID | None = None,
    current_user: User = Depends(require_therapist),
    db: Session = Depends(get_db),
):
    result = service.compare_patient_assessments(db, patient_user_id, baseline_id, current_id)
    return api_success(result.model_dump(mode="json"))
