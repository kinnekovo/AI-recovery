from functools import lru_cache
import os
from pathlib import Path


def load_env_file(env_path: Path) -> None:
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


class Settings:
    app_name: str = "言语康复智能体 API"
    api_prefix: str = "/api"
    database_url: str
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int
    backend_cors_origins: list[str]
    storage_root: Path
    speech_eval_provider: str
    asr_provider: str
    asr_api_key: str | None
    asr_base_url: str | None
    tencentcloud_secret_id: str | None
    tencentcloud_secret_key: str | None
    tencent_asr_app_id: str | None
    tencent_asr_region: str
    tencent_asr_engine_model_type: str
    tencent_asr_voice_format: str
    acoustic_provider: str
    acoustic_api_key: str | None
    acoustic_base_url: str | None
    llm_feedback_provider: str
    llm_feedback_api_key: str | None
    llm_feedback_base_url: str | None
    llm_feedback_model: str | None

    def __init__(self) -> None:
        backend_dir = Path(__file__).resolve().parents[2]
        load_env_file(backend_dir / ".env")

        self.database_url = os.getenv(
            "DATABASE_URL",
            "postgresql+psycopg://postgres:postgres@localhost:5432/speech_rehab_agent",
        )
        self.secret_key = os.getenv("SECRET_KEY", "dev-only-secret")
        self.access_token_expire_minutes = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))
        cors = os.getenv("BACKEND_CORS_ORIGINS", "http://localhost:5173")
        self.backend_cors_origins = [item.strip() for item in cors.split(",") if item.strip()]

        storage_root = Path(os.getenv("STORAGE_ROOT", "../storage"))
        if not storage_root.is_absolute():
            storage_root = backend_dir / storage_root
        self.storage_root = storage_root.resolve()

        self.speech_eval_provider = os.getenv("SPEECH_EVAL_PROVIDER", "mock").strip().lower() or "mock"
        self.asr_provider = os.getenv("ASR_PROVIDER", "mock").strip().lower() or "mock"
        self.asr_api_key = os.getenv("ASR_API_KEY")
        self.asr_base_url = os.getenv("ASR_BASE_URL")
        self.tencentcloud_secret_id = os.getenv("TENCENTCLOUD_SECRET_ID")
        self.tencentcloud_secret_key = os.getenv("TENCENTCLOUD_SECRET_KEY")
        self.tencent_asr_app_id = os.getenv("TENCENT_ASR_APP_ID")
        self.tencent_asr_region = os.getenv("TENCENT_ASR_REGION", "ap-guangzhou")
        self.tencent_asr_engine_model_type = os.getenv("TENCENT_ASR_ENGINE_MODEL_TYPE", "16k_zh")
        self.tencent_asr_voice_format = os.getenv("TENCENT_ASR_VOICE_FORMAT", "ogg-opus")
        self.acoustic_provider = os.getenv("ACOUSTIC_PROVIDER", "mock").strip().lower() or "mock"
        self.acoustic_api_key = os.getenv("ACOUSTIC_API_KEY")
        self.acoustic_base_url = os.getenv("ACOUSTIC_BASE_URL")
        self.llm_feedback_provider = os.getenv("LLM_FEEDBACK_PROVIDER", "mock").strip().lower() or "mock"
        self.llm_feedback_api_key = os.getenv("LLM_FEEDBACK_API_KEY")
        self.llm_feedback_base_url = os.getenv("LLM_FEEDBACK_BASE_URL")
        self.llm_feedback_model = os.getenv("LLM_FEEDBACK_MODEL")


@lru_cache
def get_settings() -> Settings:
    return Settings()
