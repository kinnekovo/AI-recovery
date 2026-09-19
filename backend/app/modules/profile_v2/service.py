"""Profile V2 builder.  It is deliberately a read-only consumer of canonical V3 runs."""
from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from datetime import datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.database.base import utc_now
from app.modules.assessment.comparability import compare as compare_assessments
from app.modules.assessment.model import AssessmentSession
from app.modules.calibration.model import MetricRegistry
from app.modules.evaluation_runs.model import EvaluationAdoptionStatus, EvaluationRun
from app.modules.profile_v2.mapping import (PROFILE_EVIDENCE_POLICY, PROFILE_EVIDENCE_POLICY_VERSION,
    PROFILE_MAPPING_VERSION, PROFILE_SCHEMA_VERSION, mapping_for)
from app.modules.profile_v2.model import PatientProfileSnapshot, ProfileBuildFailure, ProfileEvidenceLink
from app.modules.users.model import PatientProfile


def _fingerprint(items: list[dict], as_of) -> str:
    data = {"schema": PROFILE_SCHEMA_VERSION, "mapping": PROFILE_MAPPING_VERSION, "policy": PROFILE_EVIDENCE_POLICY_VERSION,
            "as_of": as_of.isoformat() if as_of else None, "evidence": items}
    return hashlib.sha256(json.dumps(data, ensure_ascii=False, sort_keys=True, default=str).encode()).hexdigest()


def _registry(db: Session) -> dict[str, MetricRegistry]:
    return {row.metric_code: row for row in db.scalars(select(MetricRegistry))}


def _eligible(run, dimension, registry):
    if not run.profile_eligibility or run.result_status != "formal" or dimension.status != "measured" or dimension.value is None:
        return None, "canonical_ineligible"
    mapped = mapping_for(run.domain, dimension.dimension_code)
    if not mapped:
        return None, "unmapped_dimension"
    if mapped["source_kind"] == "clinical_manual":
        return mapped, None
    metric = registry.get(dimension.dimension_code)
    if not metric:
        return None, "metric_not_registered"
    if metric.status in {"experimental", "shadow", "suspended"}:
        return None, f"metric_{metric.status}"
    # provisional evidence is retained in links/therapist payload, but never a formal aggregate by default.
    if metric.status == "provisional":
        return None, "metric_provisional_not_formal"
    if metric.status != "promoted":
        return None, "metric_not_promoted"
    return mapped, None


def _trend(values: list[dict], source_kind: str) -> tuple[str, str]:
    if len(values) < 2: return "insufficient", "insufficient_observations"
    if source_kind == "clinical_manual":
        sessions = [v.get("assessment") for v in values]
        if any(s is None for s in sessions): return "not_comparable", "clinical_metadata_missing"
        comparisons = [compare_assessments(sessions[i - 1], sessions[i]) for i in range(1, len(sessions))]
        if any(c["status"] != "comparable" for c in comparisons): return "not_comparable", "clinical_not_comparable"
    delta = values[-1]["value"] - values[0]["value"]
    direction = values[-1]["direction"]
    if delta == 0: return "stable", "numeric_no_change"
    if direction == "unknown": return "mixed", "direction_unknown"
    positive = delta > 0
    rising = positive if direction == "high" else not positive
    return ("rising" if rising else "falling"), "numeric_direction_only"


def _payload(evidence: list[dict], excluded: list[str]) -> tuple[dict, str]:
    grouped = defaultdict(list)
    for item in evidence:
        # Manual and automatic values are intentionally different groups.
        grouped[(item["profile_dimension_code"], item["unit"], item["source_kind"])].append(item)
    dimensions = []
    required = PROFILE_EVIDENCE_POLICY["minimum_supported_observations"]
    for (code, unit, source_kind), rows in sorted(grouped.items()):
        rows.sort(key=lambda item: item["timestamp"])
        window = rows[-PROFILE_EVIDENCE_POLICY["current_window_size"]:]
        trend, trend_status = _trend(window, source_kind)
        count = len(rows)
        sufficiency = "sufficient" if count >= required else "limited"
        dimensions.append({"code": code, "status": "measured", "current_value": sum(x["value"] for x in window) / len(window),
                           "unit": unit, "current_source_kind": source_kind, "observation_count": count,
                           "first_observed_at": rows[0]["timestamp"].isoformat(), "latest_observed_at": rows[-1]["timestamp"].isoformat(),
                           "trend": trend, "trend_status": trend_status, "evidence_sufficiency": sufficiency,
                           "evidence_quality_warnings": []})
    overall = "complete" if dimensions and all(d["evidence_sufficiency"] == "sufficient" for d in dimensions) else ("partial" if dimensions else "insufficient")
    return {"profile_schema_version": PROFILE_SCHEMA_VERSION, "mapping_version": PROFILE_MAPPING_VERSION,
             "evidence_policy_version": PROFILE_EVIDENCE_POLICY_VERSION, "status": overall, "dimensions": dimensions,
             "excluded_reason_codes": sorted(set(excluded)), "limitations": ["工程证据画像，不构成临床诊断或疗效结论。"]}, overall


def build_profile(db: Session, patient_profile_id: UUID, as_of: datetime | None = None) -> PatientProfileSnapshot:
    if not db.get(PatientProfile, patient_profile_id):
        raise HTTPException(status_code=404, detail="患者档案不存在")
    statement = select(EvaluationRun).where(EvaluationRun.patient_profile_id == patient_profile_id,
        EvaluationRun.adoption_status == EvaluationAdoptionStatus.adopted.value).options(selectinload(EvaluationRun.dimension_results))
    if as_of: statement = statement.where(EvaluationRun.created_at <= as_of)
    runs = list(db.scalars(statement.order_by(EvaluationRun.created_at)))
    registry = _registry(db); evidence=[]; excluded=[]
    for run in runs:
        assessment = db.get(AssessmentSession, run.source_id) if run.source_type == "assessment_session" else None
        for dimension in run.dimension_results:
            mapped, reason = _eligible(run, dimension, registry)
            if not mapped:
                excluded.append(reason); continue
            metric = registry.get(dimension.dimension_code)
            evidence.append({"run_id": str(run.id), "source_dimension_code": dimension.dimension_code, "profile_dimension_code": mapped["profile_dimension_code"],
                "source_kind": mapped["source_kind"], "unit": dimension.unit, "value": float(dimension.value), "direction": mapped["direction"],
                "timestamp": run.created_at, "source_type": run.source_type, "source_id": str(run.source_id), "metric_status": metric.status if metric else "clinical_manual",
                "provider_version": str((run.input_provenance or {}).get("providers", {}).get("version") or run.algorithm_version), "assessment": assessment,
                "canonical_result_status": run.result_status})
    fingerprint_items = [{k:v for k,v in item.items() if k not in {"assessment", "timestamp"}} | {"timestamp": item["timestamp"].isoformat()} for item in evidence]
    fingerprint = _fingerprint(fingerprint_items, as_of)
    existing = db.scalar(select(PatientProfileSnapshot).where(PatientProfileSnapshot.patient_profile_id == patient_profile_id, PatientProfileSnapshot.evidence_fingerprint == fingerprint))
    if existing: return existing
    payload, snapshot_status = _payload(evidence, excluded)
    previous = db.scalar(select(PatientProfileSnapshot).where(PatientProfileSnapshot.patient_profile_id == patient_profile_id).order_by(PatientProfileSnapshot.generated_at.desc()))
    try:
        snapshot = PatientProfileSnapshot(patient_profile_id=patient_profile_id, profile_schema_version=PROFILE_SCHEMA_VERSION,
            mapping_version=PROFILE_MAPPING_VERSION, evidence_policy_version=PROFILE_EVIDENCE_POLICY_VERSION, as_of=as_of,
            status=snapshot_status, previous_snapshot_id=previous.id if previous else None, evidence_fingerprint=fingerprint, payload=payload)
        db.add(snapshot); db.flush()
        for item in evidence:
            db.add(ProfileEvidenceLink(snapshot_id=snapshot.id, patient_profile_id=patient_profile_id, evaluation_run_id=UUID(item["run_id"]),
                assessment_session_id=item["assessment"].id if item["assessment"] else None, source_type=item["source_type"], source_id=UUID(item["source_id"]),
                profile_dimension_code=item["profile_dimension_code"], source_dimension_code=item["source_dimension_code"], source_kind=item["source_kind"], unit=item["unit"], metric_status=item["metric_status"], provider_version=item["provider_version"], canonical_result_status=item["canonical_result_status"], review_state=None, evidence_timestamp=item["timestamp"], metadata_snapshot={"mapping_version": PROFILE_MAPPING_VERSION, "direction": item["direction"]}))
        db.commit(); db.refresh(snapshot)
    except IntegrityError:
        db.rollback()
        snapshot = db.scalar(select(PatientProfileSnapshot).where(PatientProfileSnapshot.patient_profile_id == patient_profile_id, PatientProfileSnapshot.evidence_fingerprint == fingerprint))
        if snapshot: return snapshot
        raise
    _resolve_failure(db, patient_profile_id, fingerprint, snapshot.id)
    return snapshot


def get_latest_profile(db: Session, patient_profile_id: UUID):
    return db.scalar(select(PatientProfileSnapshot).where(PatientProfileSnapshot.patient_profile_id == patient_profile_id).order_by(PatientProfileSnapshot.generated_at.desc()))

def list_history(db: Session, patient_profile_id: UUID):
    return list(db.scalars(select(PatientProfileSnapshot).where(PatientProfileSnapshot.patient_profile_id == patient_profile_id).order_by(PatientProfileSnapshot.generated_at.desc())))

def evidence_for_snapshot(db: Session, snapshot_id: UUID):
    return list(db.scalars(select(ProfileEvidenceLink).where(ProfileEvidenceLink.snapshot_id == snapshot_id).order_by(ProfileEvidenceLink.evidence_timestamp.desc())))

def get_policy_profile(db: Session, patient_profile_id: UUID):
    snapshot = get_latest_profile(db, patient_profile_id)
    if not snapshot: return None
    return {"snapshot_id": str(snapshot.id), "profile_version": snapshot.profile_schema_version, "status": snapshot.status,
            "dimensions": [d for d in snapshot.payload.get("dimensions", []) if d.get("evidence_sufficiency") == "sufficient"]}

def record_build_failure(db, patient_profile_id, input_fingerprint, failure_stage, error_code="profile_build_failed"):
    row = db.scalar(select(ProfileBuildFailure).where(ProfileBuildFailure.patient_profile_id == patient_profile_id, ProfileBuildFailure.input_fingerprint == input_fingerprint))
    now=utc_now()
    if row: row.retry_count += 1; row.retry_required=True; row.failure_stage=failure_stage; row.error_code=error_code; row.last_failed_at=now; row.last_retry_at=now
    else: db.add(ProfileBuildFailure(patient_profile_id=patient_profile_id, input_fingerprint=input_fingerprint, failure_stage=failure_stage, error_code=error_code, retry_required=True, retry_count=1, last_failed_at=now, last_retry_at=now))
    db.commit()

def _resolve_failure(db, patient_profile_id, fingerprint, snapshot_id):
    rows=list(db.scalars(select(ProfileBuildFailure).where(ProfileBuildFailure.patient_profile_id == patient_profile_id, ProfileBuildFailure.input_fingerprint == fingerprint, ProfileBuildFailure.retry_required.is_(True))))
    if rows:
        for row in rows: row.retry_required=False; row.resolved_snapshot_id=snapshot_id; row.last_retry_at=utc_now()
        db.commit()
