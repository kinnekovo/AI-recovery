import hashlib,json
from sqlalchemy import select
from app.database.base import utc_now
from app.modules.controlled_governance.model import *
from app.modules.controlled_governance.policy import *
from app.modules.controlled_policy.model import *
from app.modules.controlled_policy.adapter import VERSION as ADAPTER_VERSION
from app.modules.policy_validation.model import PolicyValidationRegistry

def create_dataset(db,user,name,version,cutoff=None):
 row=ControlledActivationEvaluationDataset(name=name,version=version,status="draft",created_by_user_id=user.id,evidence_cutoff=cutoff);db.add(row);db.commit();db.refresh(row);return row
def add_item(db,dataset_id,proposal_id):
 d=db.get(ControlledActivationEvaluationDataset,dataset_id);p=db.get(ControlledActionProposal,proposal_id)
 if not d or not p:raise ValueError("dataset_or_proposal_missing")
 if d.status!="draft":raise ValueError("frozen_dataset")
 if d.evidence_cutoff and p.created_at>d.evidence_cutoff:raise ValueError("outside_evidence_cutoff")
 r=db.scalar(select(PolicyValidationRegistry).where(PolicyValidationRegistry.policy_version==p.policy_version,PolicyValidationRegistry.rules_version==p.rules_version))
 row=ControlledActivationEvaluationDatasetItem(dataset_id=d.id,proposal_id=p.id,policy_decision_id=p.policy_decision_id,patient_profile_id=p.patient_profile_id,training_session_id=p.target_training_session_id,action_type=p.action_type,policy_version=p.policy_version,rules_version=p.rules_version,profile_snapshot_id=p.profile_snapshot_id,validation_registry_status=r.validation_status if r else None,proposal_created_at=p.created_at);db.add(row);db.commit();return row
def remove_item(db,dataset_id,item_id):
 d=db.get(ControlledActivationEvaluationDataset,dataset_id);row=db.get(ControlledActivationEvaluationDatasetItem,item_id)
 if not d or not row or row.dataset_id!=d.id:raise ValueError("item_missing")
 if d.status!="draft":raise ValueError("frozen_dataset")
 db.delete(row);db.commit()
def freeze(db,dataset_id):
 d=db.get(ControlledActivationEvaluationDataset,dataset_id)
 if not d or d.status!="draft":raise ValueError("only_draft_can_freeze")
 d.status="frozen";db.commit();return d
def archive(db,dataset_id):
 d=db.get(ControlledActivationEvaluationDataset,dataset_id)
 if not d or d.status!="frozen":raise ValueError("only_frozen_can_archive")
 d.status="archived";db.commit();return d
def _rate(n,d):return n/d if d else None
def _count(xs):
 out={}
 for x in xs:out[x]=out.get(x,0)+1
 return out
def _report(db,items,action):
 ps=[db.get(ControlledActionProposal,i.proposal_id) for i in items if i.action_type==action];ps=[x for x in ps if x]
 approvals={x.proposal_id:x for x in db.scalars(select(ControlledActionApproval).where(ControlledActionApproval.proposal_id.in_([p.id for p in ps]))) } if ps else {}
 executions={x.proposal_id:x for x in db.scalars(select(ControlledActionExecution).where(ControlledActionExecution.proposal_id.in_([p.id for p in ps]))) } if ps else {}
 obs={x.execution_id:x for x in db.scalars(select(ControlledActionObservation).where(ControlledActionObservation.execution_id.in_([x.id for x in executions.values()]))) } if executions else {}
 events=list(db.scalars(select(ControlledActionSafetyEvent).where(ControlledActionSafetyEvent.proposal_id.in_([p.id for p in ps]))) if ps else [])
 n=len(ps); approved=sum(p.id in approvals for p in ps); rejected=sum(p.status=="rejected" for p in ps);expired=sum(p.status=="expired" for p in ps);pending=sum(p.status=="pending_review" for p in ps);executed=list(executions.values());applied=sum(x.status=="applied" for x in executed);no_op=sum(x.status=="no_op" for x in executed);rolled=sum(x.rolled_back_at is not None for x in executed);completed=sum(o.outcome=="session_completed" for o in obs.values());conflicts=sum(e.code=="state_conflict" for e in events)
 return {"dataset":{"proposal_count":n,"patient_count":len({p.patient_profile_id for p in ps}),"therapist_count":len({a.therapist_user_id for a in approvals.values()})},"review":{"approved":approved,"rejected":rejected,"expired":expired,"pending":pending,"approval_rate":_rate(approved,n),"rejection_rate":_rate(rejected,n),"expiry_rate":_rate(expired,n),"override":{"no_override":approved,"minor_override":0,"material_override":0,"rate":0}},"execution":{"apply_attempted":len(executed),"applied":applied,"no_op":no_op,"application_rate":_rate(applied,approved),"apply_failure_rate":0},"conflict":{"state_conflict_count":conflicts,"state_conflict_rate":_rate(conflicts,n)},"rollback":{"count":rolled,"rate":_rate(rolled,len(executed)),"reason_distribution":_count(x.rollback_reason_code or "unavailable" for x in executed if x.rolled_back_at)},"safety":{"blocked_before_write":len(events),"blocked_reason_distribution":_count(x.code for x in events),"critical_events":0},"session_observation":{"completed":completed,"abandoned":sum(o.outcome=="session_abandoned" for o in obs.values()),"unavailable":len(executed)-len(obs),"completion_coverage":_rate(len(obs),len(executed))},"action_specific":{"action_type":action,"difficulty_direction":_count(str(p.proposed_value.get("requested_difficulty_delta")) for p in ps) if action=="difficulty_step_adjustment" else {}},"privacy":"aggregate only; free-text comments excluded; descriptive operational evidence only"}
def _decision(report):
 p=POLICY;r=[];d=report["dataset"];rev=report["review"];ex=report["execution"];co=report["conflict"];rb=report["rollback"];sa=report["safety"];ob=report["session_observation"]
 if d["proposal_count"]<p["minimum_proposals"]:r.append("insufficient_proposals")
 if rev["approved"]<p["minimum_approved"]:r.append("insufficient_approved_actions")
 if ex["applied"]<p["minimum_applied"]:r.append("insufficient_executions")
 if d["patient_count"]<p["minimum_unique_patients"]:r.append("insufficient_unique_patients")
 if d["therapist_count"]<p["minimum_unique_therapists"]:r.append("insufficient_reviewer_coverage")
 if ob["completion_coverage"] is None or ob["completion_coverage"]<p["minimum_session_completion_coverage"]:r.append("low_completion_coverage")
 if r:return "insufficient_evidence",r,[]
 warnings=[]
 for value,key in ((rb["rate"],"high_rollback_rate"),(co["state_conflict_rate"],"high_state_conflict_rate"),(sa["blocked_before_write"]/d["proposal_count"] if d["proposal_count"] else 0,"high_safety_block_rate")):
  if value is not None and value>.5:warnings.append(key)
 return ("manual_only" if warnings else "eligible_for_streamlined_evaluation"),warnings,warnings
def run(db,dataset_id,actor=None,action_type=None):
 d=db.get(ControlledActivationEvaluationDataset,dataset_id)
 if not d or d.status!="frozen":raise ValueError("dataset_must_be_frozen")
 items=list(db.scalars(select(ControlledActivationEvaluationDatasetItem).where(ControlledActivationEvaluationDatasetItem.dataset_id==d.id)))
 actions=[action_type] if action_type else sorted({x.action_type for x in items})
 rows=[]
 for action in actions:
  subset=[x for x in items if x.action_type==action]
  if not subset:continue
  pv,rv,av=subset[0].policy_version,subset[0].rules_version,db.get(ControlledActionProposal,subset[0].proposal_id).activation_policy_version
  fp=hashlib.sha256(json.dumps({"dataset":str(d.id),"action":action,"items":[str(x.id) for x in subset],"policy":GOVERNANCE_POLICY_VERSION},sort_keys=True).encode()).hexdigest();existing=db.scalar(select(ControlledActivationEvaluationRun).where(ControlledActivationEvaluationRun.dataset_id==d.id,ControlledActivationEvaluationRun.input_fingerprint==fp))
  if existing:rows.append(existing);continue
  report=_report(db,subset,action);status,reasons,warnings=_decision(report);report["governance"]={"status":status,"reason_codes":reasons,"warnings":warnings,"contract":{"policy_version":pv,"rules_version":rv,"action_type":action,"governance_status":status,"governance_policy_version":GOVERNANCE_POLICY_VERSION}}
  row=ControlledActivationEvaluationRun(dataset_id=d.id,governance_schema_version=SCHEMA_VERSION,evaluation_policy_version=EVALUATION_POLICY_VERSION,governance_policy_version=GOVERNANCE_POLICY_VERSION,policy_version=pv,rules_version=rv,activation_policy_version=av,adapter_version=ADAPTER_VERSION,action_type=action,input_fingerprint=fp,report=report,governance_status=status,reason_codes=reasons,warnings=warnings,generated_by_user_id=getattr(actor,"id",None));db.add(row);db.flush();reg=db.scalar(select(ControlledActionGovernanceRegistry).where(ControlledActionGovernanceRegistry.policy_version==pv,ControlledActionGovernanceRegistry.rules_version==rv,ControlledActionGovernanceRegistry.action_type==action));old=reg.governance_status if reg else None
  if not reg:reg=ControlledActionGovernanceRegistry(policy_version=pv,rules_version=rv,action_type=action,governance_status=status,latest_evaluation_run_id=row.id,reason_codes=reasons);db.add(reg);db.flush()
  else:reg.governance_status=status;reg.latest_evaluation_run_id=row.id;reg.reason_codes=reasons
  db.add(ControlledActionGovernanceTransition(registry_id=reg.id,from_status=old,to_status=status,evaluation_run_id=row.id,reason_codes=reasons,actor_user_id=getattr(actor,"id",None)));db.commit();db.refresh(row);rows.append(row)
 return rows
def registry(db,pv=None,rv=None,action=None):
 q=select(ControlledActionGovernanceRegistry)
 if pv:q=q.where(ControlledActionGovernanceRegistry.policy_version==pv)
 if rv:q=q.where(ControlledActionGovernanceRegistry.rules_version==rv)
 if action:q=q.where(ControlledActionGovernanceRegistry.action_type==action)
 return list(db.scalars(q))
def registry_history(db,registry_id):
 return list(db.scalars(select(ControlledActionGovernanceTransition).where(ControlledActionGovernanceTransition.registry_id==registry_id).order_by(ControlledActionGovernanceTransition.created_at.asc())))
