from dataclasses import dataclass
from statistics import mean, median


POLICY_VERSION = "training-comparability-v1"


@dataclass(frozen=True)
class ComparableSet:
    status: str
    included_measurement_ids: list[str]
    excluded: list[dict]
    comparison_key: str | None
    policy_version: str = POLICY_VERSION


def build_comparable_set(metrics) -> ComparableSet:
    rows = list(metrics)
    eligible = [
        row
        for row in rows
        if row.status == "measured"
        and row.decision_eligible
        and row.comparison_key
        and row.source_type not in {"mock", "demo"}
        and row.quality.get("source_status") != "mock"
    ]
    if not eligible:
        return ComparableSet(
            status="not_comparable",
            included_measurement_ids=[],
            excluded=[{"id": str(row.id), "reason_codes": exclusion_reasons(row)} for row in rows],
            comparison_key=None,
        )
    key_counts: dict[str, int] = {}
    for row in eligible:
        key_counts[row.comparison_key] = key_counts.get(row.comparison_key, 0) + 1
    comparison_key = max(key_counts, key=lambda item: (key_counts[item], item))
    included = [row for row in eligible if row.comparison_key == comparison_key]
    excluded = [
        {"id": str(row.id), "reason_codes": ["comparison_key_mismatch"]}
        for row in eligible
        if row.comparison_key != comparison_key
    ]
    excluded.extend(
        {"id": str(row.id), "reason_codes": exclusion_reasons(row)} for row in rows if row not in eligible
    )
    return ComparableSet(
        status="comparable" if len(included) >= 2 and not excluded else "partially_comparable" if len(included) >= 2 else "not_comparable",
        included_measurement_ids=[str(row.id) for row in included],
        excluded=excluded,
        comparison_key=comparison_key,
    )


def exclusion_reasons(metric) -> list[str]:
    reasons = []
    if metric.status != "measured":
        reasons.append(f"status:{metric.status}")
    if not metric.decision_eligible:
        reasons.append("not_decision_eligible")
    if not metric.comparison_key:
        reasons.append("missing_comparison_key")
    if metric.source_type in {"mock", "demo"} or metric.quality.get("source_status") == "mock":
        reasons.append("mock_excluded")
    return reasons or ["comparison_key_mismatch"]


def trend_fact(metrics, comparable_set: ComparableSet) -> dict:
    by_id = {str(row.id): row for row in metrics}
    rows = [by_id[item] for item in comparable_set.included_measurement_ids if item in by_id]
    rows.sort(key=lambda item: item.measured_at)
    if comparable_set.status == "not_comparable" or len(rows) < 2:
        return {
            "status": "insufficient",
            "sample_count": len(rows),
            "comparison_key": comparable_set.comparison_key,
            "policy_version": comparable_set.policy_version,
        }
    values = [float(row.value) for row in rows if row.value is not None]
    if len(values) < 2:
        return {"status": "insufficient", "sample_count": len(values), "comparison_key": comparable_set.comparison_key}
    x_mean = (len(values) - 1) / 2
    denominator = sum((index - x_mean) ** 2 for index in range(len(values))) or 1
    slope = sum((index - x_mean) * (value - mean(values)) for index, value in enumerate(values)) / denominator
    return {
        "status": "measured",
        "sample_count": len(values),
        "delta": round(values[-1] - values[0], 3),
        "slope": round(slope, 3),
        "mean": round(mean(values), 3),
        "median": round(median(values), 3),
        "stability": round(max(values) - min(values), 3),
        "comparison_key": comparable_set.comparison_key,
        "policy_version": comparable_set.policy_version,
        "from": rows[0].measured_at.isoformat(),
        "to": rows[-1].measured_at.isoformat(),
    }

