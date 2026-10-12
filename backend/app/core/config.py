from functools import lru_cache
import os
from pathlib import Path

from app.core.algorithm_config import config_value


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
    log_level: str
    database_url: str
    database_connect_timeout_seconds: int
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
    ffmpeg_bin: str | None
    acoustic_dba_calibration_offset: float
    acoustic_voice_threshold_dbfs: float
    acoustic_min_loudness_dbfs: float
    pronunciation_provider: str
    tencent_soe_app_id: str | None
    tencent_soe_server_type: int
    tencent_soe_engine_type: str
    tencent_soe_score_coeff: float
    tencent_soe_tone_detection: bool
    pronunciation_timeout_seconds: int
    pronunciation_shadow_mode: bool
    tts_provider: str
    tts_api_key: str | None
    tts_base_url: str | None
    tts_model: str | None
    tencent_tts_region: str
    tencent_tts_voice_type: int
    tencent_tts_sample_rate: int
    tencent_tts_speed: float
    windows_tts_voice: str
    windows_tts_speed: int
    tts_timeout_seconds: int
    vcl_provider: str
    tencent_vcl_region: str
    vcl_timeout_seconds: int
    aliyun_avatar_enabled: bool
    aliyun_avatar_auto_provision: bool
    aliyun_avatar_instance_id: str | None
    aliyun_avatar_endpoint: str
    tencent_avatar_enabled: bool
    tencent_avatar_sign: str | None
    tencent_avatar_asset_virtualman_key: str | None
    tencent_avatar_protocol: str
    tencent_avatar_driver_type: int
    tencent_avatar_user_id_prefix: str
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
        self.log_level = os.getenv("LOG_LEVEL", "INFO")
        self.database_connect_timeout_seconds = int(os.getenv("DATABASE_CONNECT_TIMEOUT_SECONDS", "5"))
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
        self.asr_timeout_seconds = int(os.getenv("ASR_TIMEOUT_SECONDS", "10"))
        self.tencentcloud_secret_id = os.getenv("TENCENTCLOUD_SECRET_ID")
        self.tencentcloud_secret_key = os.getenv("TENCENTCLOUD_SECRET_KEY")
        self.tencent_asr_app_id = os.getenv("TENCENT_ASR_APP_ID")
        self.tencent_asr_region = os.getenv("TENCENT_ASR_REGION", "ap-guangzhou")
        self.tencent_asr_engine_model_type = os.getenv("TENCENT_ASR_ENGINE_MODEL_TYPE", "16k_zh")
        self.tencent_asr_voice_format = os.getenv("TENCENT_ASR_VOICE_FORMAT", "ogg-opus")
        self.acoustic_provider = os.getenv("ACOUSTIC_PROVIDER", "mock").strip().lower() or "mock"
        self.acoustic_api_key = os.getenv("ACOUSTIC_API_KEY")
        self.acoustic_base_url = os.getenv("ACOUSTIC_BASE_URL")
        self.ffmpeg_bin = os.getenv("FFMPEG_BIN")
        self.acoustic_dba_calibration_offset = float(os.getenv("ACOUSTIC_DBA_CALIBRATION_OFFSET", "90"))
        self.acoustic_voice_threshold_dbfs = float(
            os.getenv("ACOUSTIC_VOICE_THRESHOLD_DBFS", str(config_value("acoustic_voice_threshold")))
        )
        self.acoustic_min_speaking_seconds = float(os.getenv("ACOUSTIC_MIN_SPEAKING_SECONDS", "1.0"))
        legacy_min_dba = os.getenv("ACOUSTIC_MIN_LOUDNESS_DBA")
        configured_min_dbfs = os.getenv("ACOUSTIC_MIN_LOUDNESS_DBFS")
        self.acoustic_min_loudness_dbfs = float(
            configured_min_dbfs
            if configured_min_dbfs is not None
            else float(legacy_min_dba) - self.acoustic_dba_calibration_offset
            if legacy_min_dba is not None
            else config_value("acoustic_min_loudness")
        )
        # Deprecated compatibility field. Formal quality decisions use dBFS only.
        self.acoustic_min_loudness_dba = self.acoustic_min_loudness_dbfs + self.acoustic_dba_calibration_offset
        self.acoustic_min_snr_db = float(os.getenv("ACOUSTIC_MIN_SNR_DB", "10"))
        self.acoustic_max_clipping_ratio = float(os.getenv("ACOUSTIC_MAX_CLIPPING_RATIO", "0.01"))
        self.pronunciation_provider = os.getenv("PRONUNCIATION_PROVIDER", "disabled").strip().lower() or "disabled"
        self.tencent_soe_app_id = os.getenv("TENCENT_SOE_APP_ID") or None
        self.tencent_soe_server_type = int(os.getenv("TENCENT_SOE_SERVER_TYPE", "1"))
        self.tencent_soe_engine_type = os.getenv("TENCENT_SOE_ENGINE_TYPE", "16k_zh").strip() or "16k_zh"
        self.tencent_soe_score_coeff = float(os.getenv("TENCENT_SOE_SCORE_COEFF", "1.0"))
        self.tencent_soe_tone_detection = os.getenv("TENCENT_SOE_TONE_DETECTION", "true").strip().lower() not in {"0", "false", "no"}
        self.pronunciation_timeout_seconds = int(os.getenv("PRONUNCIATION_TIMEOUT_SECONDS", "30"))
        self.pronunciation_shadow_mode = os.getenv("PRONUNCIATION_SHADOW_MODE", "true").strip().lower() not in {"0", "false", "no"}
        self.tts_provider = os.getenv("TTS_PROVIDER", "mock").strip().lower() or "mock"
        self.tts_api_key = os.getenv("TTS_API_KEY")
        self.tts_base_url = os.getenv("TTS_BASE_URL")
        self.tts_model = os.getenv("TTS_MODEL")
        self.tencent_tts_region = os.getenv("TENCENT_TTS_REGION", "ap-guangzhou").strip() or "ap-guangzhou"
        self.tencent_tts_voice_type = int(os.getenv("TENCENT_TTS_VOICE_TYPE", "502001"))
        self.tencent_tts_sample_rate = int(os.getenv("TENCENT_TTS_SAMPLE_RATE", "24000"))
        self.tencent_tts_speed = float(os.getenv("TENCENT_TTS_SPEED", "-1"))
        self.windows_tts_voice = os.getenv("WINDOWS_TTS_VOICE", "Microsoft Huihui Desktop").strip() or "Microsoft Huihui Desktop"
        self.windows_tts_speed = int(os.getenv("WINDOWS_TTS_SPEED", "-1"))
        self.tts_timeout_seconds = int(os.getenv("TTS_TIMEOUT_SECONDS", "10"))
        self.vcl_provider = os.getenv("VCL_PROVIDER", "mock").strip().lower() or "mock"
        self.tencent_vcl_region = os.getenv("TENCENT_VCL_REGION", "ap-guangzhou").strip() or "ap-guangzhou"
        self.vcl_timeout_seconds = int(os.getenv("VCL_TIMEOUT_SECONDS", "20"))
        self.aliyun_avatar_enabled = os.getenv("ALIYUN_AVATAR_ENABLED", "false").strip().lower() in {"1", "true", "yes"}
        self.aliyun_avatar_auto_provision = os.getenv("ALIYUN_AVATAR_AUTO_PROVISION", "false").strip().lower() in {"1", "true", "yes"}
        self.aliyun_avatar_instance_id = os.getenv("ALIYUN_AVATAR_INSTANCE_ID") or None
        self.aliyun_avatar_endpoint = os.getenv("ALIYUN_AVATAR_ENDPOINT", "lingmou.cn-beijing.aliyuncs.com").strip()
        self.tencent_avatar_enabled = os.getenv("TENCENT_AVATAR_ENABLED", "false").strip().lower() in {"1", "true", "yes"}
        self.tencent_avatar_sign = os.getenv("TENCENT_AVATAR_SIGN") or None
        self.tencent_avatar_asset_virtualman_key = os.getenv("TENCENT_AVATAR_ASSET_VIRTUALMAN_KEY") or None
        self.tencent_avatar_protocol = os.getenv("TENCENT_AVATAR_PROTOCOL", "webrtc").strip().lower() or "webrtc"
        self.tencent_avatar_driver_type = int(os.getenv("TENCENT_AVATAR_DRIVER_TYPE", "3"))
        self.tencent_avatar_user_id_prefix = os.getenv("TENCENT_AVATAR_USER_ID_PREFIX", "speech-rehab-").strip()
        self.llm_feedback_provider = os.getenv("LLM_FEEDBACK_PROVIDER", "mock").strip().lower() or "mock"
        self.llm_feedback_api_key = os.getenv("LLM_FEEDBACK_API_KEY")
        self.llm_feedback_base_url = os.getenv("LLM_FEEDBACK_BASE_URL")
        self.llm_feedback_model = os.getenv("LLM_FEEDBACK_MODEL")

    @property
    def effective_database_url(self) -> str:
        if not self.database_url.startswith("postgresql") or "connect_timeout=" in self.database_url:
            return self.database_url
        separator = "&" if "?" in self.database_url else "?"
        return f"{self.database_url}{separator}connect_timeout={self.database_connect_timeout_seconds}"


@lru_cache
def get_settings() -> Settings:
    return Settings()
