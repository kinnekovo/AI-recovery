"""Versioned engineering configuration used by the legacy R0 safety baseline.

These values are engineering heuristics, not clinical standards.  Keeping the
metadata beside every value makes that boundary explicit and gives audit code a
single source of truth while the V2/V3 algorithms remain out of scope.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any


R0_CONFIG_VERSION = "r0-engineering-safety-v1"


def _entry(value: Any, unit: str, domain: str, maturity: str = "E1") -> dict[str, Any]:
    return {
        "value": value,
        "unit": unit,
        "domain": domain,
        "maturity": maturity,
        "source": "engineering heuristic",
        "version": R0_CONFIG_VERSION,
    }


ALGORITHM_CONFIG: dict[str, dict[str, Any]] = {
    "repeat_loudness_reference": _entry({"min": -35.0, "max": -12.0}, "dBFS", "repeat.voice_state"),
    "script_accuracy_reference": _entry(90.0, "%", "repeat.content_reproduction"),
    "error_count_reference": _entry({"min": 0.0, "max": 1.0}, "count/task", "repeat.disfluency_events"),
    "acoustic_voice_threshold": _entry(-45.0, "dBFS", "audio.voice_activity"),
    "acoustic_min_loudness": _entry(-45.0, "dBFS", "audio.quality_gate"),
    "speech_rate_reference": _entry({"min": 180.0, "max": 240.0}, "char/min", "repeat.fluency_efficiency"),
    "speech_rate_target": _entry(210.0, "char/min", "legacy_phase4.3.observation", "E0"),
    "articulation_rate_reference": _entry({"min": 180.0, "max": 260.0}, "char/min", "repeat.fluency_efficiency"),
    "phase43_low_accuracy": _entry(78.0, "%", "legacy_phase4.3.recommendation", "E0"),
    "phase43_high_errors": _entry(3.0, "count/task", "legacy_phase4.3.recommendation", "E0"),
    "phase43_slow_speech_rate": _entry(180.0, "char/min", "legacy_phase4.3.recommendation", "E0"),
    "phase43_scenario_content_min": _entry(3, "L-axis", "legacy_phase4.3.recommendation", "E0"),
    "phase43_scenario_autonomy_min": _entry(3, "S-axis", "legacy_phase4.3.recommendation", "E0"),
    "phase43_accuracy_delta": _entry(3.0, "percentage_point", "legacy_phase4.3.observation", "E0"),
    "phase43_error_delta": _entry(1.0, "count/task", "legacy_phase4.3.observation", "E0"),
    "phase43_speech_rate_margin": _entry(8.0, "char/min", "legacy_phase4.3.observation", "E0"),
    "phase43_loudness_margin": _entry(3.0, "dBFS", "legacy_phase4.3.observation", "E0"),
    "phase43_positive_signals": _entry(2, "count", "legacy_phase4.3.observation", "E0"),
    "phase43_negative_signals": _entry(2, "count", "legacy_phase4.3.observation", "E0"),
    "repeat_score_weights": _entry(
        {"content": 0.45, "error_control": 0.15, "fluency": 0.25, "loudness": 0.10, "independence": 0.05},
        "ratio",
        "repeat.rehab-score-v2",
    ),
    "scenario_score_weights": _entry(
        {"content": 0.30, "error_control": 0.15, "fluency": 0.30, "loudness": 0.10, "independence": 0.15},
        "ratio",
        "legacy_scenario.rehab-score-v2",
        "E0",
    ),
    "clarity_event_penalties": _entry(
        {"meaningless_repetition": 8.0, "self_correction": 4.0, "long_pause_over_3s": 10.0, "filler": 3.0},
        "score_point/event",
        "repeat.rehab-score-v2",
    ),
    "fluency_component_weights": _entry({"expression": 0.6, "articulation": 0.4}, "ratio", "repeat.rehab-score-v2"),
    "score_rate_distance_multipliers": _entry(
        {"expression": 0.7, "articulation": 0.55}, "score_point/unit", "repeat.rehab-score-v2"
    ),
    "score_pause_ratio_penalty": _entry(35.0, "score_point/ratio", "repeat.rehab-score-v2"),
    "score_loudness_distance_penalty": _entry(3.0, "score_point/dBFS", "repeat.rehab-score-v2"),
    "score_quality_confidence": _entry({"snr_min": 15.0, "penalty": 0.15}, "mixed", "repeat.rehab-score-v2"),
    "independence_prompt_penalties": _entry([0.0, 10.0, 25.0, 40.0, 55.0], "score_point", "repeat.independence"),
    "independence_help_penalty": _entry(15.0, "score_point", "repeat.independence"),
    "independence_latency_penalties": _entry(
        [{"gt_seconds": 10.0, "penalty": 15.0}, {"gt_seconds": 5.0, "penalty": 8.0}, {"gt_seconds": 3.0, "penalty": 3.0}],
        "score_point",
        "repeat.independence",
    ),
    "profile_high_accuracy": _entry(90.0, "%", "legacy_ability_profile", "E0"),
    "profile_low_loudness": _entry(-35.0, "dBFS", "legacy_ability_profile", "E0"),
    "profile_level_rules": _entry(
        [
            {"accuracy_min": 92.0, "errors_max": 1.0, "reviewed_min": 2, "levels": ["L4", "S3"]},
            {"accuracy_min": 90.0, "errors_max": 1.0, "reviewed_min": 0, "levels": ["L3", "S3"]},
            {"accuracy_min": 78.0, "errors_max": 2.0, "reviewed_min": 0, "levels": ["L2", "S2"]},
        ],
        "rule_set",
        "legacy_ability_profile",
        "E0",
    ),
    "profile_evidence_weights": _entry(
        {"process": 0.55, "assessment_review": 0.30, "scenario_review": 0.15}, "ratio", "legacy_ability_profile", "E0"
    ),
    "profile_evidence_caps": _entry(
        {"process": 5, "assessment_review": 2, "scenario_review": 2}, "count", "legacy_ability_profile", "E0"
    ),
    "profile_recommendation_gate": _entry(
        {"confidence_min": 0.45, "accuracy_low": 75.0, "errors_high": 4.0}, "mixed", "legacy_ability_profile", "E0"
    ),
    "scenario_dialogue_goal_scores": _entry(
        {"achieved": 100.0, "partly_achieved": 60.0, "not_achieved": 0.0}, "%", "functional_communication", "E1"
    ),
    "legacy_scenario_goal_scores": _entry(
        {"achieved": 100.0, "goal_partial": 60.0, "information_partial": 35.0, "not_achieved": 0.0},
        "%",
        "legacy_scenario_information_units",
        "E0",
    ),
    "scenario_dialogue_independence_penalties": _entry(
        {"maximum_prompt_level": 15.0, "prompt_count": 5.0}, "score_point", "functional_communication", "E1"
    ),
    "scenario_dialogue_evidence_confidence_min": _entry(0.7, "provider_probability", "functional_communication", "E1"),
    "scenario_dialogue_score_weights": _entry(
        {"goal": 0.35, "information": 0.25, "response": 0.15, "relevance": 0.10, "independence": 0.10, "repair": 0.05},
        "ratio",
        "functional_communication",
        "E1",
    ),
    "pronunciation_proxy_weights": _entry(
        {"process_accuracy": 0.4, "provider_accuracy": 0.35, "completion": 0.15, "prosody_quality": 0.1},
        "ratio",
        "pronunciation_shadow",
        "E1",
    ),
    "pronunciation_coverage_weights": _entry(
        {"process": 0.2, "provider": 0.55, "prosody": 0.25}, "ratio", "pronunciation_shadow", "E1"
    ),
    "pronunciation_shadow_composite_weights": _entry(
        {"process_accuracy": 0.35, "provider_accuracy": 0.20, "provider_fluency": 0.20, "event_control": 0.10, "prosody": 0.10, "independence": 0.05},
        "ratio",
        "pronunciation_shadow",
        "E1",
    ),
}


def config_entry(name: str) -> dict[str, Any]:
    """Return a copy so callers cannot mutate the process-wide audit config."""

    return deepcopy(ALGORITHM_CONFIG[name])


def config_value(name: str) -> Any:
    return deepcopy(ALGORITHM_CONFIG[name]["value"])


def range_bounds(name: str) -> tuple[float, float]:
    value = ALGORITHM_CONFIG[name]["value"]
    return float(value["min"]), float(value["max"])
