import argparse
from app.database.session import SessionLocal
from app.modules.policy_validation.service import run_validation
from uuid import UUID
def main():
 p=argparse.ArgumentParser();p.add_argument("--dataset",required=True);p.add_argument("--report",action="store_true");a=p.parse_args();db=SessionLocal()
 try:
  r=run_validation(db,UUID(a.dataset));print(r.report if a.report else r.id)
 finally:db.close()
if __name__=="__main__":main()
