"""Versioned, engineering mapping only; it does not assert clinical thresholds."""
PROFILE_SCHEMA_VERSION = "profile-v2.0"
PROFILE_MAPPING_VERSION = "profile-mapping-v1"
PROFILE_EVIDENCE_POLICY_VERSION = "profile-evidence-policy-v1"
PROFILE_EVIDENCE_POLICY = {"current_window_size": 3, "minimum_supported_observations": 2, "version": PROFILE_EVIDENCE_POLICY_VERSION}

# domain, source code (exact or prefix.*), target, direction, eligibility source kind
MAPPINGS = (
    ("repeat", "content_reproduction", "repeat.content_reproduction", "high", "automatic"),
    ("repeat", "fluency_efficiency", "repeat.fluency_efficiency", "unknown", "automatic"),
    ("repeat", "disfluency_events", "repeat.disfluency_events", "low", "automatic"),
    ("repeat", "voice_state", "repeat.voice_state", "unknown", "automatic"),
    ("repeat", "independence", "repeat.independence", "high", "automatic"),
    ("repeat", "articulation_evidence", "repeat.articulation_evidence", "unknown", "automatic"),
    ("functional_communication", "goal_achievement", "functional.goal_achievement", "high", "automatic"),
    ("functional_communication", "information_sufficiency", "functional.information_sufficiency", "high", "automatic"),
    ("functional_communication", "response_ability", "functional.response_ability", "high", "automatic"),
    ("functional_communication", "relevance_and_organization", "functional.relevance_and_organization", "high", "automatic"),
    ("functional_communication", "independence", "functional.independence", "high", "automatic"),
    ("functional_communication", "repair_ability", "functional.repair_ability", "high", "automatic"),
    ("clinical_stage", "manual_intelligibility.*", "clinical.manual_intelligibility", "unknown", "clinical_manual"),
    ("clinical_stage", "acceptability", "clinical.acceptability", "unknown", "clinical_manual"),
    ("clinical_stage", "instrument.total", "clinical.instrument.total", "unknown", "clinical_manual"),
    ("clinical_stage", "instrument.subscale.*", "clinical.instrument.subscale", "unknown", "clinical_manual"),
    ("clinical_stage", "legacy_metric.*", "clinical.legacy_metric", "unknown", "clinical_manual"),
)

def mapping_for(domain: str, code: str):
    for mapped_domain, source, target, direction, source_kind in MAPPINGS:
        if domain == mapped_domain and (source == code or source.endswith(".*") and code.startswith(source[:-1])):
            return {"source_dimension_code": source, "profile_dimension_code": target, "direction": direction,
                    "source_kind": source_kind, "mapping_version": PROFILE_MAPPING_VERSION,
                    "patient_eligible": source_kind == "automatic", "therapist_eligible": True,
                    "aggregation_eligible": True}
    return None
