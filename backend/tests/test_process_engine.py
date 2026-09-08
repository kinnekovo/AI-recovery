import unittest
from types import SimpleNamespace

from app.integrations.acoustic_analysis.provider import AcousticAnalysisResult
from app.modules.evaluations.process_metrics import PROCESS_METRIC_DEFINITIONS, PROCESS_REFERENCE_RANGES
from app.modules.evaluations.process_engine import generate_process_evaluation
from app.modules.training.model import TrainingType


def make_template(target_text: str, task_type: TrainingType = TrainingType.repeat) -> SimpleNamespace:
    return SimpleNamespace(
        task_type=task_type,
        title="测试任务",
        instruction="请跟读",
        target_text=target_text,
    )


def make_acoustic(
    speaking_duration_seconds: float = 3.0,
    loudness_dba: float = 65.0,
    long_pause_over_3s_count: int = 0,
    **kwargs,
) -> AcousticAnalysisResult:
    return AcousticAnalysisResult(
        speaking_duration_seconds=speaking_duration_seconds,
        loudness_dba=loudness_dba,
        long_pause_over_3s_count=long_pause_over_3s_count,
        **kwargs,
    )


class ProcessEngineTest(unittest.TestCase):
    def test_scores_exact_script_from_asr_text(self) -> None:
        result = generate_process_evaluation(
            make_template("吃完晚饭后，我想和家人一起散步。"),
            "吃完晚饭后，我想和家人一起散步。",
            make_acoustic(speaking_duration_seconds=4.0),
            asr_provider_name="tencent",
            acoustic_provider_name="mock",
        )

        self.assertEqual(result.script_accuracy, 100.0)
        self.assertEqual(result.details["correct_script_word_rate"], 100.0)
        self.assertEqual(result.details["correct_script_word_count"], result.details["total_script_word_count"])
        self.assertEqual(result.details["input_sources"]["asr_provider"], "tencent")

    def test_tracks_script_mismatch_without_counting_it_as_process_error(self) -> None:
        result = generate_process_evaluation(
            make_template("今天上午我要去医院复诊"),
            "今天我要去医院",
            make_acoustic(),
            asr_provider_name="tencent",
            acoustic_provider_name="mock",
        )

        self.assertLess(result.script_accuracy, 100)
        self.assertGreater(result.details["script_mismatch_events"]["omission"], 0)
        self.assertTrue(result.details["alignment_events"])
        self.assertIn("expected", result.details["alignment_events"][0])
        self.assertIn("actual", result.details["alignment_events"][0])
        self.assertEqual(result.error_count, 0)

    def test_counts_fillers_repetition_and_long_pause(self) -> None:
        result = generate_process_evaluation(
            make_template("我要和家人一起散步"),
            "我要啊和家人人一起散步",
            make_acoustic(long_pause_over_3s_count=1),
            asr_provider_name="tencent",
            acoustic_provider_name="mock",
        )

        self.assertEqual(result.details["error_events"]["filler"], 1)
        self.assertEqual(result.details["error_events"]["meaningless_repetition"], 1)
        self.assertEqual(result.details["error_events"]["long_pause_over_3s"], 1)
        self.assertEqual(result.error_count, 3)

    def test_detects_phrase_repetition_and_self_correction(self) -> None:
        repeated = generate_process_evaluation(
            make_template("我要去医院"),
            "我要我要去医院",
            make_acoustic(),
            asr_provider_name="tencent",
            acoustic_provider_name="local",
        )
        corrected = generate_process_evaluation(
            make_template("我要去医院"),
            "我要去学校，不对，我要去医院",
            make_acoustic(),
            asr_provider_name="tencent",
            acoustic_provider_name="local",
        )

        self.assertEqual(repeated.details["error_events"]["meaningless_repetition"], 1)
        self.assertEqual(repeated.details["repetition_events"][0]["text"], "我要")
        self.assertEqual(corrected.details["error_events"]["self_correction"], 1)
        self.assertEqual(corrected.details["self_correction_events"][0]["marker"], "不对")
        self.assertEqual(corrected.details["evaluated_transcript_segment"], "我要去医院")
        self.assertEqual(corrected.script_accuracy, 100.0)

    def test_separates_expression_and_articulation_rates(self) -> None:
        result = generate_process_evaluation(
            make_template("今天我要去医院"),
            "今天我要去医院",
            make_acoustic(
                speaking_duration_seconds=2.0,
                total_duration_seconds=4.0,
                loudness_dbfs=-24.0,
                pause_over_1s_count=1,
                internal_pause_duration_seconds=2.0,
                pause_ratio=0.5,
                longest_pause_seconds=2.0,
            ),
            asr_provider_name="tencent",
            acoustic_provider_name="local",
        )

        self.assertLess(result.details["expression_rate"], result.details["articulation_rate"])
        self.assertEqual(result.speech_rate, result.details["expression_rate"])
        self.assertEqual(result.details["pause_metrics"]["pause_ratio"], 0.5)
        self.assertEqual(result.loudness, -24.0)
        self.assertEqual(result.details["loudness_unit"], "dBFS")

    def test_independence_uses_prompt_help_and_start_latency(self) -> None:
        independent = generate_process_evaluation(
            make_template("我要去医院"),
            "我要去医院",
            make_acoustic(),
            asr_provider_name="tencent",
            acoustic_provider_name="local",
        )
        assisted = generate_process_evaluation(
            make_template("我要去医院"),
            "我要去医院",
            make_acoustic(),
            asr_provider_name="tencent",
            acoustic_provider_name="local",
            prompt_level=3,
            requested_help=True,
            start_latency_ms=12000,
        )

        self.assertEqual(independent.details["independence_score"], 100)
        self.assertEqual(assisted.details["independence_score"], 30)
        self.assertEqual(assisted.details["independence_evidence"]["prompt_penalty"], 40)

    def test_real_evaluation_records_provenance_and_version(self) -> None:
        result = generate_process_evaluation(
            make_template("我要去医院"),
            "我要去医院",
            make_acoustic(snr_db=22.0),
            asr_provider_name="tencent",
            acoustic_provider_name="local",
        )

        self.assertEqual(result.details["evaluation_source"], "system_rule")
        self.assertEqual(result.details["provider_version"], "rehab-process-v2")
        self.assertEqual(result.details["input_sources"], {"asr_provider": "tencent", "acoustic_provider": "local"})

    def test_keeps_mock_fallback_explicit(self) -> None:
        result = generate_process_evaluation(
            make_template("我要和家人一起散步"),
            "这是一次模拟转写结果",
            make_acoustic(),
            asr_provider_name="mock",
            acoustic_provider_name="mock",
        )

        self.assertEqual(result.details["evaluation_source"], "mock_ai")
        self.assertEqual(result.details["provider_version"], "mock-process-v1")
        self.assertGreater(result.script_accuracy, 0)

    def test_process_reference_ranges_match_metric_definitions(self) -> None:
        result = generate_process_evaluation(
            make_template("我要和家人一起散步"),
            "我要和家人一起散步",
            make_acoustic(),
            asr_provider_name="tencent",
            acoustic_provider_name="local",
        )

        self.assertEqual(result.details["reference_ranges"], PROCESS_REFERENCE_RANGES)
        self.assertEqual(set(result.details["reference_ranges"]), set(PROCESS_METRIC_DEFINITIONS))


if __name__ == "__main__":
    unittest.main()
