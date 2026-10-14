"""V3.1 repeat-domain mapping from already persisted V2 analysis evidence."""

import hashlib
import json
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.algorithm_config import config_entry
from app.core.observability import log_event
from app.modules.attempts.model import Attempt
from app.modules.evaluation_runs.model import EvaluationReviewRevision, EvaluationRun
from app.modules.evaluation_runs.schema import (
    EvaluationDimensionResultCreate,
    EvaluationRunCreate,
    InputProvenanceSnapshot,
    QualityGateSnapshot,
)
from app.modules.evaluation_runs.service import adopt_candidate_run, create_candidate_run, get_adopted_run, get_run, get_run_for_professional, source_patient_profile_id
from app.modules.evaluation_runs.schema import EvaluationReviewRevisionCreate
from app.modules.evaluations.evidence_gate import process_evidence_gate
from app.modules.pronunciation.model import PronunciationAnalysisResult
from app.modules.scoring.model import AttemptAnalysisResult, AttemptScore
from app.modules.training.model import SessionTask, TaskTemplate
from app.modules.users.model import PatientProfile, User


REPEAT_V3_VERSION = "repeat-eval-v3.0"


def _fingerprint(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _status_from_gate(gate, analysis: AttemptAnalysisResult | None) -> tuple[str, bool, list[str], list[str]]:
    if not analysis:
        return "unscorable", False, ["analysis_missing"], ["未找到 V2 分析证据，无法生成 V3 跟读结果。"]
    if gate.eligible:
        return "formal", True, [], ["工程参考区间未经过临床校准；本结果不等同于诊断或临床量表。"]
    reasons = list(gate.reasons)
    if "quality_not_passed" in reasons:
        return "unscorable", False, reasons, ["录音质量未通过，保留审计记录但不生成正式结果。"]
    return "review_required", False, reasons, ["R0 证据门控未通过，需要重录、排障或专业复核。"]


def _shadow_dimension(pronunciation: PronunciationAnalysisResult | None) -> EvaluationDimensionResultCreate:
    if not pronunciation:
        return EvaluationDimensionResultCreate(
            dimension_code="articulation_evidence", status="not_observed", limitations=["本次未观察到精细发音 shadow 证据。"]
        )
    evidence = {
        "provider": pronunciation.provider,
        "provider_version": pronunciation.provider_version,
        "algorithm_version": pronunciation.algorithm_version,
        "coverage": pronunciation.coverage,
        "intelligibility_proxy": pronunciation.intelligibility_proxy,
        "prosody_metrics": pronunciation.prosody_metrics,
        "shadow_only": True,
    }
    if pronunciation.status in {"disabled", "failed"}:
        return EvaluationDimensionResultCreate(
            dimension_code="articulation_evidence", status="unavailable", evidence_snapshot=evidence,
            limitations=["精细发音 Provider disabled/failed；不可用不等于 0，也不阻止其他核心跟读维度。"],
        )
    return EvaluationDimensionResultCreate(
        dimension_code="articulation_evidence", level="shadow_observed", status="measured", evidence_snapshot=evidence,
        limitations=["该维度为 E1 shadow 证据；coverage 仅表示覆盖度，intelligibility_proxy 不是临床构音分，不能进入正式画像或调难。"],
    )


def build_repeat_v3_payload(db: Session, attempt: Attempt, review_override: dict | None = None) -> EvaluationRunCreate:
    analysis = db.scalar(select(AttemptAnalysisResult).where(AttemptAnalysisResult.attempt_id == attempt.id))
    task = db.get(SessionTask, attempt.session_task_id)
    template = db.get(TaskTemplate, task.task_template_id) if task else None
    if not task or not template:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="跟读 V3 上下文不存在")
    semantic = analysis.semantic_metrics if analysis else {}
    process = (semantic.get("process_monitoring") or {}) if analysis else {}
    details = (process.get("details") or {}) if isinstance(process, dict) else {}
    gate = process_evidence_gate(attempt.audio_quality, semantic, analysis.provider_version if analysis else None)
    result_status, profile_eligibility, ineligibility, limitations = _status_from_gate(gate, analysis)
    acoustic = (analysis.acoustic_metrics or {}) if analysis else {}
    pronunciation = db.scalar(select(PronunciationAnalysisResult).where(PronunciationAnalysisResult.attempt_id == attempt.id))
    pause = details.get("pause_metrics") or {}
    mismatch = details.get("script_mismatch_events") or {}
    loudness = process.get("loudness") if isinstance(process, dict) else None
    loudness_ok = gate.loudness_unit == "dBFS" and loudness is not None
    dimensions = [
        EvaluationDimensionResultCreate(
            dimension_code="content_reproduction", value=process.get("script_accuracy") if isinstance(process, dict) else None,
            level="transcription_difference", unit="%", status="measured" if analysis else "unavailable",
            evidence_snapshot={"content_reproduction_rate": process.get("script_accuracy"), "omission_count": mismatch.get("omission"), "substitution_count": mismatch.get("substitution"), "addition_count": mismatch.get("addition"), "alignment_positions": details.get("alignment_events", []), "alignment_algorithm_version": details.get("provider_version"), "asr_text": analysis.asr_text if analysis else None, "target_text_snapshot": template.target_text},
            limitations=["内容复现/转写差异受 ASR 影响，不命名为构音准确率或发音错误。"],
        ),
        EvaluationDimensionResultCreate(
            dimension_code="fluency_efficiency", value=details.get("expression_rate") if analysis else None,
            unit="char/min", status="measured" if analysis else "unavailable",
            evidence_snapshot={"expression_rate": details.get("expression_rate"), "articulation_rate": details.get("articulation_rate"), "articulation_rate_status": "measured" if details.get("articulation_rate") is not None else "unavailable", "pause_ratio": pause.get("pause_ratio"), "longest_pause": pause.get("longest_pause_seconds"), "pause_over_1s_count": pause.get("pause_over_1s_count"), "pause_over_3s_count": pause.get("pause_over_3s_count"), "valid_character_count": details.get("valid_word_count"), "speaking_duration_seconds": details.get("speaking_duration_seconds"), "calculation_version": details.get("provider_version")},
            limitations=["速率参考仅为 engineering_reference，不表示普遍正常范围。"],
        ),
        EvaluationDimensionResultCreate(
            dimension_code="disfluency_events", level="observed" if analysis else None, status="measured" if analysis else "unavailable",
            evidence_snapshot={"events": details.get("error_events", {}), "repetition_positions": details.get("repetition_events", []), "self_correction_positions": details.get("self_correction_events", []), "rule_version": details.get("provider_version")},
            limitations=["自我修正不一律作为负面错误；事件不被合成为临床流利度分数。"],
        ),
        EvaluationDimensionResultCreate(
            dimension_code="voice_state", value=float(loudness) if loudness_ok else None, unit="dBFS" if loudness_ok else None,
            status="measured" if loudness_ok else "unavailable", evidence_snapshot={"active_loudness_dbfs": loudness if loudness_ok else None, "relative_loudness": "uncalibrated_engineering_observation", "voiced_ratio": acoustic.get("speaking_duration_seconds"), "prosody": (pronunciation.prosody_metrics if pronunciation else {}), "device_calibration_status": "uncalibrated", "acoustic_provider": (details.get("input_sources") or {}).get("acoustic_provider")},
            limitations=["仅以 dBFS 保存相对声音证据；未校准设备下不输出临床 dBA 结论。"],
        ),
        EvaluationDimensionResultCreate(
            dimension_code="independence", value=details.get("independence_score") if analysis else None, unit="engineering_score" if analysis else None,
            status="measured" if analysis else "unavailable", evidence_snapshot={"prompt_level": (details.get("independence_evidence") or {}).get("prompt_level"), "prompt_count": None, "help_requested": (details.get("independence_evidence") or {}).get("requested_help"), "start_latency_ms": (details.get("independence_evidence") or {}).get("start_latency_ms"), "completion": not attempt.skipped, "engineering_rule_version": config_entry("independence_prompt_penalties")["version"]},
            limitations=["提示和启动延迟的工程扣分为 E1 engineering heuristic，不是临床量表。"],
        ),
        _shadow_dimension(pronunciation),
    ]
    if review_override:
        for dimension in dimensions:
            patch = review_override.get(dimension.dimension_code)
            if not isinstance(patch, dict):
                continue
            if patch.get("status") == "unjudgeable":
                dimension.status, dimension.value, dimension.level = "unavailable", None, "unjudgeable"
            else:
                for key in ("value", "level", "unit", "status"):
                    if key in patch:
                        setattr(dimension, key, patch[key])
            if isinstance(patch.get("evidence_snapshot"), dict):
                dimension.evidence_snapshot.update(patch["evidence_snapshot"])
        result_status, profile_eligibility, ineligibility = "review_required", False, ["clinician_revision_requires_future_reassessment"]
        limitations = [*limitations, "治疗师修订保留在独立人工复核版本中；不可直接晋升正式画像。"]
    config = {"algorithm": REPEAT_V3_VERSION, "engineering_reference": {key: config_entry(key) for key in ["repeat_loudness_reference", "speech_rate_reference", "articulation_rate_reference", "independence_prompt_penalties", "independence_help_penalty", "independence_latency_penalties"]}, "missing_dimension_policy": "unavailable_and_not_observed_are_not_zero", "overall_score": "not_created", "manual_review_override": review_override or {}}
    provenance = InputProvenanceSnapshot(
        source_snapshot={"attempt_id": str(attempt.id), "audio_file_id": str(attempt.audio_file_id) if attempt.audio_file_id else None, "target_text_snapshot": template.target_text, "task_template_id": str(template.id), "task_type": template.task_type.value},
        providers={"asr": {"provider": semantic.get("asr_provider"), "requested_provider": semantic.get("requested_asr_provider"), "fallback_used": semantic.get("asr_fallback_used")}, "acoustic": {"provider": acoustic.get("provider"), "requested_provider": acoustic.get("requested_provider")}, "process": {"algorithm_version": details.get("provider_version")}, "pronunciation_shadow": {"provider": pronunciation.provider if pronunciation else None, "status": pronunciation.status if pronunciation else "not_observed"}},
        contract_version=(template.scoring_config or {}).get("version"), device_context={"calibration_status": "uncalibrated", "loudness_unit": gate.loudness_unit},
    )
    if review_override:
        provenance.source_snapshot["manual_review_override"] = review_override
    fingerprint = _fingerprint({"analysis": analysis.id if analysis else None, "semantic": semantic, "acoustic": acoustic, "pronunciation": pronunciation.id if pronunciation else None, "template": {"id": template.id, "target": template.target_text, "config": template.scoring_config}, "algorithm": REPEAT_V3_VERSION, "config": config})
    return EvaluationRunCreate(patient_profile_id=task.session.patient_profile_id, domain="repeat", source_type="attempt", source_id=attempt.id, algorithm_version=REPEAT_V3_VERSION, input_fingerprint=fingerprint, config_snapshot=config, input_provenance=provenance, quality_gate=QualityGateSnapshot(eligible=gate.eligible, reasons=list(gate.reasons), loudness_unit=gate.loudness_unit, algorithm_version=gate.algorithm_version, audio_quality=attempt.audio_quality, measurement_quality=details.get("quality_status")), result_status=result_status, profile_eligibility=profile_eligibility, profile_ineligibility_reasons=ineligibility, limitations=limitations, dimensions=dimensions)


def write_repeat_v3_run(db: Session, attempt: Attempt) -> EvaluationRun:
    payload = build_repeat_v3_payload(db, attempt)
    existing = db.scalar(select(EvaluationRun).where(EvaluationRun.source_type == "attempt", EvaluationRun.source_id == attempt.id, EvaluationRun.domain == "repeat", EvaluationRun.algorithm_version == REPEAT_V3_VERSION, EvaluationRun.input_fingerprint == payload.input_fingerprint))
    if existing:
        return existing if existing.adoption_status == "adopted" else adopt_candidate_run(db, existing.id)
    run = create_candidate_run(db, payload)
    return adopt_candidate_run(db, run.id)


def rebuild_repeat_v3_run(db: Session, attempt_id: UUID) -> EvaluationRun:
    attempt = db.get(Attempt, attempt_id)
    if not attempt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="作答不存在")
    return write_repeat_v3_run(db, attempt)


def get_adopted_repeat_run(db: Session, attempt_id: UUID) -> EvaluationRun | None:
    return get_adopted_run(db, "attempt", attempt_id, "repeat")


def require_repeat_professional_access(db: Session, current_user: User, attempt_id: UUID) -> None:
    profile_id = source_patient_profile_id(db, "attempt", attempt_id)
    profile = db.get(PatientProfile, profile_id)
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="患者档案不存在")
    from app.modules.therapist.service import require_therapist_patient_access

    require_therapist_patient_access(db, current_user, profile.user_id)


def review_or_recompute(db: Session, user: User, run_id: UUID, payload: EvaluationReviewRevisionCreate | None = None):
    current = get_run(db, run_id)
    if current.domain != "repeat":
        raise HTTPException(status_code=409, detail="该评估不是跟读 V3 结果")
    current_read = get_run_for_professional(db, user, run_id)
    if payload is None:
        attempt = db.get(Attempt, current.source_id)
        if not attempt:
            raise HTTPException(status_code=404, detail="跟读原始作答已不存在")
        rebuilt = build_repeat_v3_payload(db, attempt)
        candidate = db.scalar(select(EvaluationRun).where(EvaluationRun.source_type == "attempt", EvaluationRun.source_id == attempt.id, EvaluationRun.domain == "repeat", EvaluationRun.input_fingerprint == rebuilt.input_fingerprint))
        if not candidate:
            candidate = create_candidate_run(db, rebuilt)
        adopted = candidate if candidate.adoption_status == "adopted" else adopt_candidate_run(db, candidate.id)
        return adopted, None
    key_source = {
        "run_id": str(run_id),
        "reviewer": str(user.id),
        "action": payload.review_action if payload else "recompute",
        "dimension": str(payload.dimension_result_id) if payload and payload.dimension_result_id else None,
        "revised": payload.revised_value_snapshot if payload else {},
        "evidence": payload.evidence_override if payload else {},
        "reason": payload.reason if payload else None,
    }
    request_key = (payload.review_request_key if payload else None) or _fingerprint(key_source)
    existing_revision = db.scalar(select(EvaluationReviewRevision).where(EvaluationReviewRevision.evaluation_run_id == run_id, EvaluationReviewRevision.review_request_key == request_key))
    if existing_revision:
        return (get_run(db, existing_revision.recomputed_run_id) if existing_revision.recomputed_run_id else current), existing_revision

    target = None
    if payload and payload.dimension_result_id:
        target = next((item for item in current_read.dimension_results if item.id == payload.dimension_result_id), None)
        if not target:
            raise HTTPException(status_code=409, detail="复核维度不属于该评估运行")
    if payload and payload.review_action in {"corrected", "unjudgeable"} and not target:
        raise HTTPException(status_code=422, detail="修正或标记无法判断时必须选择一个评估维度")
    if payload and payload.review_action == "corrected":
        if not payload.reason or not payload.reason.strip():
            raise HTTPException(status_code=422, detail="修正结果必须说明依据")
        if not payload.revised_value_snapshot:
            raise HTTPException(status_code=422, detail="请填写修正后的测量值或状态")
    if payload and payload.review_action == "unjudgeable" and not payload.reason_code:
        raise HTTPException(status_code=422, detail="无法判断必须选择原因")

    attempt = db.get(Attempt, current.source_id)
    if not attempt:
        raise HTTPException(status_code=404, detail="跟读原始作答已不存在")
    if payload and payload.review_action in {"confirmed", "corrected"} and not attempt.audio_file_id:
        raise HTTPException(status_code=409, detail="缺少患者原音，只能记录无法判断，不能确认或修正自动结果")

    automatic = {}
    if target:
        automatic = {
            "dimension_code": target.dimension_code,
            "value": target.value,
            "level": target.level,
            "unit": target.unit,
            "status": _status_from_gate_value(target.status),
            "evidence_snapshot": target.evidence_snapshot or {},
            "measurement_quality": target.measurement_quality or {},
        }
    if payload and payload.review_action == "confirmed":
        revision = EvaluationReviewRevision(
            evaluation_run_id=run_id,
            dimension_result_id=payload.dimension_result_id,
            review_action="confirmed",
            automatic_value_snapshot=automatic,
            revised_value_snapshot={},
            evidence_override={},
            reason=payload.reason,
            reason_code=payload.reason_code,
            reviewer_user_id=user.id,
            review_request_key=request_key,
        )
        db.add(revision)
        db.commit()
        return current, revision

    override = {}
    if payload:
        patch = dict(payload.revised_value_snapshot or {})
        if payload.review_action == "unjudgeable":
            patch["status"] = "unjudgeable"
            patch["value"] = None
        if payload.evidence_override:
            patch["evidence_snapshot"] = dict(payload.evidence_override)
        override[target.dimension_code] = patch
    rebuilt = build_repeat_v3_payload(db, attempt, review_override=override)
    try:
        candidate = db.scalar(select(EvaluationRun).where(EvaluationRun.source_type == "attempt", EvaluationRun.source_id == attempt.id, EvaluationRun.domain == "repeat", EvaluationRun.input_fingerprint == rebuilt.input_fingerprint))
        if not candidate:
            candidate = create_candidate_run(db, rebuilt, commit=False)
        revision = EvaluationReviewRevision(
            evaluation_run_id=run_id,
            dimension_result_id=payload.dimension_result_id if payload else None,
            review_action=payload.review_action if payload else "confirmed",
            automatic_value_snapshot=automatic,
            revised_value_snapshot=payload.revised_value_snapshot if payload else {},
            evidence_override=payload.evidence_override if payload else {},
            reason=payload.reason if payload else None,
            reason_code=payload.reason_code if payload else None,
            reviewer_user_id=user.id,
            recomputed_run_id=candidate.id,
            review_request_key=request_key,
        )
        db.add(revision)
        db.flush()
        adopted = candidate if candidate.adoption_status == "adopted" else adopt_candidate_run(db, candidate.id, commit=False)
        db.commit()
        return adopted, revision
    except Exception:
        db.rollback()
        raise


def _status_from_gate_value(value) -> str:
    return str(getattr(value, "value", value))
