import unittest
from types import SimpleNamespace

from app.modules.scenario_dialogues.service import _acknowledging_fallback, _completion_reply, _follow_up_question, _match_units, _repair_score, _safety_escalation_reply, _trend_summary


class ScenarioDialogueStateTest(unittest.TestCase):
    def test_fallback_reply_acknowledges_patient_evidence(self):
        reply = _acknowledging_fallback(
            "我今天有点头疼。",
            "好的，请问您是想看病、挂号，还是咨询一下？",
            [{"id": "problem", "quote": "我今天有点头疼。"}],
        )
        self.assertIn("头疼", reply)
        self.assertIn("挂号", reply)

    def test_contract_fallback_collects_evidence_without_reference_sentence(self):
        contract = {
            "required_information_units": [
                {"id": "symptom", "label": "不适", "keywords": ["头疼", "头痛"]},
                {"id": "request", "label": "请求", "keywords": ["拿药", "拿点药", "帮忙"]},
            ]
        }

        evidence = _match_units(contract, "今天有点头疼，想来拿点药。")

        self.assertEqual({item["id"] for item in evidence}, {"symptom", "request"})
        self.assertTrue(all(item["quote"] == "今天有点头疼，想来拿点药。" for item in evidence))

    def test_unrelated_answer_does_not_create_evidence(self):
        contract = {"required_information_units": [{"id": "request", "label": "请求", "keywords": ["帮忙"]}]}
        self.assertEqual(_match_units(contract, "今天的天气很好"), [])

    def test_follow_up_comes_from_the_missing_unit_in_contract(self):
        contract = {
            "follow_up_questions": [
                {"target_information_unit": "symptom", "question": "请问您哪里不舒服？"},
                {"target_information_unit": "request", "question": "您希望我帮您做什么？"},
            ]
        }
        self.assertEqual(
            _follow_up_question(contract, "request", {"id": "request", "label": "需要的帮助"}),
            "您希望我帮您做什么？",
        )

    def test_contract_declares_default_multi_turn_bounds(self):
        contract = {"minimum_patient_turns": 2, "maximum_patient_turns": 5}
        self.assertEqual(contract["minimum_patient_turns"], 2)
        self.assertGreaterEqual(contract["maximum_patient_turns"], contract["minimum_patient_turns"])

    def test_urgent_expression_stops_role_play(self):
        self.assertIsNotNone(_safety_escalation_reply("我胸痛，喘不过气"))
        self.assertIsNone(_safety_escalation_reply("我今天有点头疼"))

    def test_trends_keep_repair_unobserved_as_null(self):
        dialogue = SimpleNamespace(prompt_count=0, maximum_prompt_level=0)
        evaluation = SimpleNamespace(goal_status="achieved", information_score=100, response_score=80, repair_score=None)
        trend = _trend_summary([(dialogue, evaluation)])
        self.assertEqual(trend["independent_goal_achievement_rate"], 1.0)
        self.assertIsNone(trend["observed_repair_success_rate"])

    def test_repair_score_uses_only_post_repair_response(self):
        agent = SimpleNamespace(speaker="agent", dialogue_act="repair", semantic_evidence={})
        patient = SimpleNamespace(speaker="patient", dialogue_act="response", semantic_evidence={"information_units": [{"id": "request"}]})
        self.assertEqual(_repair_score([agent, patient]), 100.0)
        self.assertEqual(_repair_score([agent]), 0.0)

    def test_completion_uses_scene_action_not_empty_confirmation(self):
        reply = _completion_reply({"completion_response": "请到挂号窗口办理，工作人员会告诉你下一步。"}, "我需要挂号")
        self.assertIn("挂号窗口", reply)


if __name__ == "__main__":
    unittest.main()
