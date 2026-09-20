import argparse,json
from uuid import UUID
from app.database.session import SessionLocal
from app.modules.controlled_governance import service
def main():
 p=argparse.ArgumentParser();p.add_argument("--dataset",required=True);p.add_argument("--action-type");p.add_argument("--report",action="store_true");a=p.parse_args();db=SessionLocal()
 try: print(json.dumps([{"id":str(x.id),"report":x.report} for x in service.run(db,UUID(a.dataset),None,a.action_type)],default=str))
 finally:db.close()
if __name__=="__main__":main()
