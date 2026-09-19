import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from app.modules.evaluation_runs.repeat_v3 import REPEAT_V3_VERSION, build_repeat_v3_payload, write_repeat_v3_run


def formal_analysis(*, asr_provider="tencent", fallback=False, unit="dBFS", quality="pass"):
    details = {
        "quality_status": quality,
        "evaluation_source": "system_rule",
        "input_sources": {"asr_provider": asr_provider, "acoustic_provider": "local"},
        "loudness_unit": unit,
        "provider_version": "rehab-process-v2",
        "expression_rate": 200.0,
        "articulation_rate": 240.0,
        "valid_word_count": 8,
        "speaking_duration_seconds": 2.0,
        "pause_metrics": {"pause_ratio": 0.1, "longest_pause_seconds": 1.2, "pause_over_1s_count": 1, "pause_over_3s_count": 0},
        "error_events": {"meaningless_repetition": 1, "self_correction": 1, "long_pause_over_3s": 0, "filler": 1},
        "repetition_events": [{"start": 1, "end": 2}],
        "self_correction_events": [{"start": 3, "end": 5}],
        "script_mismatch_events": {"omission": 1, "substitution": 1, "addition": 1},
        "alignment_events": [{"type": "omission", "target_start": 2}],
        "independence_score": 90,
        "independence_evidence": {"prompt_level": 1, "requested_help": False, "start_latency_ms": 500},
    }
    return SimpleNamespace(
        id=uuid4(), provider_version="rehab-process-v2", asr_text="今天天气很好", semantic_metrics={
            "asr_provider": asr_provider, "requested_asr_provider": asr_provider, "asr_fallback_used": fallback,
            "process_monitoring": {"script_accuracy": 87.5, "loudness": -20.0, "details": details},
        }, acoustic_metrics={"provider": "local", "requested_provider": "local", "speaking_duration_seconds": 2.0},
    )


class FakeDb:
    def __init__(self, analysis, pronunciation=None):
        self.scalars = [analysis, pronunciation]
        self.profile_id = uuid4()
        self.task = SimpleNamespace(task_template_id=uuid4(), session=SimpleNamespace(patient_profile_id=self.profile_id))
        self.template = SimpleNamespace(id=self.task.task_template_id, target_text="今天天气很好", task_type=SimpleNamespace(value="repeat"), scoring_config={"version": "repeat-contract-v1"})

    def scalar(self, _statement):
        return self.scalars.pop(0)

    def get(self, cls, _id):
        return self.task if cls.__name__ == "SessionTask" else self.template


class RepeatV3MappingTest(unittest.TestCase):
    def attempt(self, quality="pass"):
        return SimpleNamespace(id=uuid4(), audio_file_id=uuid4(), session_task_id=uuid4(), audio_quality=quality, skipped=False)

    def test_formal_repeat_generates_six_stable_dimensions_without_overall_score(self):
        payload = build_repeat_v3_payload(FakeDb(formal_analysis()), self.attempt())
        self.assertEqual(payload.algorithm_version, REPEAT_V3_VERSION)
        self.assertEqual(payload.result_status, "formal")
        self.assertTrue(payload.profile_eligibility)
        self.assertEqual([item.dimension_code for item in payload.dimensions], ["content_reproduction", "fluency_efficiency", "disfluency_events", "voice_state", "independence", "articulation_evidence"])
        content = payload.dimensions[0]
        self.assertEqual(content.unit, "%")
        self.assertIn("content_reproduction_rate", content.evidence_snapshot)
        self.assertNotIn("articulation_accuracy", content.evidence_snapshot)
        fluency = payload.dimensions[1].evidence_snapshot
        self.assertNotEqual(fluency["expression_rate"], fluency["articulation_rate"])
        voice = payload.dimensions[3]
        self.assertEqual(voice.unit, "dBFS")
        self.assertEqual(voice.value, -20.0)
        serialized_config = json.dumps(payload.config_snapshot)
        self.assertNotIn("target_loudness", serialized_config)
        self.assertNotIn("69", serialized_config)
        self.assertNotIn("overall_score", {item.dimension_code for item in payload.dimensions})

    def test_gate_failures_are_not_formal_and_unknown_unit_is_not_a_voice_value(self):
        for kwargs in [{"asr_provider": "mock"}, {"fallback": True}, {"unit": None}, {"quality": "unusable"}]:
            analysis = formal_analysis(**kwargs)
            payload = build_repeat_v3_payload(FakeDb(analysis), self.attempt(quality="pass" if kwargs.get("quality") != "unusable" else "unusable"))
            self.assertNotEqual(payload.result_status, "formal")
            self.assertFalse(payload.profile_eligibility)
            if kwargs.get("unit") is None and "unit" in kwargs:
                self.assertIsNone(payload.dimensions[3].value)
                self.assertEqual(payload.dimensions[3].status, "unavailable")

    def test_disabled_shadow_is_unavailable_but_does_not_demote_formal_core_run(self):
        shadow = SimpleNamespace(id=uuid4(), provider="disabled", provider_version="disabled", algorithm_version="rehab-pronunciation-v1-shadow", status="disabled", coverage=0.0, intelligibility_proxy=None, prosody_metrics={})
        payload = build_repeat_v3_payload(FakeDb(formal_analysis(), shadow), self.attempt())
        articulation = payload.dimensions[-1]
        self.assertEqual(payload.result_status, "formal")
        self.assertEqual(articulation.status, "unavailable")
        self.assertIsNone(articulation.value)

    def test_same_fingerprint_reuses_existing_adopted_run(self):
        existing = SimpleNamespace(adoption_status="adopted", id=uuid4())
        payload = build_repeat_v3_payload(FakeDb(formal_analysis()), self.attempt())
        db = SimpleNamespace(scalar=lambda _statement: existing)
        attempt = self.attempt()
        with patch("app.modules.evaluation_runs.repeat_v3.build_repeat_v3_payload", return_value=payload):
            self.assertIs(write_repeat_v3_run(db, attempt), existing)


if __name__ == "__main__":
    unittest.main()
