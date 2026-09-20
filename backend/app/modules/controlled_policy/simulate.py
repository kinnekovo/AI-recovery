"""Read-only controlled-activation eligibility and mapping preview."""
import argparse
import json
from uuid import UUID
from app.database.session import SessionLocal
from app.modules.controlled_policy import service
from app.modules.policy_v2.model import PolicyDecision

def main():
    parser = argparse.ArgumentParser(description="Read-only Policy V2 controlled-action simulation")
    parser.add_argument("--decision", required=True)
    parser.add_argument("--session", required=True)
    parser.add_argument("--action", choices=["training_focus_override", "difficulty_step_adjustment"], required=True)
    args = parser.parse_args()
    db = SessionLocal()
    try:
        decision = db.get(PolicyDecision, UUID(args.decision)); session = service._session(db, UUID(args.session))
        try:
            registry = service._eligibility(db, decision, session)
            value, reasons = service._action_from_decision(decision, args.action)
            proposed, current, scope = __import__("app.modules.controlled_policy.adapter", fromlist=["proposal_preview"]).proposal_preview(session, args.action, value)
            output = {"eligible": True, "validation_run_id": str(registry.latest_validation_run_id) if registry.latest_validation_run_id else None,
                      "proposal": {"action_type": args.action, "proposed_value": proposed, "current_value": current, "scope": scope, "reason_codes": reasons}}
        except ValueError as exc:
            output = {"eligible": False, "reason_code": str(exc)}
        print(json.dumps(output, ensure_ascii=False, default=str))
    finally:
        db.close()

if __name__ == "__main__": main()
