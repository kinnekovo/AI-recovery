import unittest
from types import SimpleNamespace
from uuid import uuid4

from fastapi import HTTPException
from unittest.mock import patch

from app.modules.evaluation_runs.functional_communication_v3 import ALGORITHM_VERSION, _build, _review_override, review_or_recompute
from app.modules.evaluation_runs.schema import EvaluationReviewRevisionCreate
from app.modules.scenario_dialogues.model import DialogueSpeaker, DialogueStatus


def turn(index, speaker, text, *, act="response", semantic=None, asr=None):
    return SimpleNamespace(id=uuid4(), turn_index=index, speaker=speaker, dialogue_act=act, text=text,
                           semantic_evidence=semantic or {}, asr_provider=asr, llm_provider=None,
                           llm_model_version=None, llm_prompt_version=None)


def dialogue(status=DialogueStatus.completed, role="training"):
    value = SimpleNamespace(id=uuid4(), session_task_id=uuid4(), training_session_id=uuid4(), status=status,
                            contract_version="scenario-contract-v1", evaluation_role=role, prompt_count=0,
                            maximum_prompt_level=0, _v3_patient_profile_id=uuid4())
    value.contract_snapshot = {"version": "scenario-contract-v1", "required_information_units": [{"id": "place"}], "goal_requirements": ["place"]}
    return value


class FunctionalCommunicationV3Test(unittest.TestCase):
    def valid_turns(self):
        patient_text = "我要去门诊楼"
        return [turn(1, DialogueSpeaker.agent, "您好", act="opening"), turn(2, DialogueSpeaker.patient, patient_text, semantic={"source": "llm_structured", "information_units": [{"id": "place", "quote": patient_text, "confidence": .9}], "answered_current_question": True}, asr="tencent")]

    def test_completed_dialogue_creates_six_non_repeat_dimensions_without_overall(self):
        payload = _build(dialogue(), self.valid_turns())
        self.assertEqual(payload.algorithm_version, ALGORITHM_VERSION)
        self.assertEqual(payload.domain, "functional_communication")
        self.assertEqual([x.dimension_code for x in payload.dimensions], ["goal_achievement", "information_sufficiency", "response_ability", "relevance_and_organization", "independence", "repair_ability"])
        self.assertEqual(payload.dimensions[-1].status, "not_observed")
        self.assertIsNone(payload.dimensions[-1].value)
        self.assertNotIn("overall", payload.config_snapshot)
        snapshots = {x.dimension_code: x.evidence_snapshot for x in payload.dimensions}
        self.assertNotEqual(snapshots["response_ability"], snapshots["relevance_and_organization"])

    def test_fallback_mock_or_unlocatable_citation_cannot_be_formal(self):
        variants = [
            [turn(1, DialogueSpeaker.patient, "回答", semantic={"source": "contract_fallback", "information_units": []})],
            [turn(1, DialogueSpeaker.patient, "回答", semantic={"source": "llm_structured", "information_units": []}, asr="mock")],
            [turn(1, DialogueSpeaker.patient, "回答", semantic={"source": "llm_structured", "information_units": [{"id": "place", "quote": "不存在", "confidence": .9}]}, asr="tencent")],
        ]
        for turns in variants:
            payload = _build(dialogue(), turns)
            self.assertNotEqual(payload.result_status, "formal")
            self.assertFalse(payload.profile_eligibility)

    def test_generalization_is_not_profile_eligible_and_incomplete_is_unscorable(self):
        self.assertFalse(_build(dialogue(role="generalization_probe"), self.valid_turns()).profile_eligibility)
        payload = _build(dialogue(status=DialogueStatus.aborted), self.valid_turns())
        self.assertEqual(payload.result_status, "unscorable")

    def test_unjudgeable_targets_only_the_reviewed_dimension_as_unavailable_null(self):
        payload = _build(dialogue(), self.valid_turns())
        original = [type("Result", (), {"id": uuid4(), "dimension_code": x.dimension_code}) for x in payload.dimensions]
        target = original[1]
        current = type("Run", (), {"dimension_results": original})
        override = _review_override(current, EvaluationReviewRevisionCreate(dimension_result_id=target.id, review_action="unjudgeable"))
        rebuilt = _build(dialogue(), self.valid_turns(), review_override=override)
        values = {x.dimension_code: x for x in rebuilt.dimensions}
        self.assertEqual(values[target.dimension_code].status, "unavailable")
        self.assertIsNone(values[target.dimension_code].value)

    def test_recompute_failure_rolls_back_before_revision_and_before_adoption(self):
        run = type("Run", (), {"id": uuid4(), "domain": "functional_communication", "source_id": uuid4(), "dimension_results": []})
        user = type("User", (), {"id": uuid4()})
        payload = EvaluationReviewRevisionCreate(review_action="corrected", revised_value_snapshot={"goal_achievement": {"value": 50}})
        class Db:
            def __init__(self): self.rollbacks = 0
            def scalar(self, *_): return None
            def rollback(self): self.rollbacks += 1
            def add(self, *_): pass
            def flush(self): pass
        for failing in ("create", "adopt"):
            db = Db()
            with patch("app.modules.evaluation_runs.functional_communication_v3.get_run", return_value=run), \
                 patch("app.modules.evaluation_runs.functional_communication_v3.get_run_for_professional"), \
                 patch("app.modules.evaluation_runs.functional_communication_v3._load_dialogue", return_value=(dialogue(), self.valid_turns())), \
                 patch("app.modules.evaluation_runs.functional_communication_v3._build", return_value=_build(dialogue(), self.valid_turns())), \
                 patch("app.modules.evaluation_runs.functional_communication_v3.create_candidate_run", side_effect=RuntimeError("inject") if failing == "create" else None, return_value=type("Candidate", (), {"id": uuid4()})()), \
                 patch("app.modules.evaluation_runs.functional_communication_v3.adopt_candidate_run", side_effect=RuntimeError("inject") if failing == "adopt" else None):
                with self.assertRaises(RuntimeError): review_or_recompute(db, user, run.id, payload)
            self.assertEqual(db.rollbacks, 1)

    def test_unassigned_professional_cannot_review(self):
        run = type("Run", (), {"id": uuid4(), "domain": "functional_communication"})
        with patch("app.modules.evaluation_runs.functional_communication_v3.get_run", return_value=run), \
             patch("app.modules.evaluation_runs.functional_communication_v3.get_run_for_professional", side_effect=HTTPException(status_code=403)):
            with self.assertRaises(HTTPException) as error:
                review_or_recompute(type("Db", (), {})(), type("User", (), {"id": uuid4()})(), run.id, EvaluationReviewRevisionCreate(review_action="confirmed"))
        self.assertEqual(error.exception.status_code, 403)

    def test_repeated_corrected_request_reuses_existing_revision_without_new_run(self):
        run = type("Run", (), {"id": uuid4(), "domain": "functional_communication", "source_id": uuid4(), "dimension_results": []})
        replacement = type("Run", (), {"id": uuid4()})
        existing_revision = type("Revision", (), {"recomputed_run_id": replacement.id})
        db = type("Db", (), {"scalar": lambda self, *_: existing_revision})()
        user = type("User", (), {"id": uuid4()})
        payload = EvaluationReviewRevisionCreate(review_action="corrected", revised_value_snapshot={"goal_achievement": {"value": 60}})
        with patch("app.modules.evaluation_runs.functional_communication_v3.get_run", side_effect=[run, replacement]), \
             patch("app.modules.evaluation_runs.functional_communication_v3.get_run_for_professional"), \
             patch("app.modules.evaluation_runs.functional_communication_v3.create_candidate_run") as create:
            returned, revision = review_or_recompute(db, user, run.id, payload)
        self.assertIs(returned, replacement)
        self.assertIs(revision, existing_revision)
        create.assert_not_called()


if __name__ == "__main__":
    unittest.main()
