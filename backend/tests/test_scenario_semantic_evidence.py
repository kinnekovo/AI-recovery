import unittest
import json
from types import SimpleNamespace
from unittest.mock import patch

from app.integrations.llm.scenario_semantics import _validate, extract_evidence, generate_role_reply


class ScenarioSemanticEvidenceTest(unittest.TestCase):
    def test_accepts_evidence_with_verbatim_quote_and_confidence(self):
        evidence = _validate({"information_units": [{"id": "symptom", "status": "supported", "quote": "头疼", "confidence": .92}], "answered_current_question": True, "relevance": "relevant"}, "我头疼，想看医生。", {"symptom", "request"})
        self.assertEqual(evidence["source"], "llm_structured")
        self.assertEqual(evidence["information_units"][0]["id"], "symptom")

    def test_rejects_hallucinated_quote(self):
        evidence = _validate({"information_units": [{"id": "request", "status": "supported", "quote": "帮我拿药", "confidence": .9}]}, "我头疼。", {"request"})
        self.assertIsNone(evidence)

    def test_rejects_out_of_range_confidence(self):
        evidence = _validate({"information_units": [{"id": "request", "status": "supported", "quote": "帮我", "confidence": 1.2}]}, "请帮我。", {"request"})
        self.assertIsNone(evidence)

    def test_confidence_threshold_is_preserved_for_rule_layer(self):
        evidence = _validate({"information_units": [{"id": "request", "status": "supported", "quote": "帮我", "confidence": .65}]}, "请帮我。", {"request"})
        self.assertEqual(evidence["information_units"][0]["confidence"], .65)

    def test_openai_compatible_response_is_parsed_as_evidence_only(self):
        settings = SimpleNamespace(llm_feedback_provider="openai_compatible", llm_feedback_api_key="test-key", llm_feedback_base_url="https://llm.example/v1", llm_feedback_model="test-model")
        response = SimpleNamespace(raise_for_status=lambda: None, json=lambda: {"choices": [{"message": {"content": '{"information_units":[{"id":"symptom","status":"supported","quote":"头疼","confidence":0.9}],"answered_current_question":true,"relevance":"relevant"}'}}]})
        contract = {"required_information_units": [{"id": "symptom", "label": "症状"}], "optional_information_units": []}
        with patch("app.integrations.llm.scenario_semantics.get_settings", return_value=settings), patch("app.integrations.llm.scenario_semantics.httpx.post", return_value=response) as post:
            evidence = extract_evidence(contract, "我头疼。")
        self.assertEqual(evidence["information_units"][0]["quote"], "头疼")
        self.assertTrue(post.call_args.args[0].endswith("/v1/chat/completions"))

    def test_provider_failure_returns_no_evidence(self):
        settings = SimpleNamespace(llm_feedback_provider="openai_compatible", llm_feedback_api_key="test-key", llm_feedback_base_url="https://llm.example/v1", llm_feedback_model="test-model")
        contract = {"required_information_units": [{"id": "symptom", "label": "症状"}], "optional_information_units": []}
        with patch("app.integrations.llm.scenario_semantics.get_settings", return_value=settings), patch("app.integrations.llm.scenario_semantics.httpx.post", side_effect=Exception("network")):
            # Unexpected provider errors must be contained by the training path.
            self.assertIsNone(extract_evidence(contract, "我头疼。"))

    def test_role_reply_failure_uses_contract_fallback(self):
        settings = SimpleNamespace(llm_feedback_provider="openai_compatible", llm_feedback_api_key="test-key", llm_feedback_base_url="https://llm.example/v1", llm_feedback_model="test-model")
        with patch("app.integrations.llm.scenario_semantics.get_settings", return_value=settings), patch("app.integrations.llm.scenario_semantics.httpx.post", side_effect=Exception("network")):
            self.assertIsNone(generate_role_reply({}, "clarify", "请再说说你的需要。"))

    def test_role_reply_receives_full_context_and_must_echo_locked_route(self):
        settings = SimpleNamespace(llm_feedback_provider="openai_compatible", llm_feedback_api_key="test-key", llm_feedback_base_url="https://llm.example/v1", llm_feedback_model="test-model")
        response = SimpleNamespace(raise_for_status=lambda: None, json=lambda: {"choices": [{"message": {"content": '{"dialogue_act":"clarify","target_information_unit_id":"request","reply":"头疼我记下了，您希望办理什么？"}'}}]})
        history = [
            {"speaker": "agent", "dialogue_act": "opening", "text": "您好，需要办理什么？"},
            {"speaker": "patient", "dialogue_act": "response", "text": "我今天头疼。"},
        ]
        with patch("app.integrations.llm.scenario_semantics.get_settings", return_value=settings), patch("app.integrations.llm.scenario_semantics.httpx.post", return_value=response) as post:
            reply = generate_role_reply(
                {"display_prompt": "医院挂号", "agent_role": "挂号处工作人员"},
                "clarify",
                "您希望办理什么？",
                conversation_history=history,
                current_patient_utterance="我今天头疼。",
                target_information_unit={"id": "request", "label": "需要办理的事情"},
                collected_information_unit_ids=["problem"],
            )
        request_body = post.call_args.kwargs["json"]
        request_context = json.loads(request_body["messages"][1]["content"])
        self.assertEqual(reply, "头疼我记下了，您希望办理什么？")
        self.assertEqual(request_context["conversation_history"], history)
        self.assertEqual(request_context["current_patient_utterance"], "我今天头疼。")
        self.assertEqual(request_context["locked_target_information_unit"]["id"], "request")

    def test_role_reply_is_rejected_when_model_changes_locked_target(self):
        settings = SimpleNamespace(llm_feedback_provider="openai_compatible", llm_feedback_api_key="test-key", llm_feedback_base_url="https://llm.example/v1", llm_feedback_model="test-model")
        response = SimpleNamespace(raise_for_status=lambda: None, json=lambda: {"choices": [{"message": {"content": '{"dialogue_act":"complete","target_information_unit_id":"","reply":"好的，结束了。"}'}}]})
        with patch("app.integrations.llm.scenario_semantics.get_settings", return_value=settings), patch("app.integrations.llm.scenario_semantics.httpx.post", return_value=response):
            reply = generate_role_reply({}, "clarify", "您希望办理什么？", target_information_unit={"id": "request"})
        self.assertIsNone(reply)
