from pathlib import Path
import sys

from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings


def main() -> int:
    settings = get_settings()
    try:
        engine = create_engine(settings.effective_database_url, pool_pre_ping=True)
        with engine.connect() as connection:
            connection.execute(text("select 1"))
    except SQLAlchemyError as exc:
        print(f"database unavailable: {exc.__class__.__name__}")
        return 1
    print("database ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
