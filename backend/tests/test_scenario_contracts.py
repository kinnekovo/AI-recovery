import unittest
from copy import deepcopy
from types import SimpleNamespace

from fastapi import HTTPException

from app.modules.training.model import TaskTemplate, TrainingType
from app.modules.training.service import SEED_TASKS, _complete_seed_dialogue_contract, _validate_scenario_contract, has_functional_scenario_contract


class ScenarioContractTest(unittest.TestCase):
    def test_seed_contracts_gain_explicit_multi_turn_fields(self):
        source = next(item for item in SEED_TASKS if item["task_type"].value == "scenario")
        contract = _complete_seed_dialogue_contract(deepcopy(source))["scoring_config"]
        self.assertEqual(contract["minimum_patient_turns"], 2)
        self.assertEqual(contract["maximum_patient_turns"], 5)
        self.assertTrue(contract["follow_up_questions"])
        self.assertTrue(contract["completion_response"])
    def test_seed_templates_can_be_instantiated_with_their_contracts(self) -> None:
        templates = [
            TaskTemplate(**{**item, "scoring_config": item.get("scoring_config", {"mode": "repeat"})})
            for item in SEED_TASKS
        ]

        self.assertEqual(len(templates), len(SEED_TASKS))
        self.assertTrue(all(template.scoring_config for template in templates))

    def test_every_seeded_scenario_has_a_functional_contract(self) -> None:
        scenarios = [item for item in SEED_TASKS if item["task_type"] == TrainingType.scenario]

        self.assertGreaterEqual(len(scenarios), 5)
        for scenario in scenarios:
            config = scenario["scoring_config"]
            _validate_scenario_contract(TrainingType.scenario, config)
            self.assertGreaterEqual(len(config["required_information_units"]), 2)
            self.assertTrue(config["prompt_hints"])

    def test_generalization_probes_are_not_regular_training_material(self) -> None:
        probes = [
            item
            for item in SEED_TASKS
            if item["task_type"] == TrainingType.scenario
            and item["scoring_config"].get("evaluation_role") == "generalization_probe"
        ]

        self.assertGreaterEqual(len(probes), 2)
        self.assertTrue(all(item["recommendation_weight"] == 0 for item in probes))

    def test_scenario_cannot_be_created_without_a_functional_contract(self) -> None:
        with self.assertRaises(HTTPException) as context:
            _validate_scenario_contract(TrainingType.scenario, {"mode": "mock"})

        self.assertEqual(context.exception.status_code, 400)

    def test_legacy_scenario_without_contract_is_not_safe_to_assign(self) -> None:
        legacy = SimpleNamespace(task_type=TrainingType.scenario, scoring_config={})
        repeat = SimpleNamespace(task_type=TrainingType.repeat, scoring_config={})

        self.assertFalse(has_functional_scenario_contract(legacy))
        self.assertTrue(has_functional_scenario_contract(repeat))

    def test_contract_rejects_duplicate_information_units(self) -> None:
        invalid = {
            "version": "scenario-contract-v1",
            "mode": "functional_scenario",
            "display_prompt": "请表达需求",
            "communication_goal": "让对方理解患者的求助需求",
            "required_information_units": [
                {"id": "need", "label": "需求", "keywords": ["帮忙"]},
                {"id": "need", "label": "补充", "keywords": ["现在"]},
            ],
            "goal_requirements": ["need"],
            "prompt_hints": ["先说你需要什么"],
        }

        with self.assertRaises(HTTPException):
            _validate_scenario_contract(TrainingType.scenario, invalid)


if __name__ == "__main__":
    unittest.main()
