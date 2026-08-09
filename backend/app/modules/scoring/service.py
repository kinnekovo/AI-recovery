from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.integrations.acoustic_analysis.provider import get_acoustic_analysis_provider
from app.integrations.asr.provider import get_asr_provider
from app.integrations.llm.provider import get_llm_scoring_provider
from app.modules.attempts.model import AnalysisStatus, Attempt
from app.modules.evaluations.model import AttemptEvaluation, EvaluationMetric, EvaluationSource
from app.modules.evaluations.service import generate_process_evaluation, save_process_evaluation
from app.modules.files.model import FileAsset
from app.modules.scoring.model import AttemptAnalysisResult, AttemptScore
from app.modules.scoring.schema import (
    ProcessMetricsRead,
    ScoreDimensions,
    ScoreFeedback,
    ScoreRead,
    TrainingFeedbackItem,
    TrainingFeedbackRead,
)
from app.modules.training.model import SessionTask, TaskTemplate
from app.modules.training.service import complete_session_if_needed


def analyze_attempt(db: Session, attempt: Attempt) -> TrainingFeedbackRead:
    if not attempt.audio_file_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请先上传录音")
    if attempt.score:
        ensure_process_evaluation(db, attempt)
        return to_training_feedback_read(db, attempt.id, transcript=None)
    audio = db.get(FileAsset, attempt.audio_file_id)
    task = db.get(SessionTask, attempt.session_task_id)
    template = db.get(TaskTemplate, task.task_template_id) if task else None
    if not audio or not task or not template:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="评分上下文不存在")

    # Ensure metric definitions exist before the score transaction starts writing attempt data.
    from app.modules.evaluations.service import ensure_default_metrics

    ensure_default_metrics(db)
    transcript = get_asr_provider().transcribe(audio.storage_path)
    acoustic = get_acoustic_analysis_provider().analyze(audio.storage_path)
    process_evaluation = generate_process_evaluation(template, transcript, acoustic)
    result = get_llm_scoring_provider().evaluate(template.target_text, transcript, template.task_type.value)
    analysis = AttemptAnalysisResult(
        attempt_id=attempt.id,
        asr_text=transcript,
        acoustic_metrics={
            "quality": "mock_pass",
            "speaking_duration_seconds": acoustic.speaking_duration_seconds,
            "loudness_dba": acoustic.loudness_dba,
            "long_pause_over_3s_count": acoustic.long_pause_over_3s_count,
        },
        semantic_metrics={
            "target_text": template.target_text,
            "process_monitoring": process_evaluation.model_dump(mode="json"),
        },
        raw_model_output={"llm_scoring": result},
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
    save_process_evaluation(db, attempt.id, process_evaluation)
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
                    AttemptEvaluation.evaluation_source == EvaluationSource.mock_ai,
                )
            ).all()
        )
        if existing_count >= 4:
            return

        db.query(AttemptEvaluation).filter(
            AttemptEvaluation.attempt_id == attempt.id,
            AttemptEvaluation.metric_id.in_(metric_ids),
            AttemptEvaluation.evaluation_source == EvaluationSource.mock_ai,
        ).delete(synchronize_session=False)
        db.flush()
        existing_count = db.scalar(
            select(AttemptEvaluation.id)
            .where(
                AttemptEvaluation.attempt_id == attempt.id,
                AttemptEvaluation.metric_id.in_(metric_ids),
                AttemptEvaluation.evaluation_source == EvaluationSource.mock_ai,
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
    transcript = analysis.asr_text if analysis else get_asr_provider().transcribe(audio.storage_path)
    acoustic = get_acoustic_analysis_provider().analyze(audio.storage_path)
    process_evaluation = generate_process_evaluation(template, transcript, acoustic)
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


def _metric_values(db: Session, attempt_id) -> dict[str, float]:
    rows = db.execute(
        select(EvaluationMetric.name, AttemptEvaluation.value)
        .join(AttemptEvaluation, AttemptEvaluation.metric_id == EvaluationMetric.id)
        .where(
            AttemptEvaluation.attempt_id == attempt_id,
            AttemptEvaluation.evaluation_source == EvaluationSource.mock_ai,
            EvaluationMetric.name.in_(["script_accuracy", "error_count", "speech_rate", "loudness"]),
        )
    ).all()
    return {name: float(value) for name, value in rows}


def to_training_feedback_read(db: Session, attempt_id, transcript: str | None) -> TrainingFeedbackRead:
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
        transcript=transcript,
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

    if 60 <= metrics.loudness <= 78:
        feedback.append(
            TrainingFeedbackItem(
                metric="loudness",
                current_performance=f"响度约为 {metrics.loudness:g} dBA，处于参考范围。",
                suggestion="保持现在的音量和呼吸支持。",
            )
        )
    elif metrics.loudness < 60:
        feedback.append(
            TrainingFeedbackItem(
                metric="loudness",
                current_performance=f"响度约为 {metrics.loudness:g} dBA，偏低。",
                suggestion="建议坐直后再发声，尝试用更稳定的气息把句子说完整。",
            )
        )
    else:
        feedback.append(
            TrainingFeedbackItem(
                metric="loudness",
                current_performance=f"响度约为 {metrics.loudness:g} dBA，偏高。",
                suggestion="建议降低用力程度，保持舒适自然的说话音量。",
            )
        )

    return feedback
