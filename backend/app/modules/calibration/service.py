from sqlalchemy import select
from fastapi import HTTPException
from app.database.base import utc_now
from app.modules.calibration.model import *
from app.modules.calibration.analysis import *
from app.modules.evaluation_runs.model import EvaluationRun,EvaluationDimensionResult
def create_dataset(db,user,p):
 x=CalibrationDataset(name=p.name,version=p.version,description=p.description,created_by_user_id=user.id);db.add(x);db.commit();return x
def add_sample(db,user,dataset_id,p):
 d=db.get(CalibrationDataset,dataset_id)
 if not d or d.status!="draft":raise HTTPException(409,"数据集不存在或已冻结")
 run=db.get(EvaluationRun,p.evaluation_run_id); dim=db.scalar(select(EvaluationDimensionResult).where(EvaluationDimensionResult.evaluation_run_id==p.evaluation_run_id,EvaluationDimensionResult.dimension_code==p.dimension_code))
 if not run or not dim:raise HTTPException(404,"canonical 样本不存在")
 x=CalibrationSample(dataset_id=d.id,patient_profile_id=run.patient_profile_id,evaluation_run_id=run.id,dimension_code=p.dimension_code,automatic_value=dim.value,automatic_status=dim.status,unit=dim.unit,task_type=run.domain,source_type=run.source_type,recorded_at=run.created_at,metadata_snapshot={"provenance":run.input_provenance,"algorithm_version":run.algorithm_version});db.add(x);db.commit();return x
def freeze(db,user,dataset_id):
 d=db.get(CalibrationDataset,dataset_id)
 if not d or d.status!="draft":raise HTTPException(409,"数据集不可冻结")
 d.status="frozen";d.frozen_at=utc_now();db.commit();return d
def dataset_read(db,dataset_id):
 d=db.get(CalibrationDataset,dataset_id)
 if not d:raise HTTPException(404,"校准数据集不存在")
 samples=list(db.scalars(select(CalibrationSample).where(CalibrationSample.dataset_id==d.id)))
 return {"id":str(d.id),"name":d.name,"version":d.version,"status":d.status,"frozen_at":d.frozen_at,"sample_count":len(samples),"sample_ids":[str(x.id) for x in samples]}
def remove_sample(db,user,dataset_id,sample_id):
 d=db.get(CalibrationDataset,dataset_id); s=db.get(CalibrationSample,sample_id)
 if not d or not s or s.dataset_id!=d.id or d.status!="draft":raise HTTPException(409,"仅 draft 数据集可删除样本")
 db.delete(s);db.commit()
def annotate(db,user,p):
 s=db.get(CalibrationSample,p.sample_id)
 if not s or s.dimension_code!=p.dimension_code:raise HTTPException(404,"标注样本不存在")
 # Unique round preserves independent annotations; callers cannot read peers from this mutation response.
 x=ReferenceAnnotation(sample_id=s.id,annotator_user_id=user.id,annotation_round=p.annotation_round,dimension_code=p.dimension_code,value=p.value,unit=p.unit,comment=p.comment);db.add(x);db.commit();return x
def adjudicate(db,user,p):
 x=annotate(db,user,p);x.is_adjudicated=True;db.commit();return x
def revise_annotation(db,user,annotation_id,p):
 old=db.get(ReferenceAnnotation,annotation_id)
 if not old or old.annotator_user_id!=user.id:raise HTTPException(404,"标注不存在")
 sample=db.get(CalibrationSample,old.sample_id); dataset=db.get(CalibrationDataset,sample.dataset_id) if sample else None
 if not sample or not dataset or dataset.status=="archived":raise HTTPException(409,"标注不可修订")
 x=ReferenceAnnotation(sample_id=old.sample_id,annotator_user_id=user.id,annotation_round=old.annotation_round+1,dimension_code=old.dimension_code,value=p.value,unit=p.unit or old.unit,comment=p.comment,supersedes_annotation_id=old.id);db.add(x);db.commit();return x
def register(db,user,p):
 x=MetricRegistry(metric_code=p.metric_code,display_name=p.display_name,source=p.source,version=p.version,dimension_type=p.dimension_type,unit=p.unit,status="experimental");db.add(x);db.commit();return x
def metric_read(db,metric_code):
 m=db.scalar(select(MetricRegistry).where(MetricRegistry.metric_code==metric_code))
 if not m:raise HTTPException(404,"metric 不存在")
 runs=list(db.scalars(select(CalibrationRun).where(CalibrationRun.metric_registry_id==m.id).order_by(CalibrationRun.created_at.desc())))
 return {"metric_code":m.metric_code,"status":m.status,"version":m.version,"last_calibrated_at":m.last_calibrated_at,"calibration_runs":[{"id":str(x.id),"decision":x.promotion_decision,"reasons":x.reason_codes} for x in runs]}
def run_report(db,run_id):
 x=db.get(CalibrationRun,run_id)
 if not x:raise HTTPException(404,"calibration run 不存在")
 d=db.get(CalibrationDataset,x.dataset_id);m=db.get(MetricRegistry,x.metric_registry_id)
 metrics=x.metrics_snapshot or {}
 return {"run_id":str(x.id),"dataset":{"id":str(d.id),"name":d.name,"version":d.version},"metric":{"code":m.metric_code,"version":m.version,"status":m.status},"split":x.split_snapshot,"policy":x.policy_snapshot,"development":metrics.get("development",{}),"holdout":metrics.get("holdout",{}),"subgroups":metrics.get("subgroups",{}),"human_reference_quality":metrics.get("reliability",{}),"promotion":{"decision":x.promotion_decision,"reason_codes":x.reason_codes},"limitations":["Engineering calibration evidence only; not a clinical-validity or efficacy conclusion."]}
def run(db,user,p):
 d=db.get(CalibrationDataset,p.dataset_id);m=db.scalar(select(MetricRegistry).where(MetricRegistry.metric_code==p.metric_code))
 if not d or d.status!="frozen" or not m:raise HTTPException(409,"需使用冻结数据集和已注册 metric")
 samples=list(db.scalars(select(CalibrationSample).where(CalibrationSample.dataset_id==d.id,CalibrationSample.dimension_code==m.metric_code)))
 split=patient_split([{"patient_profile_id":s.patient_profile_id} for s in samples],p.seed,p.holdout_ratio); rows=[]
 pairs=[]
 for s in samples:
  anns=[{"value":a.value,"is_adjudicated":a.is_adjudicated} for a in db.scalars(select(ReferenceAnnotation).where(ReferenceAnnotation.sample_id==s.id,ReferenceAnnotation.dimension_code==s.dimension_code))]
  ref,_=reference(anns)
  raw=[a["value"] for a in anns if a["value"] is not None]
  if len(raw)>=2:pairs.append((raw[0],raw[1]))
  if s.automatic_value is not None and ref is not None:rows.append({"patient":str(s.patient_profile_id),"automatic":s.automatic_value,"reference":ref,"metadata":s.metadata_snapshot})
 dev=[r for r in rows if r["patient"] in split["development_patients"]];hold=[r for r in rows if r["patient"] in split["holdout_patients"]]
 met=continuous([r["automatic"] for r in dev],[r["reference"] for r in dev]);hm=continuous([r["automatic"] for r in hold],[r["reference"] for r in hold]);rel=reliability(pairs)
 versions={str((s.metadata_snapshot or {}).get("provenance",{}).get("providers",{})) for s in samples}
 drift=len(versions)>1
 groups=subgroup(rows,"locale",PROMOTION_POLICY["minimum_subgroup_n"])
 dec,reasons=decision(met,hm,rel,groups,PROMOTION_POLICY,drift)
 x=CalibrationRun(dataset_id=d.id,metric_registry_id=m.id,created_by_user_id=user.id,split_snapshot=split,policy_snapshot=PROMOTION_POLICY,metrics_snapshot={"development":met,"holdout":hm,"subgroups":groups,"reliability":rel},promotion_decision=dec,reason_codes=reasons);db.add(x)
 # A promotion is an internal engineering evidence state, never a clinical claim.
 if "provider_version_changed" in reasons: m.status="provisional" if m.status=="promoted" else "shadow"
 elif dec=="eligible": m.status="promoted"
 elif m.status=="experimental": m.status="shadow"
 m.last_calibrated_at=utc_now();db.commit();return x
