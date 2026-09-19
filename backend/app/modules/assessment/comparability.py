"""Fact-only longitudinal comparability; never infers clinical significance."""
from app.modules.assessment.model import AssessmentSession
def compare(a: AssessmentSession,b: AssessmentSession)->dict:
 r=[]
 for field,code in [("instrument_name","scale_mismatch"),("instrument_version","scale_version_mismatch"),("language_locale","locale_mismatch"),("localization_version","localization_version_mismatch"),("score_unit","unit_mismatch")]:
  if not getattr(a,field) or not getattr(b,field): r.append("legacy_insufficient_metadata")
  elif getattr(a,field)!=getattr(b,field): r.append(code)
 if a.protocol_deviation_reasons or b.protocol_deviation_reasons:r.append("protocol_deviation")
 if a.missing_items or b.missing_items:r.append("missing_required_items")
 if a.administration_mode!=b.administration_mode:r.append("administration_condition_changed")
 dims=[]
 for k,v in (a.subscale_results or {}).items():
  other=(b.subscale_results or {}).get(k); av=v.get("value") if isinstance(v,dict) else v; bv=other.get("value") if isinstance(other,dict) else other
  if isinstance(av,(int,float)) and isinstance(bv,(int,float)): dims.append({"dimension_code":"instrument.subscale."+str(k),"baseline":av,"current":bv,"change":round(bv-av,2)})
 if not dims: r.append("dimension_mismatch")
 status="comparable" if not r else ("partially_comparable" if dims else "not_comparable")
 return {"status":status,"reason_codes":sorted(set(r)),"compared_dimensions":dims,"excluded_dimensions":[],"fact":"values are recorded differences only; no clinical interpretation"}
