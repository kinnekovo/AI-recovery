from __future__ import annotations
import hashlib,json
from uuid import UUID
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.database.base import utc_now
from app.modules.policy_v2.engine import decide
from app.modules.policy_v2.explain import explain
from app.modules.policy_v2.model import PolicyDecision,PolicyDecisionFeedback,PolicyDecisionObservation,PolicyShadowFailure
from app.modules.policy_v2.rules import POLICY_VERSION,RULES_VERSION
from app.modules.profile_v2.service import get_policy_profile
from app.modules.training.model import TrainingSession

def _fingerprint(profile):
    data={"snapshot_id":profile.get("snapshot_id") if profile else None,"policy":POLICY_VERSION,"rules":RULES_VERSION,"contract":profile}
    return hashlib.sha256(json.dumps(data,sort_keys=True,default=str).encode()).hexdigest()

def generate_shadow(db:Session, patient_profile_id:UUID)->PolicyDecision:
    profile=get_policy_profile(db,patient_profile_id) # sole Profile V2 integration point
    fingerprint=_fingerprint(profile)
    existing=db.scalar(select(PolicyDecision).where(PolicyDecision.patient_profile_id==patient_profile_id,PolicyDecision.input_fingerprint==fingerprint))
    if existing:return existing
    try:
        output=decide(profile); snapshot_id=UUID(profile["snapshot_id"]) if profile and profile.get("snapshot_id") else None
        row=PolicyDecision(patient_profile_id=patient_profile_id,profile_snapshot_id=snapshot_id,policy_version=POLICY_VERSION,rules_version=RULES_VERSION,
            profile_version=profile.get("profile_version") if profile else None,profile_mapping_version=profile.get("mapping_version") if profile else None,
            profile_evidence_policy_version=profile.get("evidence_policy_version") if profile else None,mode="shadow",status=output["status"],input_fingerprint=fingerprint,
            decision_payload=output,reason_codes=output["reason_codes"],warnings=output["warnings"])
        db.add(row);db.commit();db.refresh(row);_resolve_failure(db,patient_profile_id,fingerprint,row.id);return row
    except IntegrityError:
        db.rollback(); row=db.scalar(select(PolicyDecision).where(PolicyDecision.patient_profile_id==patient_profile_id,PolicyDecision.input_fingerprint==fingerprint))
        if row:return row
        raise
    except Exception:
        db.rollback();record_failure(db,patient_profile_id,fingerprint,profile.get("snapshot_id") if profile else None,"engine");raise

def latest(db,patient_profile_id):return db.scalar(select(PolicyDecision).where(PolicyDecision.patient_profile_id==patient_profile_id).order_by(PolicyDecision.generated_at.desc()))
def history(db,patient_profile_id):return list(db.scalars(select(PolicyDecision).where(PolicyDecision.patient_profile_id==patient_profile_id).order_by(PolicyDecision.generated_at.desc())))
def detail(db,decision_id):return db.get(PolicyDecision,decision_id)
def explanation(db,decision_id):
    row=detail(db,decision_id)
    return explain(row.decision_payload) if row else None

def add_feedback(db,decision_id,therapist_user_id,payload):
    rounds=db.scalar(select(func.max(PolicyDecisionFeedback.review_round)).where(PolicyDecisionFeedback.decision_id==decision_id,PolicyDecisionFeedback.therapist_user_id==therapist_user_id)) or 0
    row=PolicyDecisionFeedback(decision_id=decision_id,therapist_user_id=therapist_user_id,review_round=rounds+1,agreement=payload.agreement,reason_codes=payload.reason_codes,comment=payload.comment);db.add(row);db.commit();db.refresh(row);return row

def observe_policy_outcome(db,decision_id,training_session_id):
    decision=db.get(PolicyDecision,decision_id);session=db.get(TrainingSession,training_session_id)
    if not decision or not session or session.patient_profile_id!=decision.patient_profile_id: raise ValueError("policy decision/training session ownership mismatch")
    existing=db.scalar(select(PolicyDecisionObservation).where(PolicyDecisionObservation.decision_id==decision_id,PolicyDecisionObservation.training_session_id==training_session_id))
    if existing:return existing
    focus=decision.decision_payload.get("training_focus",[]); first=focus[0]["dimension_code"] if focus else None
    actual_type=getattr(session.training_type,"value",session.training_type)
    focus_match="not_observable" if not first else ("matched" if first.startswith(str(actual_type)+".") else "not_matched")
    row=PolicyDecisionObservation(decision_id=decision_id,training_session_id=training_session_id,focus_match=focus_match,difficulty_match="not_observable",reassessment_match="not_observable",actual_training_snapshot={"training_type":actual_type,"legacy_recommendation_source":session.recommendation_source})
    db.add(row);decision.status="observed";db.commit();db.refresh(row);return row

def analytics(db,patient_profile_id):
    rows=history(db,patient_profile_id);feedback=list(db.scalars(select(PolicyDecisionFeedback).join(PolicyDecision).where(PolicyDecision.patient_profile_id==patient_profile_id)));obs=list(db.scalars(select(PolicyDecisionObservation).join(PolicyDecision).where(PolicyDecision.patient_profile_id==patient_profile_id)))
    def count(values):
      result={}
      for x in values:result[x]=result.get(x,0)+1
      return result
    return {"decision_count":len(rows),"focus_distribution":count(f["dimension_code"] for row in rows for f in row.decision_payload.get("training_focus",[]) if f["priority"]!="not_eligible"),"difficulty_distribution":count(row.decision_payload.get("difficulty",{}).get("recommended_difficulty_action") for row in rows),"reassessment_distribution":count(row.decision_payload.get("reassessment",{}).get("signal") for row in rows),"therapist_agreement_distribution":count(row.agreement for row in feedback),"shadow_vs_actual_match_distribution":count(row.focus_match for row in obs)}

def record_failure(db,patient_profile_id,fingerprint,snapshot_id,failure_stage,error_code="policy_shadow_failed"):
    row=db.scalar(select(PolicyShadowFailure).where(PolicyShadowFailure.patient_profile_id==patient_profile_id,PolicyShadowFailure.input_fingerprint==fingerprint));now=utc_now()
    if row: row.retry_count+=1;row.retry_required=True;row.failure_stage=failure_stage;row.error_code=error_code;row.last_failed_at=now;row.last_retry_at=now
    else: db.add(PolicyShadowFailure(patient_profile_id=patient_profile_id,profile_snapshot_id=UUID(snapshot_id) if snapshot_id else None,input_fingerprint=fingerprint,failure_stage=failure_stage,error_code=error_code,retry_required=True,retry_count=1,last_failed_at=now,last_retry_at=now))
    db.commit()
def _resolve_failure(db,pid,fingerprint,decision_id):
    rows=list(db.scalars(select(PolicyShadowFailure).where(PolicyShadowFailure.patient_profile_id==pid,PolicyShadowFailure.input_fingerprint==fingerprint,PolicyShadowFailure.retry_required.is_(True))))
    for row in rows:row.retry_required=False;row.resolved_decision_id=decision_id;row.last_retry_at=utc_now()
    if rows:db.commit()
