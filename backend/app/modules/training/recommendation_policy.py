from dataclasses import dataclass
from typing import Any

from app.core.algorithm_config import config_entry, config_value, range_bounds
from app.modules.training.model import TrainingType


RECOMMENDATION_POLICY: dict[str, Any] = {
    "version": "phase4.3-historical-r0-frozen",
    "mode": "historical_read_compatible",
    "automatic_difficulty_adjustment": False,
    "target_speech_rate": config_entry("speech_rate_target"),
    "loudness_reference": config_entry("repeat_loudness_reference"),
    "decision_thresholds": {
        "low_accuracy": config_entry("phase43_low_accuracy"),
        "high_errors": config_entry("phase43_high_errors"),
        "low_loudness": config_entry("profile_low_loudness"),
        "slow_speech_rate": config_entry("phase43_slow_speech_rate"),
        "scenario_content_min": config_entry("phase43_scenario_content_min"),
        "scenario_autonomy_min": config_entry("phase43_scenario_autonomy_min"),
    },
    "adaptive_adjustment": {
        "effective_min_positive_signals": config_entry("phase43_positive_signals"),
        "needs_adjustment_negative_signals": config_entry("phase43_negative_signals"),
        "accuracy_delta": config_entry("phase43_accuracy_delta"),
        "error_delta": config_entry("phase43_error_delta"),
        "speech_rate_margin": config_entry("phase43_speech_rate_margin"),
        "loudness_margin": config_entry("phase43_loudness_margin"),
    },
    "sequence_steps": [
        {"label": "热身", "type": "repeat", "content_delta": -1, "autonomy_delta": -1},
        {"label": "主练", "type": "recommended", "content_delta": 0, "autonomy_delta": 0},
        {"label": "挑战", "type": "recommended", "content_delta": 1, "autonomy_delta": 1, "not_easier": True},
    ],
}


@dataclass
class RecommendationDecision:
    recommended_type: TrainingType
    headline: str
    reason: str
    focus_points: list[str]
    suggested_minutes: int
    content_level: str
    autonomy_level: str
    adaptation_note: str | None = None


@dataclass
class TrendPolicyResult:
    status: str
    summary: str
    hint: str
    evidence: list[str]
    attribution_points: list[str]
    reminder_level: str
    patient_reminder: str
    family_reminder: str
    therapist_reminder: str


def decide_recommendation_by_policy(ability, trend: TrendPolicyResult | None = None) -> RecommendationDecision:
    thresholds = RECOMMENDATION_POLICY["decision_thresholds"]
    accuracy = ability.avg_script_accuracy_recent
    errors = ability.avg_error_count_recent
    speech_rate = ability.avg_speech_rate_recent
    loudness = ability.avg_loudness_recent
    reviewed_count = (ability.evidence or {}).get("reviewed_assessment_count", 0)
    content_level = ability.current_content_level
    autonomy_level = ability.current_autonomy_level

    has_measured_values = any(value is not None for value in (accuracy, errors, speech_rate, loudness))
    if has_measured_values and (ability.evidence or {}).get("profile_eligibility") is not True:
        return RecommendationDecision(
            recommended_type=TrainingType.repeat,
            headline="先保持当前训练",
            reason="当前记录未通过正式证据准入，旧策略已停止正式调难；请完成一次通过质量检查的新训练。",
            focus_points=["保持当前任务难度", "重新采集一段清楚录音", "等待治疗师复核"],
            suggested_minutes=8,
            content_level=content_level,
            autonomy_level=autonomy_level,
            adaptation_note="安全门控：证据不可用于画像或推荐，未执行正式难度决策。",
        )

    loudness_unit = (ability.evidence or {}).get("loudness_unit")
    if loudness is not None and loudness_unit != "dBFS":
        return RecommendationDecision(
            recommended_type=TrainingType.repeat,
            headline="先保持当前训练",
            reason="当前历史响度记录缺少可验证单位，旧策略已停止正式调难；请完成一次通过质量检查的新训练。",
            focus_points=["保持当前任务难度", "重新采集一段清楚录音", "等待治疗师复核"],
            suggested_minutes=8,
            content_level=content_level,
            autonomy_level=autonomy_level,
            adaptation_note="安全门控：响度单位不明，未执行正式难度决策。",
        )

    if accuracy is None or errors is None:
        decision = RecommendationDecision(
            recommended_type=TrainingType.repeat,
            headline="先从熟悉短句开始",
            reason="系统还需要几次训练记录来了解你的表达状态，短句跟读最容易形成稳定反馈。",
            focus_points=["把一句话说完整", "不用着急，先听清再开口", "完成后查看系统反馈"],
            suggested_minutes=8,
            content_level=content_level,
            autonomy_level=autonomy_level,
        )
    elif errors >= thresholds["high_errors"]["value"] or accuracy < thresholds["low_accuracy"]["value"]:
        decision = RecommendationDecision(
            recommended_type=TrainingType.repeat,
            headline="今天先稳住一句话",
            reason="最近表达里需要留意的地方较多，先练短句能减少负担，也方便看清具体进步。",
            focus_points=["慢一点说完整", "重点减少漏字和错字", "每次只关注一个小目标"],
            suggested_minutes=10,
            content_level=content_level,
            autonomy_level=autonomy_level,
        )
    elif loudness is not None and loudness < thresholds["low_loudness"]["value"]:
        decision = RecommendationDecision(
            recommended_type=TrainingType.repeat,
            headline="先练声音稳定",
            reason="最近声音偏轻，跟读训练更适合把气息、音量和句子完整度一起稳住。",
            focus_points=["坐直后再开始", "先吸气再说句子", "让声音保持到句尾"],
            suggested_minutes=10,
            content_level=content_level,
            autonomy_level=autonomy_level,
        )
    elif speech_rate is not None and speech_rate < thresholds["slow_speech_rate"]["value"]:
        decision = RecommendationDecision(
            recommended_type=TrainingType.repeat,
            headline="练一组连贯短句",
            reason="最近说话节奏偏慢，可以用熟悉短句练习连续表达，重点减少不必要的停顿。",
            focus_points=["一句话尽量连起来", "停顿少一点", "保持清楚比追求快更重要"],
            suggested_minutes=12,
            content_level=content_level,
            autonomy_level=autonomy_level,
        )
    elif level_number(content_level) >= thresholds["scenario_content_min"]["value"] and level_number(autonomy_level) >= thresholds["scenario_autonomy_min"]["value"]:
        confidence_note = "治疗师复核已经纳入画像。" if reviewed_count else "当前建议来自系统画像，等待治疗师复核后会更稳。"
        decision = RecommendationDecision(
            recommended_type=TrainingType.scenario,
            headline="可以试试生活场景表达",
            reason=f"最近短句表现比较稳定，适合增加一点自主表达。{confidence_note}",
            focus_points=["围绕一个生活场景说清需求", "先说重点，再补充细节", "不用追求很长"],
            suggested_minutes=12,
            content_level=content_level,
            autonomy_level=autonomy_level,
        )
    else:
        decision = RecommendationDecision(
            recommended_type=TrainingType.repeat,
            headline="继续当前节奏",
            reason="目前适合保持短句练习，让表达完整度和稳定性继续累积。",
            focus_points=["每天完成一小组", "关注反馈里的一个建议", "稳定后再增加场景表达"],
            suggested_minutes=10,
            content_level=content_level,
            autonomy_level=autonomy_level,
        )
    return apply_adaptive_adjustment(decision, trend)


def apply_adaptive_adjustment(decision: RecommendationDecision, trend: TrendPolicyResult | None) -> RecommendationDecision:
    if trend is None:
        return decision
    if trend.status == "effective":
        decision.adaptation_note = "近期观察到积极变化；phase4.3 已冻结，正式 L/S 保持不变。"
        decision.reason = f"{decision.reason}{decision.adaptation_note}"
    elif trend.status == "needs_adjustment":
        decision.adaptation_note = "近期观察到不稳定变化；phase4.3 已冻结，正式 L/S 保持不变并建议治疗师复核。"
        decision.reason = f"{decision.reason}{decision.adaptation_note}"
    elif trend.status == "mixed":
        decision.adaptation_note = "近期表现有波动，系统暂时保持当前难度。"
        decision.reason = f"{decision.reason}{decision.adaptation_note}"
    return decision


def analyze_trend_by_policy(completed_effects: list[Any]) -> TrendPolicyResult:
    if len(completed_effects) < 2:
        count = len(completed_effects)
        return TrendPolicyResult(
            status="observing",
            summary="推荐后完成训练次数还不够，暂时只适合观察。",
            hint="建议继续保持当前推荐，并等待至少两次完成评分后再判断是否调整。",
            evidence=[f"已完成推荐训练 {count} 次"],
            attribution_points=["样本不足，先积累训练记录"],
            reminder_level="info",
            patient_reminder="先按今天建议完成一组训练。",
            family_reminder="陪伴时重点鼓励完成训练，不急着判断效果。",
            therapist_reminder="建议继续观察，暂不需要调整策略。",
        )

    first = completed_effects[0]
    latest = completed_effects[-1]
    deltas = metric_deltas(first.metrics, latest.metrics)
    evidence = build_trend_evidence(deltas)
    attribution = build_attribution_points(deltas, first.metrics, latest.metrics)
    positive = 0
    negative = 0
    config = RECOMMENDATION_POLICY["adaptive_adjustment"]
    if deltas.get("script_accuracy", 0) >= config["accuracy_delta"]["value"]:
        positive += 1
    elif deltas.get("script_accuracy", 0) <= -config["accuracy_delta"]["value"]:
        negative += 1
    if deltas.get("error_count", 0) <= -config["error_delta"]["value"]:
        positive += 1
    elif deltas.get("error_count", 0) >= config["error_delta"]["value"]:
        negative += 1
    if "speech_rate" in deltas and metric_closer(latest.metrics.get("speech_rate"), first.metrics.get("speech_rate"), RECOMMENDATION_POLICY["target_speech_rate"]["value"], config["speech_rate_margin"]["value"]):
        positive += 1
    if "loudness" in deltas and metric_closer_to_range(
        latest.metrics.get("loudness"), first.metrics.get("loudness"), range_bounds("repeat_loudness_reference"), config["loudness_margin"]["value"]
    ):
        positive += 1

    if positive >= config["effective_min_positive_signals"]["value"] and negative == 0:
        return TrendPolicyResult(
            status="effective",
            summary="推荐后的训练表现正在变好。",
            hint="建议继续使用当前推荐方向，下一次可小幅增加句子长度或自主表达比例。",
            evidence=evidence,
            attribution_points=attribution or ["完整度、错误或节奏指标呈改善趋势"],
            reminder_level="success",
            patient_reminder="今天可以在当前基础上稍微挑战一点。",
            family_reminder="患者最近有进步，陪伴时可以肯定完成训练这件事。",
            therapist_reminder="推荐方向有效，可继续观察是否适合小幅提高难度。",
        )
    if negative >= config["needs_adjustment_negative_signals"]["value"]:
        return TrendPolicyResult(
            status="needs_adjustment",
            summary="推荐后的表现没有稳定改善。",
            hint="建议治疗师重新检查推荐方向，必要时降低难度或改回更熟悉的跟读训练。",
            evidence=evidence,
            attribution_points=attribution or ["错误或完整度指标提示当前任务可能偏难"],
            reminder_level="warning",
            patient_reminder="今天先降低难度，把一句话说完整就很好。",
            family_reminder="陪伴时少催促，多给患者留出回答时间。",
            therapist_reminder="建议关注任务难度、疲劳和场景自主度，必要时补充自然语言调整说明。",
        )
    return TrendPolicyResult(
        status="mixed",
        summary="推荐后的表现有变化，但趋势还不稳定。",
        hint="建议保持当前推荐一到两次，同时关注错误次数和说话节奏是否继续改善。",
        evidence=evidence,
        attribution_points=attribution or ["部分指标改善，部分指标仍需观察"],
        reminder_level="info",
        patient_reminder="今天保持当前节奏，完成一组就可以。",
        family_reminder="表现有波动很常见，陪伴时以稳定完成为主。",
        therapist_reminder="建议继续观察一到两次，再判断是否需要调整。",
    )


def sequence_steps() -> list[dict[str, Any]]:
    return RECOMMENDATION_POLICY["sequence_steps"]


def metric_deltas(first: dict[str, float], latest: dict[str, float]) -> dict[str, float]:
    return {
        name: round(latest[name] - first[name], 1)
        for name in ["script_accuracy", "error_count", "speech_rate", "loudness"]
        if name in first and name in latest
    }


def build_trend_evidence(deltas: dict[str, float]) -> list[str]:
    labels = {
        "script_accuracy": ("完整度", "%"),
        "error_count": ("错误", "次"),
        "speech_rate": ("语速", "字/min"),
        "loudness": ("相对响度", "dBFS"),
    }
    points = []
    for key, value in deltas.items():
        label, unit = labels.get(key, (key, ""))
        direction = "提升" if value > 0 else "下降" if value < 0 else "持平"
        points.append(f"{label}{direction} {abs(value):g}{unit}")
    return points or ["暂无可比较指标"]


def build_attribution_points(deltas: dict[str, float], first: dict[str, float], latest: dict[str, float]) -> list[str]:
    points = []
    if deltas.get("script_accuracy", 0) >= config_value("phase43_accuracy_delta"):
        points.append("表达完整度提升，是主要积极信号。")
    elif deltas.get("script_accuracy", 0) <= -config_value("phase43_accuracy_delta"):
        points.append("表达完整度下降，任务可能偏难或状态波动。")
    if deltas.get("error_count", 0) <= -config_value("phase43_error_delta"):
        points.append("错误次数减少，说明当前练习有助于稳定表达。")
    elif deltas.get("error_count", 0) >= config_value("phase43_error_delta"):
        points.append("错误次数增加，需要关注句子长度和疲劳。")
    if metric_closer(latest.get("speech_rate"), first.get("speech_rate"), RECOMMENDATION_POLICY["target_speech_rate"]["value"], 0):
        points.append("说话节奏更接近稳定区间。")
    if metric_closer_to_range(latest.get("loudness"), first.get("loudness"), range_bounds("repeat_loudness_reference"), 0):
        points.append("声音状态更接近自然清楚的范围。")
    return points[:4]


def metric_closer(latest: float | None, first: float | None, target: float, margin: float) -> bool:
    if first is None or latest is None:
        return False
    return abs(latest - target) + margin < abs(first - target)


def metric_closer_to_range(
    latest: float | None,
    first: float | None,
    reference: tuple[float, float],
    margin: float,
) -> bool:
    if first is None or latest is None:
        return False
    minimum, maximum = reference

    def distance(value: float) -> float:
        if minimum <= value <= maximum:
            return 0.0
        return minimum - value if value < minimum else value - maximum

    return distance(latest) + margin < distance(first)


def level_number(level: str) -> int:
    try:
        return int(level[1:])
    except (TypeError, ValueError):
        return 1


def shift_level(level: str, delta: int, max_level: int) -> str:
    return f"{level[:1] or 'L'}{max(1, min(max_level, level_number(level) + delta))}"
