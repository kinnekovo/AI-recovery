"""Run one durable, single-GPU avatar-video worker.

Start in a separate terminal after the API: `python scripts/run_avatar_video_worker.py`.
The worker intentionally has no HTTP server and keeps GPU work outside FastAPI.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

# Running this file directly sets sys.path to backend/scripts, not backend.
# Keep both documented launch forms working on Windows.
if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings
from app.core.observability import configure_logging, log_event
from app.database.base import import_models
from app.database.session import SessionLocal
from app.modules.avatar_videos.service import claim_next_task, process_task, recover_stale_running_tasks


def main() -> None:
    # FastAPI imports the full ORM graph during app startup. The standalone
    # worker must do the same before its first relationship-backed query.
    import_models()
    settings = get_settings()
    configure_logging(settings.log_level)
    db = SessionLocal()
    try:
        recover_stale_running_tasks(db)
    finally:
        db.close()
    log_event("info", "avatar_video", "worker_started", provider=settings.avatar_video_provider)
    while True:
        db = SessionLocal()
        try:
            task = claim_next_task(db)
            if task:
                process_task(db, task)
                continue
        except Exception as exc:
            db.rollback()
            log_event("error", "avatar_video", "worker_loop_failed", error=exc)
        finally:
            db.close()
        time.sleep(settings.avatar_video_worker_poll_seconds)


if __name__ == "__main__":
    main()
