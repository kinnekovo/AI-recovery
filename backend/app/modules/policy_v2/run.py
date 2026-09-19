import argparse
from uuid import UUID
from app.database.session import SessionLocal
from app.modules.policy_v2.service import generate_shadow
from app.modules.profile_v2.model import PatientProfileSnapshot

def main():
 p=argparse.ArgumentParser();g=p.add_mutually_exclusive_group(required=True);g.add_argument("--patient");g.add_argument("--from-profile");args=p.parse_args();db=SessionLocal()
 try:
  pid=UUID(args.patient) if args.patient else db.get(PatientProfileSnapshot,UUID(args.from_profile)).patient_profile_id
  print(generate_shadow(db,pid).id)
 finally: db.close()
if __name__=="__main__":main()
