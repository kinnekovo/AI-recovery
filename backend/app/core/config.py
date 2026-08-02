from functools import lru_cache
import os
from pathlib import Path


class Settings:
    app_name: str = "言语康复智能体 API"
    api_prefix: str = "/api"
    database_url: str
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int
    backend_cors_origins: list[str]
    storage_root: Path

    def __init__(self) -> None:
        self.database_url = os.getenv(
            "DATABASE_URL",
            "postgresql+psycopg://postgres:postgres@localhost:5432/speech_rehab_agent",
        )
        self.secret_key = os.getenv("SECRET_KEY", "dev-only-secret")
        self.access_token_expire_minutes = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))
        cors = os.getenv("BACKEND_CORS_ORIGINS", "http://localhost:5173")
        self.backend_cors_origins = [item.strip() for item in cors.split(",") if item.strip()]
        root = os.getenv("STORAGE_ROOT", "../storage")
        self.storage_root = Path(root).resolve()


@lru_cache
def get_settings() -> Settings:
    return Settings()
