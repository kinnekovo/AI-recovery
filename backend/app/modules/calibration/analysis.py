"""Pure, offline-friendly calibration calculations. Thresholds are engineering policy, never clinical standards."""
import math, random
from collections import defaultdict
PROMOTION_POLICY={"version":"promotion-policy-v1","minimum_total_n":20,"minimum_holdout_n":5,"minimum_subgroup_n":5,"minimum_annotation_pair_n":5,"maximum_mae":10.0,"maximum_abs_bias":5.0,"minimum_correlation":0.7,"maximum_subgroup_mae_gap":5.0}
def _rank(v):
 s=sorted((x,i) for i,x in enumerate(v)); out=[0.0]*len(v); p=0
 while p<len(s):
  q=p
  while q<len(s) and s[q][0]==s[p][0]:q+=1
  r=(p+q-1)/2+1
  for _,i in s[p:q]:out[i]=r
  p=q
 return out
def pearson(a,b):
 if len(a)<2:return None
 ma=sum(a)/len(a); mb=sum(b)/len(b); da=sum((x-ma)**2 for x in a); db=sum((x-mb)**2 for x in b)
 return None if not da or not db else sum((x-ma)*(y-mb) for x,y in zip(a,b))/math.sqrt(da*db)
def icc_3_1(pairs):
 """Two-rater consistency ICC(3,1); requires >=2 targets and finite numeric pairs."""
 n=len(pairs)
 if n<2:return None
 rows=[(float(a),float(b)) for a,b in pairs]; gm=sum(a+b for a,b in rows)/(2*n); means=[(a+b)/2 for a,b in rows]
 msr=2*sum((x-gm)**2 for x in means)/(n-1)
 mse=sum((v-means[i])**2 for i,row in enumerate(rows) for v in row)/(n*(2-1))
 return None if msr+mse==0 else (msr-mse)/(msr+mse)
def continuous(auto,ref):
 n=len(auto)
 if not n:return {"n":0,"mae":None,"rmse":None,"bias":None,"pearson":None,"spearman":None}
 e=[a-r for a,r in zip(auto,ref)]
 return {"n":n,"mae":sum(abs(x) for x in e)/n,"rmse":math.sqrt(sum(x*x for x in e)/n),"bias":sum(e)/n,"pearson":pearson(auto,ref),"spearman":pearson(_rank(auto),_rank(ref))}
def classification(auto,ref):
 n=len(auto)
 if not n:return {"n":0,"accuracy":None,"macro_f1":None}
 labels=sorted(set(auto)|set(ref)); f=[]
 for label in labels:
  tp=sum(a==label and r==label for a,r in zip(auto,ref)); fp=sum(a==label and r!=label for a,r in zip(auto,ref)); fn=sum(a!=label and r==label for a,r in zip(auto,ref));
  f.append(0 if not (2*tp+fp+fn) else 2*tp/(2*tp+fp+fn))
 return {"n":n,"accuracy":sum(a==r for a,r in zip(auto,ref))/n,"macro_f1":sum(f)/len(f)}
def weighted_kappa(auto,ref):
 if len(auto)<2:return None
 labels=sorted(set(auto)|set(ref)); n=len(labels)
 if n<2:return 1.0
 obs=sum(((labels.index(a)-labels.index(r))/(n-1))**2 for a,r in zip(auto,ref))/len(auto)
 pa=[auto.count(x)/len(auto) for x in labels];pr=[ref.count(x)/len(ref) for x in labels]
 exp=sum(pa[i]*pr[j]*((i-j)/(n-1))**2 for i in range(n) for j in range(n))
 return None if exp==0 else 1-obs/exp
def stability(pairs,comparability):
 eligible=[p for p,c in zip(pairs,comparability) if c.get("status") in {"comparable","partially_comparable"}]
 if not eligible:return {"n":0,"status":"no_comparable_pairs","mean_absolute_difference":None}
 return {"n":len(eligible),"status":"ok","mean_absolute_difference":sum(abs(a-b) for a,b in eligible)/len(eligible),"mean_difference":sum(a-b for a,b in eligible)/len(eligible),"pearson":pearson([a for a,b in eligible],[b for a,b in eligible])}
def assessment_stability(pairs):
 """Pairs of (assessment_a, assessment_b, automatic_a, automatic_b); gates via V3.3 comparability."""
 from app.modules.assessment.comparability import compare
 values=[]; decisions=[]
 for a,b,x,y in pairs:
  result=compare(a,b);decisions.append(result)
  if result["status"] in {"comparable","partially_comparable"}: values.append((x,y))
 out=stability(values,[{"status":"comparable"} for _ in values]);out["comparability"]={"eligible_pairs":len(values),"all_pair_results":decisions};return out
def patient_split(samples,seed=17,holdout_ratio=.2):
 patients=sorted({str(s["patient_profile_id"]) for s in samples}); r=random.Random(seed);r.shuffle(patients); cut=max(1,round(len(patients)*(1-holdout_ratio))) if patients else 0; dev=set(patients[:cut]);return {"method":"patient_level_random_v1","seed":seed,"holdout_ratio":holdout_ratio,"development_patients":sorted(dev),"holdout_patients":sorted(set(patients)-dev)}
def reference(annotations):
 vals=[a["value"] for a in annotations if a.get("value") is not None]
 if not vals:return None,"missing_reference_data"
 adjud=[a for a in annotations if a.get("adjudicated") or a.get("is_adjudicated")]
 if adjud:return adjud[-1]["value"],"adjudicated"
 return sum(vals)/len(vals),"dual_mean" if len(vals)>=2 else "single_annotation"
def reliability(pairs):
 if len(pairs)<2:return {"n":len(pairs),"reference_unstable":True,"pearson":None,"icc_3_1":None,"mean_abs_difference":None}
 a,b=zip(*pairs);return {"n":len(pairs),"reference_unstable":False,"pearson":pearson(a,b),"icc_3_1":icc_3_1(pairs),"mean_abs_difference":sum(abs(x-y) for x,y in pairs)/len(pairs)}
def subgroup(rows,key,minimum_n):
 groups=defaultdict(list)
 for r in rows: groups[(r.get("metadata") or {}).get(key,"missing")].append(r)
 out={}
 for name,x in groups.items():out[str(name)]={"n":len(x),"status":"ok" if len(x)>=minimum_n else "insufficient_sample",**(continuous([r["automatic"] for r in x],[r["reference"] for r in x]) if len(x)>=minimum_n else {})}
 return out
def decision(metrics,holdout,reliability_metrics,subgroups,policy=PROMOTION_POLICY,drift=False):
 reasons=[]
 if drift: reasons.append("provider_version_changed")
 if metrics["n"]<policy["minimum_total_n"]:reasons.append("insufficient_total_samples")
 if holdout["n"]<policy["minimum_holdout_n"]:reasons.append("insufficient_holdout_samples")
 if metrics.get("mae") is not None and metrics["mae"]>policy["maximum_mae"]:reasons.append("mae_above_threshold")
 if metrics.get("bias") is not None and abs(metrics["bias"])>policy["maximum_abs_bias"]:reasons.append("bias_above_threshold")
 if metrics.get("pearson") is not None and metrics["pearson"]<policy["minimum_correlation"]:reasons.append("agreement_below_threshold")
 if reliability_metrics.get("reference_unstable"):reasons.append("reference_unstable")
 maes=[v.get("mae") for v in (subgroups or {}).values() if v.get("status")=="ok" and v.get("mae") is not None]
 if len(maes)>=2 and max(maes)-min(maes)>policy["maximum_subgroup_mae_gap"]:reasons.append("subgroup_disparity")
 if any(v.get("status")=="insufficient_sample" for v in (subgroups or {}).values()):reasons.append("insufficient_subgroup_samples")
 return ("eligible" if not reasons else ("insufficient_evidence" if any(x.startswith("insufficient") for x in reasons) else "review_required")),reasons
