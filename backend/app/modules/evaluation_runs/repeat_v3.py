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
from app.modules.evaluation_runs.model import EvaluationRun
from app.modules.evaluation_runs.schema import (
    EvaluationDimensionResultCreate,
    EvaluationRunCreate,
    InputProvenanceSnapshot,
    QualityGateSnapshot,
)
from app.modules.evaluation_runs.service import adopt_candidate_run, create_candidate_run, get_adopted_run, source_patient_profile_id
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


def build_repeat_v3_payload(db: Session, attempt: Attempt) -> EvaluationRunCreate:
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
    config = {"algorithm": REPEAT_V3_VERSION, "engineering_reference": {key: config_entry(key) for key in ["repeat_loudness_reference", "speech_rate_reference", "articulation_rate_reference", "independence_prompt_penalties", "independence_help_penalty", "independence_latency_penalties"]}, "missing_dimension_policy": "unavailable_and_not_observed_are_not_zero", "overall_score": "not_created"}
    provenance = InputProvenanceSnapshot(
        source_snapshot={"attempt_id": str(attempt.id), "audio_file_id": str(attempt.audio_file_id) if attempt.audio_file_id else None, "target_text_snapshot": template.target_text, "task_template_id": str(template.id), "task_type": template.task_type.value},
        providers={"asr": {"provider": semantic.get("asr_provider"), "requested_provider": semantic.get("requested_asr_provider"), "fallback_used": semantic.get("asr_fallback_used")}, "acoustic": {"provider": acoustic.get("provider"), "requested_provider": acoustic.get("requested_provider")}, "process": {"algorithm_version": details.get("provider_version")}, "pronunciation_shadow": {"provider": pronunciation.provider if pronunciation else None, "status": pronunciation.status if pronunciation else "not_observed"}},
        contract_version=(template.scoring_config or {}).get("version"), device_context={"calibration_status": "uncalibrated", "loudness_unit": gate.loudness_unit},
    )
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
