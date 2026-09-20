import unittest
import uuid
from app.modules.controlled_governance import service as governance
from app.modules.controlled_governance.model import ControlledActionGovernanceRegistry, ControlledActivationEvaluationRun
from app.modules.controlled_policy import service as controlled
from tests.test_controlled_policy_v38 import ControlledPolicyV38Tests

class ControlledGovernanceV39Tests(ControlledPolicyV38Tests):
    def test_frozen_dataset_run_creates_append_only_governance_transition(self):
        proposal=self._proposal("difficulty_step_adjustment")
        dataset=governance.create_dataset(self.db,self.actor,"v39","1")
        item=governance.add_item(self.db,dataset.id,proposal.id)
        with self.assertRaisesRegex(ValueError,"only_frozen_can_archive"): governance.archive(self.db,dataset.id)
        governance.freeze(self.db,dataset.id)
        with self.assertRaisesRegex(ValueError,"frozen_dataset"): governance.remove_item(self.db,dataset.id,item.id)
        rows=governance.run(self.db,dataset.id,self.actor)
        self.assertEqual(len(rows),1);self.assertEqual(rows[0].governance_status,"insufficient_evidence")
        self.assertEqual(self.db.query(ControlledActivationEvaluationRun).count(),1)
        registry=self.db.query(ControlledActionGovernanceRegistry).one()
        self.assertEqual(registry.action_type,"difficulty_step_adjustment")
        self.assertEqual(len(governance.registry_history(self.db,registry.id)),1)

    def test_governance_suspension_blocks_new_v38_proposal_without_auto_apply(self):
        self.db.add(ControlledActionGovernanceRegistry(policy_version="policy-v2.0",rules_version="policy-rules-v1",action_type="difficulty_step_adjustment",governance_status="suspended",latest_evaluation_run_id=None,reason_codes=["critical_safety_event"]));self.db.commit()
        with self.assertRaisesRegex(ValueError,"governance_suspended"): self._proposal("difficulty_step_adjustment")
        self.assertEqual(self.db.get(type(self.session),self.session.id).status.value,"in_progress")

    def test_adapter_version_drift_requires_revalidation(self):
        run=ControlledActivationEvaluationRun(id=uuid.uuid4(),dataset_id=uuid.uuid4(),governance_schema_version="x",evaluation_policy_version="x",governance_policy_version="x",policy_version="policy-v2.0",rules_version="policy-rules-v1",activation_policy_version="x",adapter_version="old-adapter",action_type="difficulty_step_adjustment",input_fingerprint="drift",report={},governance_status="controlled",reason_codes=[],warnings=[])
        self.db.add(run);self.db.flush();self.db.add(ControlledActionGovernanceRegistry(policy_version="policy-v2.0",rules_version="policy-rules-v1",action_type="difficulty_step_adjustment",governance_status="controlled",latest_evaluation_run_id=run.id,reason_codes=[]));self.db.commit()
        with self.assertRaisesRegex(ValueError,"revalidation_required"):self._proposal("difficulty_step_adjustment")

if __name__=="__main__":unittest.main()
