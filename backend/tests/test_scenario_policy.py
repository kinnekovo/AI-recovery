import unittest
from copy import deepcopy

from app.modules.scenario_dialogues.policy import choose_dialogue_action
from app.modules.training.model import TrainingType
from app.modules.training.service import SEED_TASKS, _complete_seed_dialogue_contract, _validate_scenario_contract


class ScenarioPolicyTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = next(item for item in SEED_TASKS if item["title"] == "医院看病场景")
        cls.contract = _complete_seed_dialogue_contract(deepcopy(source))["scoring_config"]
        _validate_scenario_contract(TrainingType.scenario, cls.contract)

    def test_hospital_requires_problem_before_completion(self):
        decision = choose_dialogue_action(
            self.contract,
            collected={"medical_intent", "request"},
            patient_turn_count=1,
            minimum_patient_turns=2,
            maximum_patient_turns=5,
        )
        self.assertEqual(decision.action, "acknowledge_and_ask")
        self.assertEqual(decision.target["id"], "problem")

    def test_unrelated_answer_repeats_the_current_question(self):
        decision = choose_dialogue_action(
            self.contract,
            collected={"medical_intent", "request"},
            patient_turn_count=2,
            minimum_patient_turns=2,
            maximum_patient_turns=5,
            current_target_id="problem",
            answered_current_question=False,
            answer_status="uncertain",
        )
        self.assertEqual(decision.action, "clarify_current")
        self.assertEqual(decision.target["id"], "problem")

    def test_time_is_not_asked_before_problem_and_not_auto_prompted(self):
        decision = choose_dialogue_action(
            self.contract,
            collected={"medical_intent", "problem", "request"},
            patient_turn_count=2,
            minimum_patient_turns=2,
            maximum_patient_turns=5,
        )
        self.assertEqual(decision.action, "complete")

    def test_explicit_optional_policy_can_request_dependent_unit(self):
        contract = deepcopy(self.contract)
        contract["optional_follow_up_policy"] = "always_before_completion"
        decision = choose_dialogue_action(
            contract,
            collected={"medical_intent", "problem", "request"},
            patient_turn_count=2,
            minimum_patient_turns=2,
            maximum_patient_turns=5,
        )
        self.assertEqual(decision.action, "ask_optional")
        self.assertEqual(decision.target["id"], "time")


if __name__ == "__main__":
    unittest.main()
