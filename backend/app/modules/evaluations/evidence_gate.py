"""R0 admission checks for consumers of the legacy process-evaluation chain."""

from dataclasses import dataclass


FORMAL_PROCESS_VERSION = "rehab-process-v2"
FORMAL_LOUDNESS_UNIT = "dBFS"


@dataclass(frozen=True)
class EvidenceGateResult:
    eligible: bool
    reasons: tuple[str, ...]
    loudness_unit: str | None
    algorithm_version: str | None


def _process_details(semantic_metrics: dict | None) -> tuple[dict, dict]:
    semantic = semantic_metrics or {}
    process = semantic.get("process_monitoring") or {}
    details = process.get("details") or {}
    return process if isinstance(process, dict) else {}, details if isinstance(details, dict) else {}


def process_evidence_gate(
    audio_quality: str | None,
    semantic_metrics: dict | None,
    provider_version: str | None = None,
) -> EvidenceGateResult:
    semantic = semantic_metrics or {}
    process, details = _process_details(semantic)
    reasons: list[str] = []
    source = details.get("evaluation_source", process.get("evaluation_source"))
    sources = details.get("input_sources", process.get("input_sources")) or {}
    quality_status = details.get("quality_status", process.get("quality_status"))
    loudness_unit = details.get("loudness_unit", process.get("loudness_unit"))
    algorithm_version = provider_version or details.get("provider_version", process.get("provider_version"))
    asr_provider = semantic.get("asr_provider") or sources.get("asr_provider")
    acoustic_provider = sources.get("acoustic_provider")

    if audio_quality != "pass" or quality_status not in {None, "pass"}:
        reasons.append("quality_not_passed")
    if semantic.get("asr_fallback_used"):
        reasons.append("asr_fallback")
    if asr_provider in {None, "", "mock", "unknown"}:
        reasons.append("asr_provider_not_formal")
    if acoustic_provider != "local":
        reasons.append("acoustic_provider_not_formal")
    if source != "system_rule":
        reasons.append("process_source_not_formal")
    if loudness_unit != FORMAL_LOUDNESS_UNIT:
        reasons.append("loudness_unit_unknown_or_incompatible")
    if algorithm_version != FORMAL_PROCESS_VERSION:
        reasons.append("algorithm_version_unknown_or_incompatible")
    return EvidenceGateResult(not reasons, tuple(reasons), loudness_unit, algorithm_version)


def is_formal_process_evidence(
    audio_quality: str | None,
    semantic_metrics: dict | None,
    provider_version: str | None = None,
) -> bool:
    return process_evidence_gate(audio_quality, semantic_metrics, provider_version).eligible
