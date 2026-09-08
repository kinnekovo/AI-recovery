from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.observability import log_event
from app.core.redaction import provider_error_summary
from app.integrations.acoustic_analysis.provider import get_acoustic_analysis_provider
from app.integrations.asr.provider import ASRProviderError, transcribe_with_fallback
from app.integrations.llm.provider import get_llm_scoring_provider
from app.modules.attempts.model import AnalysisStatus, Attempt
from app.modules.evaluations.model import AttemptEvaluation, EvaluationMetric, EvaluationSource
from app.modules.evaluations.service import generate_process_evaluation, save_process_evaluation
from app.modules.files.model import FileAsset
from app.modules.files.service import public_url
from app.modules.scoring.model import AttemptAnalysisResult, AttemptScore
from app.modules.scoring.schema import (
    ProcessMetricsRead,
    ScoreDimensions,
    ScoreFeedback,
    ScoreRead,
    TrainingFeedbackItem,
    TrainingFeedbackRead,
)
from app.modules.training.model import SessionTask, TaskTemplate, TrainingStatus
from app.modules.training.service import complete_session_if_needed


def analyze_attempt(db: Session, attempt: Attempt) -> TrainingFeedbackRead:
    if not attempt.audio_file_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请先上传录音")
    if attempt.score:
        ensure_process_evaluation(db, attempt)
        task = db.get(SessionTask, attempt.session_task_id)
        if task and task.session:
            from app.modules.profiles.service import refresh_ability_profile

            refresh_ability_profile(db, task.session.patient_profile_id)
        else:
            db.commit()
        return to_training_feedback_read(db, attempt.id, transcript=None)
    audio = db.get(FileAsset, attempt.audio_file_id)
    task = db.get(SessionTask, attempt.session_task_id)
    template = db.get(TaskTemplate, task.task_template_id) if task else None
    if not audio or not task or not template:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="评分上下文不存在")

    # Ensure metric definitions exist before the score transaction starts writing attempt data.
    from app.modules.evaluations.service import ensure_default_metrics

    ensure_default_metrics(db)
    acoustic_provider = get_acoustic_analysis_provider()
    llm_provider = get_llm_scoring_provider()
    try:
        asr_result = transcribe_with_fallback(audio.storage_path)
    except ASRProviderError as exc:
        attempt.analysis_status = AnalysisStatus.failed
        attempt.analysis_error_code = f"asr:{exc.code}"
        attempt.analysis_error_message = exc.message[:255]
        db.commit()
        log_event(
            "error",
            "analysis",
            "asr_analysis_failed",
            attempt_id=str(attempt.id),
            file_id=str(audio.id),
            error_code=exc.code,
            error_message=exc.message,
        )
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"语音识别失败：{exc.message}") from exc
    transcript = asr_result.text
    try:
        acoustic = acoustic_provider.analyze(audio.storage_path)
    except Exception as exc:
        attempt.analysis_status = AnalysisStatus.failed
        attempt.analysis_error_code = "acoustic:analysis_failed"
        attempt.analysis_error_message = "声学分析失败，请稍后重试"
        db.commit()
        log_event(
            "error",
            "analysis",
            "acoustic_analysis_failed",
            attempt_id=str(attempt.id),
            file_id=str(audio.id),
            provider=getattr(acoustic_provider, "provider_name", "unknown"),
            error_message=provider_error_summary("声学分析失败", exc),
        )
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="声学分析失败，请稍后重试") from exc
    if acoustic_provider.provider_name == "mock":
        attempt.analysis_status = AnalysisStatus.failed
        attempt.audio_quality = "unusable"
        attempt.analysis_error_code = "acoustic:mock_provider"
        attempt.analysis_error_message = "正式评分需要启用本地声学分析"
        db.commit()
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="正式评分需要启用本地声学分析。")
    if acoustic.quality_status != "pass":
        attempt.analysis_status = AnalysisStatus.failed
        attempt.audio_quality = acoustic.quality_status
        reason = _quality_reason_message(acoustic.quality_reason)
        attempt.analysis_error_code = f"audio_quality:{acoustic.quality_reason}"[:80]
        attempt.analysis_error_message = reason[:255]
        db.commit()
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"录音质量不合格，未生成分数：{reason}")
    process_evaluation = generate_process_evaluation(
        template,
        transcript,
        acoustic,
        asr_provider_name=asr_result.provider_name,
        acoustic_provider_name=acoustic_provider.provider_name,
        prompt_level=attempt.prompt_level,
        requested_help=attempt.requested_help,
        start_latency_ms=attempt.start_latency_ms,
        attempt_duration_ms=attempt.duration_ms,
    )
    score_dimensions = build_rule_score_dimensions(process_evaluation)
    llm_feedback = safe_llm_feedback(llm_provider, template.target_text, transcript, template.task_type.value, process_evaluation)
    analysis = AttemptAnalysisResult(
        attempt_id=attempt.id,
        asr_text=transcript,
        acoustic_metrics={
            "quality_status": acoustic.quality_status,
            "quality_reason": acoustic.quality_reason,
            "too_short": acoustic.too_short,
            "too_quiet": acoustic.too_quiet,
            "too_noisy": acoustic.too_noisy,
            "clipped": acoustic.clipped,
            "provider": acoustic_provider.provider_name,
            "requested_provider": getattr(acoustic_provider, "requested_provider", acoustic_provider.provider_name),
            "speaking_duration_seconds": acoustic.speaking_duration_seconds,
            "total_duration_seconds": acoustic.total_duration_seconds,
            "loudness_dba": acoustic.loudness_dba,
            "loudness_dbfs": acoustic.loudness_dbfs,
            "pause_over_1s_count": acoustic.pause_over_1s_count,
            "long_pause_over_3s_count": acoustic.long_pause_over_3s_count,
            "internal_pause_duration_seconds": acoustic.internal_pause_duration_seconds,
            "pause_ratio": acoustic.pause_ratio,
            "longest_pause_seconds": acoustic.longest_pause_seconds,
            "clipping_ratio": acoustic.clipping_ratio,
            "snr_db": acoustic.snr_db,
        },
        semantic_metrics={
            "target_text": template.target_text,
            "process_monitoring": process_evaluation.model_dump(mode="json"),
            "asr_provider": asr_result.provider_name,
            "requested_asr_provider": asr_result.requested_provider,
            "asr_fallback_used": asr_result.fallback_used,
            "asr_error_code": asr_result.error_code,
            "asr_error_message": asr_result.error_message,
        },
        raw_model_output={
            "llm_feedback": llm_feedback,
            "llm_provider": llm_provider.provider_name,
            "requested_llm_provider": getattr(llm_provider, "requested_provider", llm_provider.provider_name),
            "llm_allowed_fields": ["main_strength", "main_issue", "suggestion"],
        },
        provider_version=process_evaluation.details.get("provider_version", "rehab-process-v2"),
    )
    score = AttemptScore(
        attempt_id=attempt.id,
        overall_score=score_dimensions["overall_score"],
        content_score=score_dimensions["content_score"],
        clarity_score=score_dimensions["clarity_score"],
        fluency_score=score_dimensions["fluency_score"],
        loudness_score=score_dimensions["loudness_score"],
        prompt_dependence_score=score_dimensions["prompt_dependence_score"],
        task_type=template.task_type.value,
        scoring_version="rehab-score-v2",
        scoring_config=score_dimensions["scoring_config"],
        confidence=score_dimensions["confidence"],
        is_scorable=True,
        main_strength=llm_feedback["main_strength"],
        main_issue=llm_feedback["main_issue"],
        suggestion=llm_feedback["suggestion"],
    )
    attempt.analysis_status = AnalysisStatus.completed
    attempt.audio_quality = acoustic.quality_status
    attempt.analysis_error_code = None
    attempt.analysis_error_message = None
    db.add(analysis)
    db.add(score)
    db.flush()
    save_process_evaluation(db, attempt.id, process_evaluation)
    from app.modules.profiles.service import refresh_ability_profile

    refresh_ability_profile(db, task.session.patient_profile_id)
    task.status = TrainingStatus.completed
    db.flush()
    complete_session_if_needed(db, task.session)
    db.refresh(score)
    return to_training_feedback_read(db, attempt.id, transcript=transcript)


def ensure_process_evaluation(db: Session, attempt: Attempt) -> None:
    metric_ids = list(
        db.scalars(
            select(EvaluationMetric.id).where(
                EvaluationMetric.name.in_(["script_accuracy", "error_count", "speech_rate", "loudness"])
            )
        )
    )
    if metric_ids:
        existing_count = len(
            db.scalars(
                select(AttemptEvaluation.id).where(
                    AttemptEvaluation.attempt_id == attempt.id,
                    AttemptEvaluation.metric_id.in_(metric_ids),
                    AttemptEvaluation.evaluation_source == EvaluationSource.system_rule,
                )
            ).all()
        )
        if existing_count >= 4:
            return

        db.query(AttemptEvaluation).filter(
            AttemptEvaluation.attempt_id == attempt.id,
            AttemptEvaluation.metric_id.in_(metric_ids),
            AttemptEvaluation.evaluation_source == EvaluationSource.system_rule,
        ).delete(synchronize_session=False)
        db.flush()
        existing_count = db.scalar(
            select(AttemptEvaluation.id)
            .where(
                AttemptEvaluation.attempt_id == attempt.id,
                AttemptEvaluation.metric_id.in_(metric_ids),
                AttemptEvaluation.evaluation_source == EvaluationSource.system_rule,
            )
            .limit(1)
        )
        if existing_count:
            return

    audio = db.get(FileAsset, attempt.audio_file_id)
    task = db.get(SessionTask, attempt.session_task_id)
    template = db.get(TaskTemplate, task.task_template_id) if task else None
    analysis = db.scalar(select(AttemptAnalysisResult).where(AttemptAnalysisResult.attempt_id == attempt.id))
    if not audio or not task or not template:
        return
    acoustic_provider = get_acoustic_analysis_provider()
    try:
        asr_result = None if analysis else transcribe_with_fallback(audio.storage_path)
    except ASRProviderError as exc:
        log_event(
            "error",
            "analysis",
            "process_evaluation_asr_failed",
            attempt_id=str(attempt.id),
            file_id=str(audio.id),
            error_code=exc.code,
            error_message=exc.message,
        )
        return
    transcript = analysis.asr_text if analysis else asr_result.text
    try:
        acoustic = acoustic_provider.analyze(audio.storage_path)
    except Exception as exc:
        log_event(
            "error",
            "analysis",
            "process_evaluation_backfill_failed",
            attempt_id=str(attempt.id),
            file_id=str(audio.id),
            provider=getattr(acoustic_provider, "provider_name", "unknown"),
            error_message=provider_error_summary("过程指标补生成失败", exc),
        )
        return
    if acoustic.quality_status != "pass" or acoustic_provider.provider_name == "mock":
        return
    process_evaluation = generate_process_evaluation(
        template,
        transcript,
        acoustic,
        asr_provider_name="stored" if analysis else asr_result.provider_name,
        acoustic_provider_name=acoustic_provider.provider_name,
        prompt_level=attempt.prompt_level,
        requested_help=attempt.requested_help,
        start_latency_ms=attempt.start_latency_ms,
        attempt_duration_ms=attempt.duration_ms,
    )
    save_process_evaluation(db, attempt.id, process_evaluation)
    db.commit()


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


def build_rule_score_dimensions(process_evaluation) -> dict[str, int]:
    details = getattr(process_evaluation, "details", None) or {}
    content_score = round(_clamp(process_evaluation.script_accuracy))
    events = details.get("error_events") or {}
    error_penalty = (
        events.get("meaningless_repetition", 0) * 8
        + events.get("self_correction", 0) * 4
        + events.get("long_pause_over_3s", 0) * 10
        + events.get("filler", 0) * 3
    )
    clarity_score = round(_clamp(100 - error_penalty))
    expression_rate = float(details.get("expression_rate", process_evaluation.speech_rate))
    articulation_rate = float(details.get("articulation_rate", expression_rate))
    expression_score = _clamp(100 - _distance_from_range(expression_rate, 180, 240) * 0.7)
    articulation_score = _clamp(100 - _distance_from_range(articulation_rate, 180, 260) * 0.55)
    pause_ratio = float((details.get("pause_metrics") or {}).get("pause_ratio", 0))
    fluency_score = round(_clamp(expression_score * 0.6 + articulation_score * 0.4 - pause_ratio * 35))
    loudness_unit = details.get("loudness_unit", "dBA")
    loudness_range = (-35, -12) if loudness_unit == "dBFS" else (60, 78)
    loudness_score = round(_clamp(100 - _distance_from_range(process_evaluation.loudness, *loudness_range) * 3))
    prompt_dependence_score = round(_clamp(float(details.get("independence_score", 100))))
    task_type = details.get("task_type", "repeat")
    weights = (
        {"content": 0.30, "error_control": 0.15, "fluency": 0.30, "loudness": 0.10, "independence": 0.15}
        if task_type == "scenario"
        else {"content": 0.45, "error_control": 0.15, "fluency": 0.25, "loudness": 0.10, "independence": 0.05}
    )
    overall_score = round(
        content_score * weights["content"]
        + clarity_score * weights["error_control"]
        + fluency_score * weights["fluency"]
        + loudness_score * weights["loudness"]
        + prompt_dependence_score * weights["independence"]
    )
    quality = details.get("acoustic_quality") or {}
    confidence = round(
        _clamp(
            1.0
            - (0.15 if quality.get("snr_db", 60) < 15 else 0)
            - (0.15 if details.get("input_sources", {}).get("asr_provider") in {"mock", "unknown"} else 0),
            0,
            1,
        ),
        2,
    )
    return {
        "overall_score": overall_score,
        "content_score": content_score,
        "clarity_score": clarity_score,
        "fluency_score": fluency_score,
        "loudness_score": loudness_score,
        "prompt_dependence_score": prompt_dependence_score,
        "confidence": confidence,
        "scoring_config": {
            "version": "rehab-score-v2",
            "weights": weights,
            "task_type": task_type,
            "loudness_unit": loudness_unit,
            "speech_rate_reference": [180, 240],
        },
    }


def safe_llm_feedback(provider, target_text: str, transcript: str, task_type: str, process_evaluation) -> dict[str, str]:
    fallback = rule_feedback_summary(process_evaluation)
    if getattr(provider, "provider_name", "mock") == "mock":
        return fallback
    try:
        raw = provider.evaluate(target_text, transcript, task_type)
    except Exception:
        return fallback
    if not isinstance(raw, dict):
        return fallback
    result: dict[str, str] = {}
    for field in ("main_strength", "main_issue", "suggestion"):
        value = raw.get(field)
        if not isinstance(value, str) or not value.strip():
            return fallback
        result[field] = value.strip()[:255] if field != "suggestion" else value.strip()[:1000]
    return result


def rule_feedback_summary(process_evaluation) -> dict[str, str]:
    metrics = ProcessMetricsRead(
        script_accuracy=process_evaluation.script_accuracy,
        error_count=process_evaluation.error_count,
        speech_rate=process_evaluation.speech_rate,
        loudness=process_evaluation.loudness,
    )
    feedback = build_feedback(metrics)
    return {
        "main_strength": feedback[0].current_performance,
        "main_issue": feedback[1].current_performance if len(feedback) > 1 else "本次过程性指标已生成。",
        "suggestion": feedback[0].suggestion,
    }


def _clamp(value: float, minimum: float = 0, maximum: float = 100) -> float:
    return max(minimum, min(maximum, value))


def _distance_from_range(value: float, minimum: float, maximum: float) -> float:
    if minimum <= value <= maximum:
        return 0
    return minimum - value if value < minimum else value - maximum


def _quality_reason_message(reason: str) -> str:
    labels = {
        "empty_audio": "未检测到有效录音",
        "too_short": "有效发声时间过短",
        "too_quiet": "录音音量过低",
        "too_noisy": "背景噪声过大",
        "clipped": "录音出现明显削波失真",
    }
    matched = [label for key, label in labels.items() if key in reason]
    return "、".join(matched) if matched else "录音未通过质量检查"


def _metric_values(db: Session, attempt_id) -> dict[str, float]:
    rows = db.execute(
        select(EvaluationMetric.name, AttemptEvaluation.value)
        .join(AttemptEvaluation, AttemptEvaluation.metric_id == EvaluationMetric.id)
        .where(
            AttemptEvaluation.attempt_id == attempt_id,
            AttemptEvaluation.evaluation_source == EvaluationSource.system_rule,
            EvaluationMetric.name.in_(["script_accuracy", "error_count", "speech_rate", "loudness"]),
        )
    ).all()
    return {name: float(value) for name, value in rows}


def to_training_feedback_read(db: Session, attempt_id, transcript: str | None) -> TrainingFeedbackRead:
    attempt = db.get(Attempt, attempt_id)
    analysis = db.scalar(select(AttemptAnalysisResult).where(AttemptAnalysisResult.attempt_id == attempt_id))
    values = _metric_values(db, attempt_id)
    metrics = ProcessMetricsRead(
        script_accuracy=values.get("script_accuracy", 0.0),
        error_count=values.get("error_count", 0.0),
        speech_rate=values.get("speech_rate", 0.0),
        loudness=values.get("loudness", 0.0),
    )
    return TrainingFeedbackRead(
        attempt_id=attempt_id,
        process_metrics=metrics,
        feedback=build_feedback(metrics),
        transcript=transcript or analysis.asr_text if analysis else transcript,
        audio_url=public_url(attempt.audio_file) if attempt and attempt.audio_file else None,
        process_details=analysis.semantic_metrics.get("process_monitoring") if analysis else None,
    )


def build_feedback(metrics: ProcessMetricsRead) -> list[TrainingFeedbackItem]:
    feedback: list[TrainingFeedbackItem] = []

    if metrics.script_accuracy >= 90:
        feedback.append(
            TrainingFeedbackItem(
                metric="script_accuracy",
                current_performance=f"脚本完成度较好，正确生成比例约为 {metrics.script_accuracy:g}%。",
                suggestion="继续保持清晰稳定的跟读节奏，下一次可以尝试减少停顿。",
            )
        )
    else:
        feedback.append(
            TrainingFeedbackItem(
                metric="script_accuracy",
                current_performance=f"脚本完成度还有提升空间，正确生成比例约为 {metrics.script_accuracy:g}%。",
                suggestion="建议先分短句练习，再逐步合成完整句子。",
            )
        )

    if metrics.error_count <= 1:
        feedback.append(
            TrainingFeedbackItem(
                metric="error_count",
                current_performance=f"本次明显错误较少，记录到 {metrics.error_count:g} 次。",
                suggestion="保持当前表达方式，注意减少不必要的重复和插入语。",
            )
        )
    else:
        feedback.append(
            TrainingFeedbackItem(
                metric="error_count",
                current_performance=f"本次记录到 {metrics.error_count:g} 次错误或停顿事件。",
                suggestion="建议放慢开始速度，先想好关键词，再连续说出完整表达。",
            )
        )

    if metrics.speech_rate < 180:
        feedback.append(
            TrainingFeedbackItem(
                metric="speech_rate",
                current_performance=f"言语速率约为 {metrics.speech_rate:g} 字/min，低于参考范围。",
                suggestion="建议增加连续表达训练，先用熟悉短句做稳定输出。",
            )
        )
    elif metrics.speech_rate > 240:
        feedback.append(
            TrainingFeedbackItem(
                metric="speech_rate",
                current_performance=f"言语速率约为 {metrics.speech_rate:g} 字/min，高于参考范围。",
                suggestion="建议稍微放慢语速，优先保证每个词都说清楚。",
            )
        )
    else:
        feedback.append(
            TrainingFeedbackItem(
                metric="speech_rate",
                current_performance=f"言语速率约为 {metrics.speech_rate:g} 字/min，处于参考范围。",
                suggestion="继续保持自然语速，后续可以增加更长句子的练习。",
            )
        )

    loudness_unit = "dBFS" if metrics.loudness < 0 else "dBA"
    loudness_min, loudness_max = (-35, -12) if loudness_unit == "dBFS" else (60, 78)
    if loudness_min <= metrics.loudness <= loudness_max:
        feedback.append(
            TrainingFeedbackItem(
                metric="loudness",
                current_performance=f"响度约为 {metrics.loudness:g} {loudness_unit}，处于工程参考范围。",
                suggestion="保持现在的音量和呼吸支持。",
            )
        )
    elif metrics.loudness < loudness_min:
        feedback.append(
            TrainingFeedbackItem(
                metric="loudness",
                current_performance=f"响度约为 {metrics.loudness:g} {loudness_unit}，偏低。",
                suggestion="建议坐直后再发声，尝试用更稳定的气息把句子说完整。",
            )
        )
    else:
        feedback.append(
            TrainingFeedbackItem(
                metric="loudness",
                current_performance=f"响度约为 {metrics.loudness:g} {loudness_unit}，偏高。",
                suggestion="建议降低用力程度，保持舒适自然的说话音量。",
            )
        )

    return feedback
