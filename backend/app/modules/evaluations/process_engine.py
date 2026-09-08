from difflib import SequenceMatcher
from typing import Any

from app.integrations.acoustic_analysis.provider import AcousticAnalysisResult
from app.modules.evaluations.model import EvaluationSource
from app.modules.evaluations.process_metrics import PROCESS_REFERENCE_RANGES
from app.modules.evaluations.schema import ProcessEvaluation
from app.modules.training.model import TaskTemplate, TrainingType


ALGORITHM_VERSION = "rehab-process-v2"
PUNCTUATION = set("，。！？,.!?、；;：:“”\"'（）()《》<>【】[] \n\r\t")
FILLER_CHARS = {"呃", "啊", "嗯", "额"}
SELF_CORRECTION_MARKERS = ("不对", "不是", "我是说", "应该是", "改成")


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


def _alignment_analysis(target_chars: list[str], transcript_chars: list[str]) -> tuple[dict[str, int], list[dict]]:
    matcher = SequenceMatcher(a=target_chars, b=transcript_chars, autojunk=False)
    counts = {"correct": 0, "substitution": 0, "addition": 0, "omission": 0}
    events: list[dict] = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        target_len = i2 - i1
        transcript_len = j2 - j1
        if tag == "equal":
            counts["correct"] += target_len
            continue
        if tag == "delete":
            counts["omission"] += target_len
            event_type = "omission"
        elif tag == "insert":
            counts["addition"] += transcript_len
            event_type = "addition"
        else:
            shared = min(target_len, transcript_len)
            counts["substitution"] += shared
            counts["omission"] += max(target_len - transcript_len, 0)
            counts["addition"] += max(transcript_len - target_len, 0)
            event_type = "substitution"
        events.append(
            {
                "type": event_type,
                "target_start": i1,
                "target_end": i2,
                "transcript_start": j1,
                "transcript_end": j2,
                "expected": "".join(target_chars[i1:i2]),
                "actual": "".join(transcript_chars[j1:j2]),
            }
        )
    return counts, events


def _repetition_analysis(target_chars: list[str], transcript_chars: list[str]) -> tuple[int, int, list[dict]]:
    if target_chars == transcript_chars:
        return 0, 0, []
    events: list[dict] = []
    repeated_chars = 0
    index = 0
    while index < len(transcript_chars) - 1:
        max_size = min(4, (len(transcript_chars) - index) // 2)
        size = next(
            (
                candidate
                for candidate in range(max_size, 0, -1)
                if transcript_chars[index : index + candidate]
                == transcript_chars[index + candidate : index + candidate * 2]
            ),
            0,
        )
        if not size:
            index += 1
            continue
        text = "".join(transcript_chars[index : index + size])
        events.append({"text": text, "start": index, "end": index + size * 2, "repeated_chars": size})
        repeated_chars += size
        index += size * 2
    return len(events), repeated_chars, events


def _self_correction_analysis(transcript: str, target_text: str) -> list[dict]:
    events = []
    for marker in SELF_CORRECTION_MARKERS:
        if marker in target_text:
            continue
        start = 0
        while True:
            index = transcript.find(marker, start)
            if index < 0:
                break
            events.append({"marker": marker, "start": index, "end": index + len(marker)})
            start = index + len(marker)
    return sorted(events, key=lambda item: item["start"])


def _final_corrected_segment(transcript: str, correction_events: list[dict]) -> str:
    if not correction_events:
        return transcript
    final_segment = transcript[correction_events[-1]["end"] :].strip(" ，。！？,.!?、；;：:\n\r\t")
    return final_segment or transcript


def _independence_score(prompt_level: int, requested_help: bool, start_latency_ms: int | None) -> tuple[int, dict]:
    normalized_prompt_level = max(0, min(int(prompt_level), 4))
    prompt_penalty = (0, 10, 25, 40, 55)[normalized_prompt_level]
    help_penalty = 15 if requested_help else 0
    latency_seconds = max((start_latency_ms or 0) / 1000, 0)
    if latency_seconds > 10:
        latency_penalty = 15
    elif latency_seconds > 5:
        latency_penalty = 8
    elif latency_seconds > 3:
        latency_penalty = 3
    else:
        latency_penalty = 0
    score = max(0, 100 - prompt_penalty - help_penalty - latency_penalty)
    return score, {
        "prompt_level": normalized_prompt_level,
        "requested_help": requested_help,
        "start_latency_ms": start_latency_ms,
        "prompt_penalty": prompt_penalty,
        "help_penalty": help_penalty,
        "latency_penalty": latency_penalty,
    }


def _mock_process_evaluation(template: TaskTemplate, acoustic: AcousticAnalysisResult) -> ProcessEvaluation:
    total_script_chars = max(count_effective_chars(template.target_text), 1)
    accuracy = 95.0 if template.task_type == TrainingType.repeat else 88.0
    correct_chars = round(total_script_chars * accuracy / 100)
    target_rate = 150.0 if template.task_type == TrainingType.repeat else 140.0
    return ProcessEvaluation(
        script_accuracy=accuracy,
        error_count=1,
        speech_rate=target_rate,
        loudness=round(acoustic.loudness_dba, 2),
        details={
            "correct_script_word_rate": accuracy,
            "correct_script_word_count": correct_chars,
            "total_script_word_count": total_script_chars,
            "valid_word_count": max(correct_chars, 1),
            "error_events": {"meaningless_repetition": 0, "self_correction": 0, "long_pause_over_3s": 1, "filler": 0},
            "alignment_events": [],
            "script_mismatch_events": {"substitution": 0, "addition": 0, "omission": total_script_chars - correct_chars},
            "reference_ranges": PROCESS_REFERENCE_RANGES,
            "evaluation_source": EvaluationSource.mock_ai.value,
            "provider_version": "mock-process-v1",
            "quality_status": "mock",
            "limitations": ["当前 ASR 为 mock，结果仅用于流程联调。"],
        },
    )


def generate_process_evaluation(
    template: TaskTemplate,
    transcript: str,
    acoustic: AcousticAnalysisResult,
    *,
    asr_provider_name: str = "unknown",
    acoustic_provider_name: str = "unknown",
    prompt_level: int = 0,
    requested_help: bool = False,
    start_latency_ms: int | None = None,
    attempt_duration_ms: int | None = None,
) -> ProcessEvaluation:
    if transcript == "这是一次模拟转写结果":
        return _mock_process_evaluation(template, acoustic)

    target_chars = normalize_chars(template.target_text, drop_fillers=True)
    correction_events = _self_correction_analysis(transcript, template.target_text)
    evaluated_transcript = _final_corrected_segment(transcript, correction_events)
    transcript_chars = normalize_chars(evaluated_transcript, drop_fillers=True)
    raw_transcript_chars = normalize_chars(transcript)
    total_script_chars = max(len(target_chars), 1)
    alignment, alignment_events = _alignment_analysis(target_chars, transcript_chars)
    repetition_count, repeated_chars, repetition_events = _repetition_analysis(target_chars, transcript_chars)

    correct_chars = min(alignment["correct"], total_script_chars)
    correct_rate = round(correct_chars / total_script_chars * 100, 2)
    filler_count = sum(1 for char in raw_transcript_chars if char in FILLER_CHARS)
    effective_chars = max(len(transcript_chars) - repeated_chars, 0)
    speaking_duration = max(acoustic.speaking_duration_seconds, 0.1)
    measured_total_duration = acoustic.total_duration_seconds or (attempt_duration_ms or 0) / 1000 or speaking_duration
    total_duration = max(measured_total_duration, speaking_duration, 0.1)
    expression_rate = round(effective_chars / total_duration * 60, 2) if effective_chars else 0.0
    articulation_rate = round(effective_chars / speaking_duration * 60, 2) if effective_chars else 0.0
    independence_score, independence_evidence = _independence_score(prompt_level, requested_help, start_latency_ms)
    error_events = {
        "meaningless_repetition": repetition_count,
        "self_correction": len(correction_events),
        "long_pause_over_3s": acoustic.long_pause_over_3s_count,
        "filler": filler_count,
    }
    limitations = ["尚未接入音素级发音评测，构音准确性未测量。"]
    if template.task_type == TrainingType.scenario:
        limitations.append("场景表达暂使用文本对齐，语义信息单元评分将在后续阶段接入。")
    if acoustic_provider_name == "mock":
        limitations.append("声学指标来自 mock provider，不可用于正式趋势。")

    details: dict[str, Any] = {
        "task_type": template.task_type.value,
        "correct_script_word_rate": correct_rate,
        "correct_script_word_count": correct_chars,
        "total_script_word_count": total_script_chars,
        "valid_word_count": effective_chars,
        "evaluated_transcript_segment": evaluated_transcript,
        "expression_rate": expression_rate,
        "articulation_rate": articulation_rate,
        "speaking_duration_seconds": round(speaking_duration, 2),
        "total_duration_seconds": round(total_duration, 2),
        "pause_metrics": {
            "pause_over_1s_count": acoustic.pause_over_1s_count,
            "pause_over_3s_count": acoustic.long_pause_over_3s_count,
            "internal_pause_duration_seconds": acoustic.internal_pause_duration_seconds,
            "pause_ratio": acoustic.pause_ratio,
            "longest_pause_seconds": acoustic.longest_pause_seconds,
        },
        "error_events": error_events,
        "repetition_events": repetition_events,
        "self_correction_events": correction_events,
        "alignment_events": alignment_events,
        "script_mismatch_events": {
            "substitution": alignment["substitution"],
            "addition": alignment["addition"],
            "omission": alignment["omission"],
        },
        "independence_score": independence_score,
        "independence_evidence": independence_evidence,
        "quality_status": acoustic.quality_status,
        "quality_reason": acoustic.quality_reason,
        "acoustic_quality": {
            "snr_db": acoustic.snr_db,
            "clipping_ratio": acoustic.clipping_ratio,
            "too_short": acoustic.too_short,
            "too_quiet": acoustic.too_quiet,
            "too_noisy": acoustic.too_noisy,
            "clipped": acoustic.clipped,
        },
        "loudness_unit": "dBFS" if acoustic_provider_name == "local" else "dBA",
        "reference_ranges": PROCESS_REFERENCE_RANGES,
        "evaluation_source": EvaluationSource.system_rule.value,
        "provider_version": ALGORITHM_VERSION,
        "input_sources": {"asr_provider": asr_provider_name, "acoustic_provider": acoustic_provider_name},
        "limitations": limitations,
    }

    loudness = acoustic.loudness_dbfs if acoustic_provider_name == "local" else acoustic.loudness_dba
    return ProcessEvaluation(
        script_accuracy=correct_rate,
        error_count=sum(error_events.values()),
        speech_rate=expression_rate,
        loudness=round(loudness, 2),
        details=details,
    )
