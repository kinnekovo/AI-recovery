from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.response import api_success
from app.database.session import get_db
from app.modules.scenario_dialogues import service
from app.modules.scenario_dialogues.schema import ScenarioDialogueCreate, ScenarioDialoguePatientTurnCreate
from app.integrations.asr.provider import ASRProviderError, transcribe_with_fallback
from app.modules.files.model import FileType
from app.modules.files.service import save_upload
from app.modules.users.model import User
from app.modules.users.service import require_patient
from app.modules.users.service import require_therapist
from app.modules.evaluation_runs.functional_communication_v3 import get_functional_run_for_professional

router = APIRouter(prefix="/scenario-dialogues", tags=["scenario-dialogues"])

@router.post("")
def create(payload: ScenarioDialogueCreate, current_user: User = Depends(require_patient), db: Session = Depends(get_db)):
    return api_success(service.create_dialogue(db, current_user, payload.session_task_id).model_dump(mode="json"))

@router.get("/trends")
def trends(current_user: User = Depends(require_patient), db: Session = Depends(get_db)):
    return api_success(service.patient_trends(db, current_user))

@router.get("/{dialogue_id}")
def get(dialogue_id: UUID, current_user: User = Depends(require_patient), db: Session = Depends(get_db)):
    return api_success(service.get_dialogue(db, current_user, dialogue_id).model_dump(mode="json"))

@router.get("/{dialogue_id}/evaluation")
def evaluation(dialogue_id: UUID, current_user: User = Depends(require_patient), db: Session = Depends(get_db)):
    return api_success(service.get_evaluation(db, current_user, dialogue_id).model_dump(mode="json"))

@router.get("/{dialogue_id}/evaluation-v3")
def evaluation_v3(dialogue_id: UUID, current_user: User = Depends(require_therapist), db: Session = Depends(get_db)):
    return api_success(get_functional_run_for_professional(db, current_user, dialogue_id).model_dump(mode="json"))

@router.post("/{dialogue_id}/hint")
def hint(dialogue_id: UUID, current_user: User = Depends(require_patient), db: Session = Depends(get_db)):
    return api_success(service.next_hint(db, current_user, dialogue_id))

@router.post("/{dialogue_id}/finish")
def finish(dialogue_id: UUID, current_user: User = Depends(require_patient), db: Session = Depends(get_db)):
    return api_success(service.finish_dialogue(db, current_user, dialogue_id).model_dump(mode="json"))

@router.post("/{dialogue_id}/turns")
def add_turn(dialogue_id: UUID, payload: ScenarioDialoguePatientTurnCreate, current_user: User = Depends(require_patient), db: Session = Depends(get_db)):
    return api_success(service.add_patient_turn(db, current_user, dialogue_id, payload.transcript).model_dump(mode="json"))


@router.post("/{dialogue_id}/turns/audio")
def add_audio_turn(
    dialogue_id: UUID,
    audio_file: UploadFile = File(...),
    client_turn_id: str | None = Form(default=None),
    current_user: User = Depends(require_patient),
    db: Session = Depends(get_db),
):
    # Persist first so the therapist review can always replay the original response.
    service.get_dialogue(db, current_user, dialogue_id)
    asset = save_upload(db, current_user, audio_file, FileType.training_audio)
    try:
        transcription = transcribe_with_fallback(asset.storage_path)
    except ASRProviderError as exc:
        raise HTTPException(status_code=422, detail=exc.message) from exc
    return api_success(
        service.add_patient_turn(
            db,
            current_user,
            dialogue_id,
            transcription.text,
            audio_file_id=asset.id,
            asr_provider=transcription.provider_name,
            client_turn_id=client_turn_id,
        ).model_dump(mode="json")
    )
