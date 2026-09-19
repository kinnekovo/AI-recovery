from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.algorithm_config import config_entry, config_value, range_bounds
from app.core.config import get_settings
from app.core.observability import log_event
from app.core.redaction import provider_error_summary
from app.integrations.acoustic_analysis.provider import get_acoustic_analysis_provider
from app.integrations.asr.provider import ASRProviderError, transcribe_with_fallback
from app.integrations.llm.provider import get_llm_scoring_provider
from app.modules.attempts.model import AnalysisStatus, Attempt
from app.modules.evaluations.model import (
    AttemptEvaluation,
    EvaluationMetric,
    EvaluationSource,
    ScenarioExpressionReview,
)
from app.modules.evaluations.service import generate_process_evaluation, save_process_evaluation
from app.modules.files.model import FileAsset
from app.modules.files.service import public_url
from app.modules.pronunciation.service import analyze_attempt_pronunciation, get_attempt_pronunciation
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
        _write_repeat_v3_shadow_nonblocking(db, attempt)
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
        _write_repeat_v3_shadow_nonblocking(db, attempt)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"语音识别失败：{exc.message}") from exc
    transcript = asr_result.text
    if asr_result.provider_name == "mock":
        # A fallback transcript is useful for diagnostics, but it cannot support a
        # patient-facing communication conclusion or a rehabilitation trend.
        attempt.analysis_status = AnalysisStatus.failed
        attempt.audio_quality = "unusable"
        attempt.analysis_error_code = "asr:mock_provider"
        attempt.analysis_error_message = "正式评分需要可用的语音识别服务"
        db.commit()
        _write_repeat_v3_shadow_nonblocking(db, attempt)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="语音识别服务暂不可用，未生成正式场景结论，请稍后重试。",
        )
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
        _write_repeat_v3_shadow_nonblocking(db, attempt)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="声学分析失败，请稍后重试") from exc
    if acoustic_provider.provider_name == "mock":
        attempt.analysis_status = AnalysisStatus.failed
        attempt.audio_quality = "unusable"
        attempt.analysis_error_code = "acoustic:mock_provider"
        attempt.analysis_error_message = "正式评分需要启用本地声学分析"
        db.commit()
        _write_repeat_v3_shadow_nonblocking(db, attempt)
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="正式评分需要启用本地声学分析。")
    if acoustic.quality_status != "pass":
        attempt.analysis_status = AnalysisStatus.failed
        attempt.audio_quality = acoustic.quality_status
        reason = _quality_reason_message(acoustic.quality_reason)
        attempt.analysis_error_code = f"audio_quality:{acoustic.quality_reason}"[:80]
        attempt.analysis_error_message = reason[:255]
        db.commit()
        _write_repeat_v3_shadow_nonblocking(db, attempt)
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
    pronunciation = None
    try:
        pronunciation = analyze_attempt_pronunciation(
            db,
            attempt,
            template,
            transcript,
            process_evaluation.script_accuracy,
        )
    except Exception as exc:
        log_event(
            "error",
            "analysis",
            "pronunciation_shadow_failed",
            attempt_id=str(attempt.id),
            error_message=provider_error_summary("精细发音影子评估失败", exc),
        )
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
        pronunciation_shadow_score=_pronunciation_shadow_score(process_evaluation, pronunciation)
        if get_settings().pronunciation_shadow_mode
        else None,
        pronunciation_coverage=pronunciation.coverage if pronunciation and get_settings().pronunciation_shadow_mode else None,
        pronunciation_status=pronunciation.status if pronunciation else "failed",
        pronunciation_confidence=pronunciation.confidence if pronunciation and get_settings().pronunciation_shadow_mode else None,
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
    if template.task_type.value == "scenario":
        scenario = process_evaluation.details.get("scenario_evaluation") or {}
        db.add(
            ScenarioExpressionReview(
                attempt_id=attempt.id,
                goal_status=scenario.get("goal_status"),
                information_unit_overrides={},
            )
        )
    save_process_evaluation(db, attempt.id, process_evaluation)
    from app.modules.profiles.service import refresh_ability_profile

    refresh_ability_profile(db, task.session.patient_profile_id)
    task.status = TrainingStatus.completed
    db.flush()
    complete_session_if_needed(db, task.session)
    _write_repeat_v3_shadow_nonblocking(db, attempt)
    db.refresh(score)
    return to_training_feedback_read(db, attempt.id, transcript=transcript)


def _write_repeat_v3_shadow_nonblocking(db: Session, attempt: Attempt) -> None:
    """V3 is shadow-only: a failed write cannot retract completed V2 training."""

    try:
        from app.modules.evaluation_runs.repeat_v3 import write_repeat_v3_run

        run = write_repeat_v3_run(db, attempt)
        from app.modules.evaluation_runs.service import resolve_evaluation_write_failure
        resolve_evaluation_write_failure(db, source_type="attempt", source_id=attempt.id, domain="repeat", algorithm_version=run.algorithm_version, run=run)
        analysis = db.scalar(select(AttemptAnalysisResult).where(AttemptAnalysisResult.attempt_id == attempt.id))
        if analysis:
            raw = dict(analysis.raw_model_output or {})
            raw["repeat_v3_write"] = {"status": "adopted", "run_id": str(run.id), "algorithm_version": run.algorithm_version}
            analysis.raw_model_output = raw
            db.commit()
    except Exception as exc:
        db.rollback()
        from app.modules.evaluation_runs.repeat_v3 import REPEAT_V3_VERSION
        from app.modules.evaluation_runs.service import record_evaluation_write_failure
        record_evaluation_write_failure(db, source_type="attempt", source_id=attempt.id, domain="repeat", algorithm_version=REPEAT_V3_VERSION,
            failure_stage="shadow_write")
        analysis = db.scalar(select(AttemptAnalysisResult).where(AttemptAnalysisResult.attempt_id == attempt.id))
        if analysis:
            raw = dict(analysis.raw_model_output or {})
            raw["repeat_v3_write"] = {"status": "retry_required", "attempt_id": str(attempt.id), "error": provider_error_summary("V3 写入失败", exc)}
            analysis.raw_model_output = raw
            db.commit()
        log_event("error", "evaluation_v3", "repeat_v3_write_failed", attempt_id=str(attempt.id), retry_required=True, error_message=provider_error_summary("V3 写入失败", exc))


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
    loudness_unit = details.get("loudness_unit")
    if loudness_unit != "dBFS":
        raise ValueError("正式规则评分要求显式 dBFS 响度单位")
    content_score = round(_clamp(process_evaluation.script_accuracy))
    events = details.get("error_events") or {}
    penalties = config_value("clarity_event_penalties")
    error_penalty = sum(float(events.get(name, 0)) * penalty for name, penalty in penalties.items())
    clarity_score = round(_clamp(100 - error_penalty))
    expression_rate = float(details.get("expression_rate", process_evaluation.speech_rate))
    articulation_rate = float(details.get("articulation_rate", expression_rate))
    expression_range = range_bounds("speech_rate_reference")
    articulation_range = range_bounds("articulation_rate_reference")
    rate_multipliers = config_value("score_rate_distance_multipliers")
    expression_score = _clamp(100 - _distance_from_range(expression_rate, *expression_range) * rate_multipliers["expression"])
    articulation_score = _clamp(100 - _distance_from_range(articulation_rate, *articulation_range) * rate_multipliers["articulation"])
    pause_ratio = float((details.get("pause_metrics") or {}).get("pause_ratio", 0))
    fluency_weights = config_value("fluency_component_weights")
    fluency_score = round(
        _clamp(
            expression_score * fluency_weights["expression"]
            + articulation_score * fluency_weights["articulation"]
            - pause_ratio * config_value("score_pause_ratio_penalty")
        )
    )
    loudness_range = range_bounds("repeat_loudness_reference")
    loudness_score = round(
        _clamp(
            100
            - _distance_from_range(process_evaluation.loudness, *loudness_range)
            * config_value("score_loudness_distance_penalty")
        )
    )
    prompt_dependence_score = round(_clamp(float(details.get("independence_score", 100))))
    task_type = details.get("task_type", "repeat")
    weight_config_name = "scenario_score_weights" if task_type == "scenario" else "repeat_score_weights"
    weights = config_value(weight_config_name)
    overall_score = round(
        content_score * weights["content"]
        + clarity_score * weights["error_control"]
        + fluency_score * weights["fluency"]
        + loudness_score * weights["loudness"]
        + prompt_dependence_score * weights["independence"]
    )
    quality = details.get("acoustic_quality") or {}
    quality_confidence = config_value("score_quality_confidence")
    confidence = round(
        _clamp(
            1.0
            - (quality_confidence["penalty"] if quality.get("snr_db", 60) < quality_confidence["snr_min"] else 0)
            - (quality_confidence["penalty"] if details.get("input_sources", {}).get("asr_provider") in {"mock", "unknown"} else 0),
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
            "speech_rate_reference": list(expression_range),
            "config_version": config_entry(weight_config_name)["version"],
            "maturity": config_entry(weight_config_name)["maturity"],
            "source": config_entry(weight_config_name)["source"],
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
    feedback = build_feedback(metrics, process_evaluation.details)
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
    try:
        pronunciation = get_attempt_pronunciation(db, attempt_id).model_dump(mode="json")
    except HTTPException:
        pronunciation = None
    process_details = analysis.semantic_metrics.get("process_monitoring") if analysis else None
    return TrainingFeedbackRead(
        attempt_id=attempt_id,
        process_metrics=metrics,
        feedback=build_feedback(metrics, process_details),
        transcript=transcript or analysis.asr_text if analysis else transcript,
        audio_url=public_url(attempt.audio_file) if attempt and attempt.audio_file else None,
        process_details=process_details,
        pronunciation=pronunciation,
    )


def _pronunciation_shadow_score(process_evaluation, pronunciation) -> int | None:
    if not pronunciation or pronunciation.status != "completed" or pronunciation.overall_accuracy is None:
        return None
    prosody = pronunciation.prosody_metrics or {}
    prosody_score = 100 if prosody.get("status") == "completed" else 0
    weights = config_value("pronunciation_shadow_composite_weights")
    score = (
        process_evaluation.script_accuracy * weights["process_accuracy"]
        + pronunciation.overall_accuracy * weights["provider_accuracy"]
        + (pronunciation.fluency or 0) * 100 * weights["provider_fluency"]
        + max(0, 100 - process_evaluation.error_count * 10) * weights["event_control"]
        + prosody_score * weights["prosody"]
        + float((process_evaluation.details or {}).get("independence_score", 100)) * weights["independence"]
    )
    return round(max(0, min(100, score)))


def build_feedback(metrics: ProcessMetricsRead, details: dict | None = None) -> list[TrainingFeedbackItem]:
    feedback: list[TrainingFeedbackItem] = []
    details = details or {}
    details = details.get("details") if isinstance(details.get("details"), dict) else details
    scenario = details.get("scenario_evaluation")

    if isinstance(scenario, dict):
        status = scenario.get("goal_status")
        if status == "achieved":
            feedback.append(
                TrainingFeedbackItem(
                    metric="functional_communication",
                    current_performance="这次已经把主要需求表达出来了。",
                    suggestion="继续用自己的方式表达；下次可以再补充一个细节，让对方更容易帮到你。",
                )
            )
        elif status == "partly_achieved":
            feedback.append(
                TrainingFeedbackItem(
                    metric="functional_communication",
                    current_performance="这次已经表达出一部分意思，再补充一点会更清楚。",
                    suggestion="下次先说最想让对方帮你的事，再补充相关信息。",
                )
            )
        else:
            feedback.append(
                TrainingFeedbackItem(
                    metric="functional_communication",
                    current_performance="这次还没有识别到足够的场景信息。",
                    suggestion="可以先说最重要的需求；需要时点击“给我一个提示”。",
                )
            )
        missing = scenario.get("next_information_units") or []
        if missing:
            feedback.append(
                TrainingFeedbackItem(
                    metric="information_units",
                    current_performance=f"下次可以补充：{'、'.join(str(item) for item in missing[:2])}。",
                    suggestion="不用照着固定句子说，能让对方明白就很好。",
                )
            )
        feedback.append(
            TrainingFeedbackItem(
                metric="independence",
                current_performance=(
                    "这次是在没有提示的情况下完成的。"
                    if float((details or {}).get("independence_score", 100)) >= 90
                    else "这次使用了提示，系统已把它记录为训练过程的一部分。"
                ),
                suggestion="下次可以先自己想一想；需要时再使用提示，不必着急。",
            )
        )
    else:
        if metrics.script_accuracy >= config_value("script_accuracy_reference"):
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

    error_reference = config_value("error_count_reference")
    if metrics.error_count <= error_reference["max"]:
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

    speech_min, speech_max = range_bounds("speech_rate_reference")
    if metrics.speech_rate < speech_min:
        feedback.append(
            TrainingFeedbackItem(
                metric="speech_rate",
                current_performance=f"言语速率约为 {metrics.speech_rate:g} 字/min，低于参考范围。",
                suggestion="建议增加连续表达训练，先用熟悉短句做稳定输出。",
            )
        )
    elif metrics.speech_rate > speech_max:
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

    loudness_unit = details.get("loudness_unit")
    if loudness_unit != "dBFS":
        feedback.append(
            TrainingFeedbackItem(
                metric="loudness",
                current_performance="本次响度单位未确认，未生成正式声音状态判断。",
                suggestion="请重新完成一次通过录音质量检查的训练。",
            )
        )
        return feedback
    loudness_min, loudness_max = range_bounds("repeat_loudness_reference")
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
