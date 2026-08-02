from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.integrations.asr.provider import get_asr_provider
from app.integrations.llm.provider import get_llm_scoring_provider
from app.modules.attempts.model import AnalysisStatus, Attempt
from app.modules.files.model import FileAsset
from app.modules.scoring.model import AttemptAnalysisResult, AttemptScore
from app.modules.scoring.schema import ScoreDimensions, ScoreFeedback, ScoreRead
from app.modules.training.model import SessionTask, TaskTemplate
from app.modules.training.service import complete_session_if_needed


def analyze_attempt(db: Session, attempt: Attempt) -> ScoreRead:
    if not attempt.audio_file_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请先上传录音")
    if attempt.score:
        return to_score_read(attempt.score, transcript=None)
    audio = db.get(FileAsset, attempt.audio_file_id)
    task = db.get(SessionTask, attempt.session_task_id)
    template = db.get(TaskTemplate, task.task_template_id) if task else None
    if not audio or not task or not template:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="评分上下文不存在")

    transcript = get_asr_provider().transcribe(audio.storage_path)
    result = get_llm_scoring_provider().evaluate(template.target_text, transcript, template.task_type.value)
    analysis = AttemptAnalysisResult(
        attempt_id=attempt.id,
        asr_text=transcript,
        acoustic_metrics={"quality": "mock_pass"},
        semantic_metrics={"target_text": template.target_text},
        raw_model_output=result,
    )
    score = AttemptScore(
        attempt_id=attempt.id,
        overall_score=result["overall_score"],
        content_score=result["content_score"],
        clarity_score=result["clarity_score"],
        fluency_score=result["fluency_score"],
        loudness_score=result["loudness_score"],
        prompt_dependence_score=result["prompt_dependence_score"],
        main_strength=result["main_strength"],
        main_issue=result["main_issue"],
        suggestion=result["suggestion"],
    )
    attempt.analysis_status = AnalysisStatus.completed
    db.add(analysis)
    db.add(score)
    db.flush()
    complete_session_if_needed(db, task.session)
    db.refresh(score)
    return to_score_read(score, transcript=transcript)


def to_score_read(score: AttemptScore, transcript: str | None) -> ScoreRead:
    return ScoreRead(
        attempt_id=score.attempt_id,
        overall_score=score.overall_score,
        dimensions=ScoreDimensions(
            content=score.content_score,
            clarity=score.clarity_score,
            fluency=score.fluency_score,
            loudness=score.loudness_score,
            prompt_dependence=score.prompt_dependence_score,
        ),
        feedback=ScoreFeedback(strength=score.main_strength, improve=score.suggestion),
        transcript=transcript,
    )
