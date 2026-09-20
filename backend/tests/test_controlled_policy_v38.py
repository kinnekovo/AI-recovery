import unittest
import uuid
from types import SimpleNamespace
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.dialects.postgresql import JSONB
from app.database.base import Base, import_models
from app.modules.controlled_policy import service
from app.modules.controlled_policy.model import (ControlledActionApproval, ControlledActionAuditEvent, ControlledActionExecution,
    ControlledActionObservation, ControlledActionProposal, ControlledActionSafetyEvent)
from app.modules.policy_v2.model import PolicyDecision
from app.modules.policy_validation.model import PolicyValidationRegistry, PolicyValidationRun
from app.modules.profile_v2.model import PatientProfileSnapshot
from app.modules.training.model import SessionTask, TaskTemplate, TrainingSession, TrainingStatus, TrainingType

@compiles(JSONB, "sqlite")
def _jsonb_sqlite(_type, _compiler, **_kwargs): return "JSON"

class ControlledPolicyV38Tests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        import_models(); Base.metadata.create_all(self.engine)
        self.db = sessionmaker(bind=self.engine, expire_on_commit=False)()
        self.patient_id = uuid.uuid4(); self.actor = SimpleNamespace(id=uuid.uuid4())
        self.snapshot = PatientProfileSnapshot(id=uuid.uuid4(), patient_profile_id=self.patient_id, profile_schema_version="profile-v2.0", mapping_version="x", evidence_policy_version="x", status="complete", evidence_fingerprint="a", payload={})
        self.db.add(self.snapshot)
        self.decision = PolicyDecision(id=uuid.uuid4(), patient_profile_id=self.patient_id, profile_snapshot_id=self.snapshot.id,
            policy_version="policy-v2.0", rules_version="policy-rules-v1", mode="shadow", status="generated", input_fingerprint="x",
            decision_payload={"training_focus": [{"dimension_code":"repeat.accuracy", "priority":"high", "reason_codes":["FALLING_TREND"]}], "difficulty":{"recommended_difficulty_action":"increase"}}, reason_codes=[], warnings=[])
        self.db.add(self.decision)
        self.db.add(PolicyValidationRegistry(id=uuid.uuid4(), policy_version="policy-v2.0", rules_version="policy-rules-v1", validation_status="eligible_for_controlled_activation", latest_validation_run_id=None, status_reason_codes=[]))
        repeat = TaskTemplate(id=uuid.uuid4(), task_type=TrainingType.repeat, title="r", instruction="i", target_text="t")
        scenario = TaskTemplate(id=uuid.uuid4(), task_type=TrainingType.scenario, title="s", instruction="i", target_text="t")
        self.session = TrainingSession(id=uuid.uuid4(), patient_profile_id=self.patient_id, training_type=TrainingType.repeat, status=TrainingStatus.in_progress)
        self.db.add_all([repeat, scenario, self.session]); self.db.flush()
        self.repeat_task = SessionTask(id=uuid.uuid4(), training_session_id=self.session.id, task_template_id=repeat.id, order_index=1, prompt_level=1)
        self.scenario_task = SessionTask(id=uuid.uuid4(), training_session_id=self.session.id, task_template_id=scenario.id, order_index=0, prompt_level=1)
        self.db.add_all([self.repeat_task, self.scenario_task]); self.db.commit()

    def tearDown(self): self.db.close(); self.engine.dispose()
    def _proposal(self, action): return service.create_proposal(self.db, self.decision.id, action, self.session.id, self.actor)

    def test_no_approval_cannot_mutate_real_training(self):
        proposal = self._proposal("difficulty_step_adjustment")
        with self.assertRaisesRegex(ValueError, "approval_required"): service.apply(self.db, proposal.id, self.patient_id, self.actor)
        self.assertEqual(self.db.get(SessionTask, self.repeat_task.id).prompt_level, 1)
        self.assertEqual(self.db.get(PolicyDecision, self.decision.id).mode, "shadow")

    def test_approved_focus_runs_once_observes_and_rolls_back(self):
        proposal = self._proposal("training_focus_override")
        service.approve(self.db, proposal.id, self.patient_id, self.actor, "reviewed")
        execution = service.apply(self.db, proposal.id, self.patient_id, self.actor)
        self.assertEqual(execution.status, "applied")
        self.assertEqual(self.db.get(SessionTask, self.repeat_task.id).order_index, 0)
        self.assertEqual(self.db.get(PolicyDecision, self.decision.id).mode, "shadow")
        with self.assertRaisesRegex(ValueError, "duplicate_apply"): service.apply(self.db, proposal.id, self.patient_id, self.actor)
        observation = service.observe(self.db, execution.id, self.patient_id, self.actor, "therapist_accepted")
        self.assertEqual(observation.outcome, "therapist_accepted")
        rolled = service.rollback(self.db, execution.id, self.patient_id, self.actor, "manual_review")
        self.assertEqual(rolled.status, "applied")
        self.assertIsNotNone(rolled.rolled_back_at)
        self.assertEqual(self.db.get(SessionTask, self.repeat_task.id).order_index, 1)
        self.assertGreaterEqual(self.db.query(ControlledActionAuditEvent).count(), 4)

    def test_suspended_registry_blocks_proposal_and_apply(self):
        registry = self.db.query(PolicyValidationRegistry).one(); registry.validation_status = "suspended"; self.db.commit()
        with self.assertRaisesRegex(ValueError, "activation_suspended"): self._proposal("difficulty_step_adjustment")
        self.assertEqual(self.db.query(ControlledActionProposal).count(), 0)

    def test_state_conflict_blocks_manual_change_and_only_target_changes(self):
        proposal = self._proposal("difficulty_step_adjustment")
        service.approve(self.db, proposal.id, self.patient_id, self.actor)
        self.db.get(SessionTask, self.scenario_task.id).prompt_level = 3; self.db.commit()
        with self.assertRaisesRegex(ValueError, "state_conflict"): service.apply(self.db, proposal.id, self.patient_id, self.actor)
        self.assertEqual(self.db.get(SessionTask, self.repeat_task.id).prompt_level, 1)
        self.assertEqual(self.db.get(PolicyDecision, self.decision.id).status, "generated")
        self.assertEqual(self.db.get(PatientProfileSnapshot, self.snapshot.id).status, "complete")

    def test_difficulty_is_one_step_and_boundary_is_no_op(self):
        proposal = self._proposal("difficulty_step_adjustment")
        self.assertEqual(proposal.proposed_value["prompt_level"], 0)
        service.approve(self.db, proposal.id, self.patient_id, self.actor)
        execution = service.apply(self.db, proposal.id, self.patient_id, self.actor)
        self.assertEqual(execution.after_state["prompt_level"], 0)
        self.assertEqual(self.db.get(SessionTask, self.scenario_task.id).prompt_level, 0)

    def test_rejection_stale_profile_and_expiry_cannot_apply(self):
        proposal = self._proposal("difficulty_step_adjustment")
        service.reject(self.db, proposal.id, self.patient_id, self.actor, "not_now")
        with self.assertRaisesRegex(ValueError, "approval_required"): service.apply(self.db, proposal.id, self.patient_id, self.actor)
        # A newer snapshot invalidates an otherwise eligible shadow decision.
        self.db.add(PatientProfileSnapshot(id=uuid.uuid4(), patient_profile_id=self.patient_id, profile_schema_version="profile-v2.0", mapping_version="x", evidence_policy_version="x", status="complete", evidence_fingerprint="new", payload={}))
        self.db.commit()
        with self.assertRaisesRegex(ValueError, "stale_profile"): self._proposal("training_focus_override")

    def test_boundary_no_op_is_explicit_and_not_a_second_mutation(self):
        self.db.get(SessionTask, self.scenario_task.id).prompt_level = 0; self.db.commit()
        proposal = self._proposal("difficulty_step_adjustment")
        self.assertTrue(proposal.proposed_value["no_op"])
        service.approve(self.db, proposal.id, self.patient_id, self.actor)
        execution = service.apply(self.db, proposal.id, self.patient_id, self.actor)
        self.assertEqual(execution.status, "no_op")
        self.assertEqual(self.db.get(SessionTask, self.scenario_task.id).prompt_level, 0)

if __name__ == "__main__": unittest.main()
