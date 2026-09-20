"""Read-only lifecycle consistency audit; never mutates training or approvals."""
import argparse,json
from uuid import UUID
from app.database.session import SessionLocal
from app.modules.controlled_governance.model import ControlledActivationEvaluationDatasetItem
from app.modules.controlled_policy.model import ControlledActionApproval,ControlledActionExecution
from sqlalchemy import select
def main():
 p=argparse.ArgumentParser();p.add_argument("--dataset",required=True);a=p.parse_args();db=SessionLocal()
 try:
  items=list(db.scalars(select(ControlledActivationEvaluationDatasetItem).where(ControlledActivationEvaluationDatasetItem.dataset_id==UUID(a.dataset))));gaps=[]
  for i in items:
   e=db.scalar(select(ControlledActionExecution).where(ControlledActionExecution.proposal_id==i.proposal_id));ap=db.scalar(select(ControlledActionApproval).where(ControlledActionApproval.proposal_id==i.proposal_id))
   if e and not ap:gaps.append({"proposal_id":str(i.proposal_id),"code":"execution_without_approval"})
  print(json.dumps({"dataset_id":a.dataset,"valid":not gaps,"gaps":gaps}))
 finally:db.close()
if __name__=="__main__":main()
