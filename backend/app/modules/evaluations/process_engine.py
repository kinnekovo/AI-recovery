from difflib import SequenceMatcher
from typing import Any

from app.integrations.acoustic_analysis.provider import AcousticAnalysisResult
from app.modules.evaluations.model import EvaluationSource
from app.modules.evaluations.schema import ProcessEvaluation
from app.modules.training.model import TaskTemplate, TrainingType


PUNCTUATION = set("，。！？,.!?、；;：:“”\"'（）()《》<>【】[] \n\r\t")
FILLER_CHARS = {"呃", "啊", "嗯", "额"}
REFERENCE_RANGES = {
    "correct_script_word_rate": "100%",
    "error_count": "0",
    "speech_rate_wpm": "180-240字/min",
    "loudness_dba": "60-78 dBA",
}


def normalize_chars(text: str, *, drop_fillers: bool = False) -> list[str]:
    chars: list[str] = []
    for char in text:
        if char in PUNCTUATION:
            continue
        if drop_fillers and char in FILLER_CHARS:
            continue
        if char.strip():
            chars.append(char)
    return chars


def count_effective_chars(text: str) -> int:
    return len(normalize_chars(text, drop_fillers=True))


def _alignment_counts(target_chars: list[str], transcript_chars: list[str]) -> dict[str, int]:
    matcher = SequenceMatcher(a=target_chars, b=transcript_chars, autojunk=False)
    counts = {
        "correct": 0,
        "substitution": 0,
        "addition": 0,
        "omission": 0,
    }
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        target_len = i2 - i1
        transcript_len = j2 - j1
        if tag == "equal":
            counts["correct"] += target_len
        elif tag == "delete":
            counts["omission"] += target_len
        elif tag == "insert":
            counts["addition"] += transcript_len
        elif tag == "replace":
            shared = min(target_len, transcript_len)
            counts["substitution"] += shared
            counts["omission"] += max(target_len - transcript_len, 0)
            counts["addition"] += max(transcript_len - target_len, 0)
    return counts


def _count_meaningless_repetitions(chars: list[str]) -> int:
    repetitions = 0
    index = 1
    while index < len(chars):
        if chars[index] == chars[index - 1]:
            repetitions += 1
            repeated_char = chars[index]
            while index + 1 < len(chars) and chars[index + 1] == repeated_char:
                index += 1
        index += 1
    return repetitions


def _mock_process_evaluation(template: TaskTemplate, acoustic: AcousticAnalysisResult) -> ProcessEvaluation:
    total_script_chars = max(count_effective_chars(template.target_text), 1)
    accuracy = 95.0 if template.task_type == TrainingType.repeat else 88.0
    correct_chars = round(total_script_chars * accuracy / 100)
    valid_chars = max(correct_chars, 1)
    target_rate = 150.0 if template.task_type == TrainingType.repeat else 140.0
    speaking_duration = round(valid_chars / target_rate * 60, 2)
    error_events = {
        "meaningless_repetition": 1 if template.task_type == TrainingType.scenario else 0,
        "long_pause_over_3s": acoustic.long_pause_over_3s_count,
        "unintelligible_pronunciation": 0,
        "filler": 0,
    }
    return ProcessEvaluation(
        script_accuracy=accuracy,
        error_count=sum(error_events.values()),
        speech_rate=round(valid_chars / max(speaking_duration, 0.1) * 60, 2),
        loudness=round(acoustic.loudness_dba, 2),
        details={
            "correct_script_word_rate": accuracy,
            "correct_script_word_count": correct_chars,
            "total_script_word_count": total_script_chars,
            "valid_word_count": valid_chars,
            "speaking_duration_seconds": speaking_duration,
            "error_events": error_events,
            "script_mismatch_events": {
                "substitution": 0,
                "addition": 0,
                "omission": total_script_chars - correct_chars,
            },
            "reference_ranges": REFERENCE_RANGES,
            "evaluation_source": EvaluationSource.mock_ai.value,
            "provider_version": "mock-process-v1",
            "limitations": ["当前 ASR 为 mock，过程性监控结果仅用于流程联调。"],
        },
    )


def generate_process_evaluation(
    template: TaskTemplate,
    transcript: str,
    acoustic: AcousticAnalysisResult,
    *,
    asr_provider_name: str = "unknown",
    acoustic_provider_name: str = "unknown",
) -> ProcessEvaluation:
    if transcript == "这是一次模拟转写结果":
        return _mock_process_evaluation(template, acoustic)

    target_chars = normalize_chars(template.target_text, drop_fillers=True)
    transcript_chars = normalize_chars(transcript, drop_fillers=True)
    raw_transcript_chars = normalize_chars(transcript)
    total_script_chars = max(len(target_chars), 1)
    alignment = _alignment_counts(target_chars, transcript_chars)

    correct_chars = min(alignment["correct"], total_script_chars)
    correct_rate = round(correct_chars / total_script_chars * 100, 2)
    filler_count = sum(1 for char in raw_transcript_chars if char in FILLER_CHARS)
    repetition_count = _count_meaningless_repetitions(transcript_chars)
    unintelligible_count = 1 if not transcript_chars else 0
    error_events = {
        "meaningless_repetition": repetition_count,
        "long_pause_over_3s": acoustic.long_pause_over_3s_count,
        "unintelligible_pronunciation": unintelligible_count,
        "filler": filler_count,
    }
    speaking_duration = max(acoustic.speaking_duration_seconds, 0.1)
    valid_chars = max(len(transcript_chars) - repetition_count, 0)
    speech_rate = round(valid_chars / speaking_duration * 60, 2) if valid_chars else 0.0
    limitations = []
    if acoustic_provider_name == "mock":
        limitations.append("响度、停顿和说话时长来自 mock 声学 provider，待真实声学分析接入后更新。")

    details: dict[str, Any] = {
        "correct_script_word_rate": correct_rate,
        "correct_script_word_count": correct_chars,
        "total_script_word_count": total_script_chars,
        "valid_word_count": valid_chars,
        "speaking_duration_seconds": round(speaking_duration, 2),
        "error_events": error_events,
        "script_mismatch_events": {
            "substitution": alignment["substitution"],
            "addition": alignment["addition"],
            "omission": alignment["omission"],
        },
        "reference_ranges": REFERENCE_RANGES,
        "evaluation_source": "system_rule",
        "provider_version": "process-rule-v1",
        "input_sources": {
            "asr_provider": asr_provider_name,
            "acoustic_provider": acoustic_provider_name,
        },
        "limitations": limitations,
    }

    return ProcessEvaluation(
        script_accuracy=correct_rate,
        error_count=sum(error_events.values()),
        speech_rate=speech_rate,
        loudness=round(acoustic.loudness_dba, 2),
        details=details,
    )
