"""Manual stage-assessment canonical records; no scale scoring or interpretation."""
import hashlib, json
from sqlalchemy import select
from sqlalchemy.orm import Session
from fastapi import HTTPException
from app.modules.assessment.model import AssessmentSession, AssessmentReviewStatus
from app.modules.evaluation_runs.model import EvaluationRun
from app.modules.evaluation_runs.schema import EvaluationRunCreate, EvaluationDimensionResultCreate, InputProvenanceSnapshot, QualityGateSnapshot
from app.modules.evaluation_runs.service import create_candidate_run, adopt_candidate_run, resolve_evaluation_write_failure, get_run_for_professional

ALGORITHM_VERSION="clinical-stage-v2.0"

def _fp(value): return hashlib.sha256(json.dumps(value,sort_keys=True,default=str,separators=(",",":")).encode()).hexdigest()
def _num(value): return float(value) if isinstance(value,(int,float)) else None

def build_payload(a: AssessmentSession):
    has_result=bool(a.total_result or a.subscale_results or a.metrics)
    review_value = getattr(a.review_status, "value", a.review_status)
    formal_ready=bool(a.instrument_name and a.instrument_version and a.score_unit and review_value in {AssessmentReviewStatus.confirmed.value, AssessmentReviewStatus.adjusted.value} and has_result)
    reasons=[]
    if not has_result: reasons.append("no_valid_result")
    if not a.instrument_name or not a.instrument_version: reasons.append("instrument_identity_incomplete")
    if not a.score_unit: reasons.append("score_unit_unknown")
    if a.protocol_deviation_reasons: reasons.append("protocol_deviation_requires_confirmation")
    if not has_result: result="unscorable"
    elif not a.instrument_name or not a.instrument_version or not a.score_unit or a.protocol_deviation_reasons: result="review_required"
    elif not formal_ready: result="provisional"
    else: result="formal"
    dims=[]
    def add(code, value, source):
      dims.append(EvaluationDimensionResultCreate(dimension_code=code,value=_num(value),unit=a.score_unit,status="measured" if _num(value) is not None else "unavailable",measurement_quality={"manual":True},evidence_snapshot={"instrument_name":a.instrument_name,"instrument_version":a.instrument_version,"source_field":source},limitations=[] if _num(value) is not None else ["value_not_supplied"]))
    if a.total_result: add("instrument.total",a.total_result.get("value"),"total_result")
    for code,v in (a.subscale_results or {}).items(): add("instrument.subscale."+str(code),v.get("value") if isinstance(v,dict) else v,"subscale_results."+str(code))
    for code,v in (a.metrics or {}).items():
      if code in {"wab_comprehensibility","wab_repetition_comprehensibility"}: add("manual_intelligibility."+code,v,"metrics."+code)
      elif code=="acceptance_score": add("acceptability",v,"metrics.acceptance_score")
      else: add("legacy_metric."+code,v,"metrics."+code)
    prov={"source_snapshot":{"assessment_session_id":str(a.id),"instrument_name":a.instrument_name,"instrument_version":a.instrument_version,"language_locale":a.language_locale,"localization_version":a.localization_version,"assessment_stage":a.assessment_stage,"assessed_at":str(a.assessed_at),"raw_item_results":a.raw_item_results,"missing_items":a.missing_items,"protocol_deviations":a.protocol_deviations,"review_status":a.review_status},"providers":{"administrator_user_id":str(a.administered_by_user_id) if a.administered_by_user_id else None,"administrator_role":a.administrator_role},"contract_version":"manual-assessment-input-v1"}
    fp=_fp({"algorithm":ALGORITHM_VERSION,"provenance":prov,"subscales":a.subscale_results,"total":a.total_result,"metrics":a.metrics})
    return EvaluationRunCreate(patient_profile_id=a.patient_profile_id,domain="clinical_stage",source_type="assessment_session",source_id=a.id,algorithm_version=ALGORITHM_VERSION,input_fingerprint=fp,config_snapshot={"missing_item_policy":"recorded_not_zero","comparability_rule_version":"clinical-stage-comparability-v1","score_unit":a.score_unit,"calibration_level":"manual_record_only_no_clinical_interpretation"},input_provenance=InputProvenanceSnapshot(**prov),quality_gate=QualityGateSnapshot(eligible=formal_ready,reasons=reasons,algorithm_version=ALGORITHM_VERSION,measurement_quality="manual_record"),result_status=result,profile_eligibility=formal_ready,profile_ineligibility_reasons=[] if formal_ready else reasons,limitations=["recording_and_comparison_only; no automatic clinical interpretation"],dimensions=dims)

def write_clinical_stage_run(db:Session, assessment_id):
 a=db.get(AssessmentSession,assessment_id)
 if not a: raise HTTPException(404,"阶段评估不存在")
 p=build_payload(a); old=db.scalar(select(EvaluationRun).where(EvaluationRun.source_type=="assessment_session",EvaluationRun.source_id==a.id,EvaluationRun.domain=="clinical_stage",EvaluationRun.algorithm_version==ALGORITHM_VERSION,EvaluationRun.input_fingerprint==p.input_fingerprint))
 run=old if old and old.adoption_status=="adopted" else adopt_candidate_run(db,(old or create_candidate_run(db,p)).id)
 resolve_evaluation_write_failure(db,source_type="assessment_session",source_id=a.id,domain="clinical_stage",algorithm_version=ALGORITHM_VERSION,run=run); return run
