from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.integrations.pronunciation_assessment.provider import (
    PronunciationAssessmentResult,
    PronunciationProviderError,
    get_pronunciation_provider,
)
from app.modules.attempts.model import Attempt
from app.modules.pronunciation.model import IntelligibilityReview, PronunciationAnalysisResult, PronunciationRevision, PronunciationSegment
from app.modules.pronunciation.prosody import analyze_prosody
from app.modules.pronunciation.schema import (
    PronunciationAnalysisRead,
    PatientPronunciationRead,
    IntelligibilityReviewCreate,
    IntelligibilityReviewRead,
    PronunciationRevisionCreate,
    PronunciationRevisionRead,
    PronunciationSegmentRead,
)
from app.modules.training.model import TaskTemplate
from app.modules.users.model import User


ALGORITHM_VERSION = "rehab-pronunciation-v1-shadow"


def evaluation_mode_for_template(template: TaskTemplate) -> str:
    text_length = len("".join(char for char in template.target_text if char.strip() and char not in "，。！？,.!?、；;："))
    if template.task_type.value == "scenario":
        return "scenario"
    return "paragraph" if text_length > 30 else "sentence"


def analyze_attempt_pronunciation(
    db: Session,
    attempt: Attempt,
    template: TaskTemplate,
    transcript: str,
    process_accuracy: float,
) -> PronunciationAnalysisResult:
    existing = _analysis_query(db, attempt.id)
    if existing:
        return existing
    mode = evaluation_mode_for_template(template)
    prosody = analyze_prosody(attempt.audio_file.storage_path) if attempt.audio_file else {"status": "unavailable", "reason": "audio_missing"}
    provider = get_pronunciation_provider()
    try:
        result = provider.evaluate(attempt.audio_file.storage_path, template.target_text, mode)
    except PronunciationProviderError as exc:
        result = PronunciationAssessmentResult(
            provider=getattr(provider, "provider_name", "unknown"),
            provider_version=getattr(provider, "provider_version", "unknown"),
            evaluation_mode=mode,
            status="failed",
            error_code=exc.code,
            error_message=exc.message,
        )
    proxy = _intelligibility_proxy(process_accuracy, result, prosody)
    coverage = _coverage(process_accuracy, result, prosody)
    analysis = PronunciationAnalysisResult(
        attempt_id=attempt.id,
        provider=result.provider,
        provider_version=result.provider_version,
        evaluation_mode=result.evaluation_mode,
        status=result.status,
        overall_accuracy=result.overall_accuracy,
        fluency=result.fluency,
        completion=result.completion,
        suggested_score=result.suggested_score,
        intelligibility_proxy=proxy,
        confidence=result.confidence,
        coverage=coverage,
        prosody_metrics=prosody,
        raw_provider_output=result.raw_output,
        algorithm_version=ALGORITHM_VERSION,
        error_code=result.error_code,
        error_message=result.error_message,
    )
    db.add(analysis)
    db.flush()
    for item in result.segments:
        db.add(
            PronunciationSegment(
                analysis_id=analysis.id,
                level=item.level,
                ordinal=item.ordinal,
                reference_text=item.reference_text,
                recognized_text=item.recognized_text,
                start_ms=item.start_ms,
                end_ms=item.end_ms,
                accuracy=item.accuracy,
                fluency=item.fluency,
                match_type=item.match_type,
                reference_tone=item.reference_tone,
                recognized_tone=item.recognized_tone,
                tone_correct=item.tone_correct,
                provider_payload=item.payload,
            )
        )
    db.flush()
    return analysis


def get_attempt_pronunciation(db: Session, attempt_id: UUID) -> PronunciationAnalysisRead:
    analysis = _analysis_query(db, attempt_id)
    if not analysis:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="本次训练尚无精细发音评估结果")
    return to_read(analysis)


def get_patient_attempt_pronunciation(db: Session, attempt_id: UUID) -> PatientPronunciationRead:
    analysis = _analysis_query(db, attempt_id)
    if not analysis:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="本次训练尚无精细发音评估结果")
    return PatientPronunciationRead(
        attempt_id=analysis.attempt_id,
        status=analysis.status,
        overall_accuracy=analysis.overall_accuracy,
        fluency=analysis.fluency,
        completion=analysis.completion,
        intelligibility_proxy=analysis.intelligibility_proxy,
        confidence=analysis.confidence,
        coverage=analysis.coverage,
        prosody_metrics=analysis.prosody_metrics,
        error_code=analysis.error_code,
        error_message=analysis.error_message,
        segments=[PronunciationSegmentRead.model_validate(item) for item in analysis.segments],
        created_at=analysis.created_at,
    )


def add_revision(
    db: Session,
    analysis_id: UUID,
    reviewer: User,
    payload: PronunciationRevisionCreate,
) -> PronunciationAnalysisRead:
    analysis = _analysis_by_id(db, analysis_id)
    segment = None
    if payload.segment_id:
        segment = db.get(PronunciationSegment, payload.segment_id)
        if not segment or segment.analysis_id != analysis.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="发音片段不存在")
    original = _original_value(analysis, segment, payload.metric_name)
    if set(payload.revised_value) != {payload.metric_name}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="修正值必须只包含当前修正指标")
    if payload.judgment == "confirmed" and payload.revised_value != original:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="确认操作不能改变原始值")
    revision = PronunciationRevision(
        analysis_id=analysis.id,
        segment_id=segment.id if segment else None,
        metric_name=payload.metric_name,
        original_value=original,
        revised_value=payload.revised_value,
        judgment=payload.judgment,
        error_category=payload.error_category,
        reason=payload.reason,
        reviewed_by_user_id=reviewer.id,
    )
    analysis.review_status = "in_review"
    analysis.reviewed_by_user_id = reviewer.id
    db.add(revision)
    db.commit()
    return to_read(_analysis_by_id(db, analysis.id))


def complete_review(db: Session, analysis_id: UUID, reviewer: User) -> PronunciationAnalysisRead:
    analysis = _analysis_by_id(db, analysis_id)
    analysis.review_status = "completed"
    analysis.reviewed_by_user_id = reviewer.id
    db.commit()
    return to_read(_analysis_by_id(db, analysis.id))


def add_intelligibility_review(
    db: Session,
    analysis_id: UUID,
    reviewer: User,
    payload: IntelligibilityReviewCreate,
) -> PronunciationAnalysisRead:
    analysis = _analysis_by_id(db, analysis_id)
    db.add(
        IntelligibilityReview(
            analysis_id=analysis.id,
            listener_role=payload.listener_role,
            listener_transcript=payload.listener_transcript,
            understood_percent=payload.understood_percent,
            playback_count=payload.playback_count,
            listening_environment=payload.listening_environment,
            notes=payload.notes,
            recorded_by_user_id=reviewer.id,
        )
    )
    analysis.review_status = "in_review"
    analysis.reviewed_by_user_id = reviewer.id
    db.commit()
    return to_read(_analysis_by_id(db, analysis.id))


def get_analysis_attempt_id(db: Session, analysis_id: UUID) -> UUID:
    return _analysis_by_id(db, analysis_id).attempt_id


def _analysis_query(db: Session, attempt_id: UUID) -> PronunciationAnalysisResult | None:
    return db.scalar(
        select(PronunciationAnalysisResult)
        .where(PronunciationAnalysisResult.attempt_id == attempt_id)
        .options(
            selectinload(PronunciationAnalysisResult.segments),
            selectinload(PronunciationAnalysisResult.revisions),
            selectinload(PronunciationAnalysisResult.intelligibility_reviews),
        )
    )


def _analysis_by_id(db: Session, analysis_id: UUID) -> PronunciationAnalysisResult:
    value = db.scalar(
        select(PronunciationAnalysisResult)
        .where(PronunciationAnalysisResult.id == analysis_id)
        .options(
            selectinload(PronunciationAnalysisResult.segments),
            selectinload(PronunciationAnalysisResult.revisions),
            selectinload(PronunciationAnalysisResult.intelligibility_reviews),
        )
    )
    if not value:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="精细发音评估不存在")
    return value


def _intelligibility_proxy(process_accuracy: float, result: PronunciationAssessmentResult, prosody: dict) -> float | None:
    if result.status != "completed" or result.overall_accuracy is None:
        return None
    quality = 100.0 if prosody.get("status") == "completed" else 70.0
    completion = (result.completion or 0) * 100
    return round(process_accuracy * 0.4 + result.overall_accuracy * 0.35 + completion * 0.15 + quality * 0.1, 2)


def _coverage(process_accuracy: float, result: PronunciationAssessmentResult, prosody: dict) -> float:
    value = 0.2 if process_accuracy >= 0 else 0.0
    if result.status == "completed":
        value += 0.55
    if prosody.get("status") == "completed":
        value += 0.25
    return round(value, 2)


def _original_value(analysis: PronunciationAnalysisResult, segment: PronunciationSegment | None, metric_name: str) -> dict:
    if segment:
        allowed_metrics = {"accuracy", "fluency", "match_type", "reference_tone", "recognized_tone", "tone_correct"}
        if metric_name not in allowed_metrics:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="不支持修正该片段指标")
        return {metric_name: getattr(segment, metric_name)}
    if metric_name not in {"overall_accuracy", "fluency", "completion", "intelligibility_proxy"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="不支持修正该总体指标")
    return {metric_name: getattr(analysis, metric_name)}


def to_read(analysis: PronunciationAnalysisResult) -> PronunciationAnalysisRead:
    return PronunciationAnalysisRead(
        id=analysis.id,
        attempt_id=analysis.attempt_id,
        provider=analysis.provider,
        provider_version=analysis.provider_version,
        evaluation_mode=analysis.evaluation_mode,
        status=analysis.status,
        overall_accuracy=analysis.overall_accuracy,
        fluency=analysis.fluency,
        completion=analysis.completion,
        suggested_score=analysis.suggested_score,
        intelligibility_proxy=analysis.intelligibility_proxy,
        confidence=analysis.confidence,
        coverage=analysis.coverage,
        prosody_metrics=analysis.prosody_metrics,
        algorithm_version=analysis.algorithm_version,
        error_code=analysis.error_code,
        error_message=analysis.error_message,
        review_status=analysis.review_status,
        reviewed_by_user_id=analysis.reviewed_by_user_id,
        segments=[PronunciationSegmentRead.model_validate(item) for item in analysis.segments],
        revisions=[PronunciationRevisionRead.model_validate(item) for item in analysis.revisions],
        intelligibility_reviews=[IntelligibilityReviewRead.model_validate(item) for item in analysis.intelligibility_reviews],
        created_at=analysis.created_at,
    )
