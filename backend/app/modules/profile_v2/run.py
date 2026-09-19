"""Offline, explicit Profile V2 rebuild entry point (never invoked by training)."""
import argparse
from uuid import UUID
from app.database.session import SessionLocal
from app.modules.profile_v2.service import build_profile

def main():
    parser=argparse.ArgumentParser(); group=parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--patient"); group.add_argument("--all-stale", action="store_true")
    args=parser.parse_args(); db=SessionLocal()
    try:
        if args.patient: print(build_profile(db, UUID(args.patient)).id)
        else: print("--all-stale requires an operational scheduler/query and is intentionally not an implicit bulk rebuild.")
    finally: db.close()
if __name__ == "__main__": main()
