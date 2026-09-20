import hashlib,json
POLICY_VALIDATION_VERSION="policy-validation-v1"; VALIDATION_POLICY_VERSION="policy-validation-policy-v1"
VALIDATION_POLICY={"minimum_total_decisions":20,"minimum_unique_patients":5,"minimum_reviewed_decisions":10,"minimum_observed_decisions":10,"minimum_subgroup_n":5,"version":VALIDATION_POLICY_VERSION,"source":"engineering validation policy","maturity":"E1"}
VALIDATION_STATUSES={"insufficient_evidence","shadow","validated","eligible_for_controlled_activation","suspended","review_required"}
def fingerprint(x):return hashlib.sha256(json.dumps(x,sort_keys=True,default=str).encode()).hexdigest()
def feedback_stats(feedback, total):
 c={k:0 for k in ("agree","partially_agree","disagree","not_applicable")}
 for x in feedback:c[x.agreement]+=1
 n=sum(c.values());return {**c,"reviewed":n,"unreviewed":max(0,total-n),"review_coverage":n/total if total else 0,"agree_rate":c["agree"]/n if n else None,"partial_agree_rate":c["partially_agree"]/n if n else None,"disagree_rate":c["disagree"]/n if n else None}
def safety(payload,mode):
 forbidden=("diagnosis","prescription","treatment effective","patient recovered","automatic activation")
 text=json.dumps(payload,ensure_ascii=False).lower(); reasons=[]
 if mode!="shadow":reasons.append("NON_SHADOW_MODE")
 if any(x in text for x in forbidden):reasons.append("FORBIDDEN_PAYLOAD_CONCEPT")
 return {"status":"passed" if not reasons else "failed","reason_codes":reasons}
def promotion(stats,safety_status):
 r=[];p=VALIDATION_POLICY
 if stats["total"]<p["minimum_total_decisions"]:r.append("INSUFFICIENT_TOTAL_DECISIONS")
 if stats["patients"]<p["minimum_unique_patients"]:r.append("INSUFFICIENT_UNIQUE_PATIENTS")
 if stats["feedback"]["reviewed"]<p["minimum_reviewed_decisions"]:r.append("INSUFFICIENT_REVIEW_COVERAGE")
 if stats["observed"]<p["minimum_observed_decisions"]:r.append("INSUFFICIENT_OBSERVATION_COVERAGE")
 if safety_status!="passed":r.append("SAFETY_VIOLATION")
 return {"status":"eligible_for_controlled_activation" if not r else "insufficient_evidence","reason_codes":r}
def patient_split(patient_ids,seed="policy-validation-v1",ratio=.8):
 ids=sorted(set(map(str,patient_ids)));dev=[];hold=[]
 for pid in ids:(dev if int(hashlib.sha256((seed+pid).encode()).hexdigest(),16)%10000 < int(ratio*10000) else hold).append(pid)
 return {"method":"patient_hash","seed":seed,"ratio":ratio,"development":dev,"holdout":hold}
def stability_pairs(decisions):
 rows=sorted(decisions,key=lambda x:(str(x.patient_profile_id),x.generated_at));out=[]
 for a,b in zip(rows,rows[1:]):
  if a.patient_profile_id!=b.patient_profile_id or a.policy_version!=b.policy_version or a.rules_version!=b.rules_version:continue
  ad=a.decision_payload.get("difficulty",{}).get("recommended_difficulty_action");bd=b.decision_payload.get("difficulty",{}).get("recommended_difficulty_action")
  changed=ad!=bd; same_input=a.profile_snapshot_id==b.profile_snapshot_id
  out.append({"first":str(a.id),"second":str(b.id),"decision_flip":changed,"explained_by_input_change":changed and not same_input,"unexpected_decision_instability":changed and same_input})
 return out
def subgroup_behavior(rows,key="locale"):
 groups={}
 for r in rows:groups.setdefault((r.decision_payload.get("subgroup") or {}).get(key,"missing"),[]).append(r)
 return {g:{"n":len(v),"status":"insufficient_sample" if len(v)<VALIDATION_POLICY["minimum_subgroup_n"] else "reported","difficulty":{x.decision_payload.get("difficulty",{}).get("recommended_difficulty_action"):sum(y.decision_payload.get("difficulty",{}).get("recommended_difficulty_action")==x.decision_payload.get("difficulty",{}).get("recommended_difficulty_action") for y in v) for x in v}} for g,v in groups.items()}
