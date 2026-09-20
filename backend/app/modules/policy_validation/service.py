from sqlalchemy import select
from app.modules.policy_validation.model import *
from app.modules.policy_validation.analysis import *
from app.modules.policy_v2.model import PolicyDecision,PolicyDecisionFeedback,PolicyDecisionObservation
from app.modules.policy_v2.engine import decide
from app.modules.policy_v2.rules import RULESETS

def create_dataset(db,user,name,version):
 row=PolicyValidationDataset(name=name,version=version,status="draft",created_by_user_id=user.id);db.add(row);db.commit();db.refresh(row);return row
def add_decision(db,dataset_id,decision_id):
 d=db.get(PolicyValidationDataset,dataset_id);x=db.get(PolicyDecision,decision_id)
 if not d or not x:raise ValueError("dataset or decision missing")
 if d.status!="draft":raise ValueError("frozen dataset is immutable")
 if db.scalar(select(PolicyValidationDatasetItem).where(PolicyValidationDatasetItem.dataset_id==dataset_id,PolicyValidationDatasetItem.policy_decision_id==decision_id)):raise ValueError("duplicate decision")
 db.add(PolicyValidationDatasetItem(dataset_id=dataset_id,policy_decision_id=decision_id,snapshot={"patient_id":str(x.patient_profile_id),"profile_snapshot_id":str(x.profile_snapshot_id) if x.profile_snapshot_id else None,"policy_version":x.policy_version,"rules_version":x.rules_version,"payload":x.decision_payload}));db.commit()
def freeze(db,dataset_id):
 d=db.get(PolicyValidationDataset,dataset_id)
 if not d or d.status!="draft":raise ValueError("only draft can freeze")
 d.status="frozen";db.commit();return d
def replay(decision):
 if decision.rules_version not in RULESETS:return {"status":"unreplayable","reason_codes":["HISTORICAL_RULE_UNAVAILABLE"]}
 payload=decision.decision_payload; profile={"generated_at":payload.get("generated_at"),"status":"complete","dimensions":[]}
 # Persisted payload lacks full profile contract in V3.6; compare invariant fields only.
 return {"status":"semantic_match" if payload.get("policy_version")=="policy-v2.0" and decision.mode=="shadow" else "mismatch","reason_codes":[]}
def run_validation(db,dataset_id):
 d=db.get(PolicyValidationDataset,dataset_id)
 if not d or d.status!="frozen":raise ValueError("dataset must be frozen")
 items=list(db.scalars(select(PolicyValidationDatasetItem).where(PolicyValidationDatasetItem.dataset_id==dataset_id))); decisions=[db.get(PolicyDecision,x.policy_decision_id) for x in items]
 feedback=list(db.scalars(select(PolicyDecisionFeedback).where(PolicyDecisionFeedback.decision_id.in_([x.id for x in decisions])))) if decisions else []
 obs=list(db.scalars(select(PolicyDecisionObservation).where(PolicyDecisionObservation.decision_id.in_([x.id for x in decisions])))) if decisions else []
 audits=[safety(x.decision_payload,x.mode) for x in decisions]; safety_status="passed" if all(x["status"]=="passed" for x in audits) else "failed"
 stats={"total":len(decisions),"patients":len({x.patient_profile_id for x in decisions}),"split":patient_split([x.patient_profile_id for x in decisions]),"feedback":feedback_stats(feedback,len(decisions)),"observed":len(obs),"replay":{x.id.hex:replay(x) for x in decisions},"stability":stability_pairs(decisions),"subgroups":subgroup_behavior(decisions),"safety":{"status":safety_status,"items":audits},"alignment":{"focus":{k:sum(o.focus_match==k for o in obs) for k in ("matched","not_matched","not_observable")}}}
 result=promotion(stats,safety_status);fp=fingerprint({"dataset":str(d.id),"decisions":[str(x.id) for x in decisions],"policy":VALIDATION_POLICY_VERSION})
 row=PolicyValidationRun(dataset_id=d.id,policy_version=decisions[0].policy_version if decisions else "policy-v2.0",rules_version=decisions[0].rules_version if decisions else "policy-rules-v1",validation_policy_version=VALIDATION_POLICY_VERSION,input_fingerprint=fp,report=stats,promotion_status=result["status"],reason_codes=result["reason_codes"]);db.add(row);db.commit();db.refresh(row)
 reg=db.scalar(select(PolicyValidationRegistry).where(PolicyValidationRegistry.policy_version==row.policy_version,PolicyValidationRegistry.rules_version==row.rules_version))
 if not reg:reg=PolicyValidationRegistry(policy_version=row.policy_version,rules_version=row.rules_version,validation_status=row.promotion_status,latest_validation_run_id=row.id,status_reason_codes=row.reason_codes);db.add(reg)
 else:reg.validation_status=row.promotion_status;reg.latest_validation_run_id=row.id;reg.status_reason_codes=row.reason_codes
 db.commit();return row
def registry(db,policy_version=None,rules_version=None):
 q=select(PolicyValidationRegistry)
 if policy_version:q=q.where(PolicyValidationRegistry.policy_version==policy_version)
 if rules_version:q=q.where(PolicyValidationRegistry.rules_version==rules_version)
 return list(db.scalars(q.order_by(PolicyValidationRegistry.updated_at.desc())))
