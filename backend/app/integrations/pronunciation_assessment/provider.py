import base64
import hashlib
import hmac
import json
import random
from dataclasses import dataclass, field
from pathlib import Path
import subprocess
import tempfile
import threading
import time
from urllib.parse import quote
from uuid import uuid4

from app.core.config import get_settings
from app.core.redaction import provider_error_summary


class PronunciationProviderError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class PronunciationSegmentResult:
    level: str
    ordinal: int
    reference_text: str | None = None
    recognized_text: str | None = None
    start_ms: int | None = None
    end_ms: int | None = None
    accuracy: float | None = None
    fluency: float | None = None
    match_type: str = "unavailable"
    reference_tone: int | None = None
    recognized_tone: int | None = None
    tone_correct: bool | None = None
    payload: dict = field(default_factory=dict)


@dataclass(frozen=True)
class PronunciationAssessmentResult:
    provider: str
    provider_version: str
    evaluation_mode: str
    status: str
    overall_accuracy: float | None = None
    fluency: float | None = None
    completion: float | None = None
    suggested_score: float | None = None
    confidence: float | None = None
    segments: tuple[PronunciationSegmentResult, ...] = ()
    raw_output: dict = field(default_factory=dict)
    error_code: str | None = None
    error_message: str | None = None


class PronunciationAssessmentProvider:
    provider_name = "base"

    def evaluate(self, audio_path: str, reference_text: str, evaluation_mode: str) -> PronunciationAssessmentResult:
        raise NotImplementedError


class DisabledPronunciationAssessmentProvider(PronunciationAssessmentProvider):
    provider_name = "disabled"

    def __init__(self, requested_provider: str = "disabled") -> None:
        self.requested_provider = requested_provider

    def evaluate(self, audio_path: str, reference_text: str, evaluation_mode: str) -> PronunciationAssessmentResult:
        return PronunciationAssessmentResult(
            provider=self.provider_name,
            provider_version="disabled-v1",
            evaluation_mode=evaluation_mode,
            status="unavailable",
            error_code="provider_disabled",
            error_message="精细发音评测尚未启用。",
        )


class TencentSoeProvider(PronunciationAssessmentProvider):
    provider_name = "tencent_soe"
    provider_version = "soe-new-wss-v1"
    mode_values = {"word": 0, "sentence": 1, "paragraph": 2, "free": 3, "phoneme": 8, "scenario": 5}

    def __init__(self) -> None:
        settings = get_settings()
        self.secret_id = settings.tencentcloud_secret_id
        self.secret_key = settings.tencentcloud_secret_key
        self.app_id = settings.tencent_soe_app_id
        self.engine_type = settings.tencent_soe_engine_type
        self.score_coeff = settings.tencent_soe_score_coeff
        self.timeout_seconds = settings.pronunciation_timeout_seconds
        self.ffmpeg_bin = settings.ffmpeg_bin or self._bundled_ffmpeg_bin()

    def evaluate(self, audio_path: str, reference_text: str, evaluation_mode: str) -> PronunciationAssessmentResult:
        self._validate()
        mode = self.mode_values.get(evaluation_mode, self.mode_values["sentence"])
        prepared_audio: Path | None = None
        try:
            prepared_audio = self._prepare_wav(audio_path)
            audio_bytes = prepared_audio.read_bytes()
            if len(audio_bytes) > 10 * 1024 * 1024:
                raise PronunciationProviderError("payload_too_large", "发音评测录音超过 10MB，请缩短录音后重试。")
            import websocket
        except ImportError as exc:
            raise PronunciationProviderError("dependency_missing", "缺少 websocket-client，请安装 backend requirements。") from exc

        connection = None
        worker = None
        try:
            opened = threading.Event()
            completed = threading.Event()
            state: dict[str, object] = {}

            def on_open(_connection) -> None:
                opened.set()

            def on_message(_connection, message) -> None:
                try:
                    payload = self._decode_response(message)
                    if payload.get("final") == 1:
                        state["result"] = payload
                        completed.set()
                except PronunciationProviderError as exc:
                    state["error"] = exc
                    completed.set()

            def on_error(_connection, error) -> None:
                state["error"] = PronunciationProviderError(
                    "provider_error", provider_error_summary("腾讯 SOE 新版评测失败", error)
                )
                completed.set()

            def on_close(_connection, *_args) -> None:
                if "result" not in state and "error" not in state:
                    state["error"] = PronunciationProviderError("connection_closed", "腾讯 SOE 新版连接在返回评测结果前关闭。")
                    completed.set()

            connection = websocket.WebSocketApp(
                self._build_websocket_url(reference_text, mode),
                on_open=on_open,
                on_message=on_message,
                on_error=on_error,
                on_close=on_close,
            )
            worker = threading.Thread(target=connection.run_forever, daemon=True)
            worker.start()
            if not opened.wait(self.timeout_seconds):
                raise PronunciationProviderError("connection_timeout", "腾讯 SOE 新版连接超时，未进入可发送音频状态。")
            if connection.sock is None:
                raise PronunciationProviderError("connection_closed", "腾讯 SOE 新版连接已关闭，无法发送音频。")
            connection.sock.send_binary(audio_bytes)
            # The Tencent recording-mode SDK ends a one-shot upload with this text frame.
            # Without it, the service can keep waiting instead of committing the audio buffer.
            connection.sock.send(json.dumps({"type": "end"}))
            if not completed.wait(self.timeout_seconds):
                raise PronunciationProviderError("provider_timeout", "腾讯 SOE 新版评测超时，未返回最终结果。")
            if error := state.get("error"):
                raise error
            result = state.get("result")
            if not isinstance(result, dict):
                raise PronunciationProviderError("bad_response", "腾讯 SOE 新版未返回最终评测结果。")
            return parse_tencent_soe_response(result, evaluation_mode, self.provider_version)
        except PronunciationProviderError:
            raise
        except Exception as exc:
            raise PronunciationProviderError("provider_error", provider_error_summary("腾讯 SOE 新版评测失败", exc)) from exc
        finally:
            if connection is not None:
                connection.close()
            if worker is not None:
                worker.join(timeout=1)
            if prepared_audio is not None:
                prepared_audio.unlink(missing_ok=True)

    def _validate(self) -> None:
        missing = []
        if not self.secret_id:
            missing.append("TENCENTCLOUD_SECRET_ID")
        if not self.secret_key:
            missing.append("TENCENTCLOUD_SECRET_KEY")
        if not self.app_id:
            missing.append("TENCENT_SOE_APP_ID")
        if missing:
            raise PronunciationProviderError("config_missing", f"腾讯 SOE 新版配置缺失：{', '.join(missing)}")
        if self.engine_type not in {"16k_zh", "16k_en"}:
            raise PronunciationProviderError("config_invalid", "TENCENT_SOE_ENGINE_TYPE 仅支持 16k_zh 或 16k_en。")

    def _build_websocket_url(self, reference_text: str, mode: int) -> str:
        timestamp = int(time.time())
        params = {
            "eval_mode": str(mode),
            "expired": str(timestamp + 300),
            "nonce": str(random.randint(1, 999_999_999)),
            "rec_mode": "1",
            "ref_text": reference_text,
            "score_coeff": f"{self.score_coeff:.1f}",
            "secretid": self.secret_id,
            "sentence_info_enabled": "0",
            "server_engine_type": self.engine_type,
            "text_mode": "0",
            "timestamp": str(timestamp),
            "voice_format": "1",
            "voice_id": str(uuid4()),
            "keyword": "",
        }
        path = f"soe.cloud.tencent.com/soe/api/{self.app_id}"
        signing_query = "&".join(f"{key}={value}" for key, value in sorted(params.items()))
        signature = base64.b64encode(
            hmac.new(self.secret_key.encode("utf-8"), f"{path}?{signing_query}".encode("utf-8"), hashlib.sha1).digest()
        ).decode("ascii")
        query = "&".join(f"{key}={quote(value, safe='')}" for key, value in {**params, "signature": signature}.items())
        return f"wss://{path}?{query}"

    @staticmethod
    def _decode_response(message) -> dict:
        if isinstance(message, bytes):
            message = message.decode("utf-8")
        if not isinstance(message, str):
            raise PronunciationProviderError("bad_response", "腾讯 SOE 新版返回了无法识别的消息。")
        try:
            payload = json.loads(message)
        except json.JSONDecodeError as exc:
            raise PronunciationProviderError("bad_response", "腾讯 SOE 新版返回了无效 JSON。") from exc
        if int(payload.get("code", 0)) != 0:
            raise PronunciationProviderError("provider_error", f"腾讯 SOE 新版评测失败：{payload.get('message') or '未知错误'}")
        return payload

    def _prepare_wav(self, audio_path: str) -> Path:
        if not self.ffmpeg_bin:
            raise PronunciationProviderError("transcode_dependency_missing", "未找到 ffmpeg，无法将浏览器录音转换为发音评测所需的 WAV 格式。")
        source = Path(audio_path)
        if not source.is_file() or source.stat().st_size == 0:
            raise PronunciationProviderError("audio_missing", "发音评测音频不存在或为空。")
        with tempfile.NamedTemporaryFile(prefix="tencent-soe-", suffix=".wav", delete=False) as temp_file:
            destination = Path(temp_file.name)
        command = [
            self.ffmpeg_bin, "-y", "-hide_banner", "-loglevel", "error", "-i", str(source),
            "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(destination),
        ]
        try:
            subprocess.run(command, check=True, capture_output=True)
            if destination.stat().st_size == 0:
                raise RuntimeError("转换后的音频为空")
        except (OSError, subprocess.CalledProcessError, RuntimeError) as exc:
            destination.unlink(missing_ok=True)
            raise PronunciationProviderError("audio_transcode_failed", "录音格式转换失败，请重新录制后再试。") from exc
        return destination

    @staticmethod
    def _bundled_ffmpeg_bin() -> str | None:
        try:
            import imageio_ffmpeg
        except ImportError:
            return None
        return imageio_ffmpeg.get_ffmpeg_exe()


def _normalize_percentage(value) -> float | None:
    if value is None or value == -1:
        return None
    value = float(value)
    return round(value * 100 if 0 <= value <= 1 else value, 2)


def _normalize_ratio(value) -> float | None:
    if value is None or value == -1:
        return None
    value = float(value)
    return round(value / 100 if value > 1 else value, 4)


def _match_type(value) -> str:
    return {0: "matched", 1: "addition", 2: "omission", 3: "substitution", 4: "out_of_vocabulary"}.get(value, "unavailable")


def parse_tencent_soe_response(payload: dict, evaluation_mode: str, provider_version: str = "soe-basic-v20180724") -> PronunciationAssessmentResult:
    if not isinstance(payload, dict):
        raise PronunciationProviderError("bad_response", "腾讯 SOE 返回格式无效。")
    response = payload.get("Response", payload)
    if not isinstance(response, dict):
        raise PronunciationProviderError("bad_response", "腾讯 SOE 返回内容无效。")
    if isinstance(response.get("result"), dict):
        response = response["result"]
    expected_fields = {"PronAccuracy", "PronFluency", "PronCompletion", "SuggestedScore", "Words"}
    if not expected_fields.intersection(response):
        raise PronunciationProviderError("bad_response", "腾讯 SOE 未返回可解析的评测结果。")
    words = response.get("Words") or []
    segments: list[PronunciationSegmentResult] = []
    for word_index, word in enumerate(words):
        tone = word.get("Tone") or {}
        segments.append(
            PronunciationSegmentResult(
                level="word",
                ordinal=word_index,
                reference_text=word.get("ReferenceWord"),
                recognized_text=word.get("Word"),
                start_ms=word.get("MemBeginTime"),
                end_ms=word.get("MemEndTime"),
                accuracy=_normalize_percentage(word.get("PronAccuracy")),
                fluency=_normalize_ratio(word.get("PronFluency")),
                match_type=_match_type(word.get("MatchTag")),
                reference_tone=tone.get("RefTone") if tone.get("Valid") else None,
                recognized_tone=tone.get("Tone") if tone.get("Valid") else None,
                tone_correct=tone.get("RefTone") == tone.get("Tone") if tone.get("Valid") else None,
                payload=word,
            )
        )
        for phone_index, phone in enumerate(word.get("PhoneInfos") or []):
            segments.append(
                PronunciationSegmentResult(
                    level="phoneme",
                    ordinal=phone_index,
                    reference_text=phone.get("ReferencePhone"),
                    recognized_text=phone.get("Phone"),
                    start_ms=phone.get("MemBeginTime"),
                    end_ms=phone.get("MemEndTime"),
                    accuracy=_normalize_percentage(phone.get("PronAccuracy")),
                    match_type=_match_type(phone.get("MatchTag")),
                    payload={"word_index": word_index, **phone},
                )
            )
    overall_accuracy = _normalize_percentage(response.get("PronAccuracy"))
    completion = _normalize_ratio(response.get("PronCompletion"))
    confidence = min(1.0, round(0.55 + (0.25 if words else 0) + (0.2 if completion is not None else 0), 2))
    return PronunciationAssessmentResult(
        provider="tencent_soe",
        provider_version=provider_version,
        evaluation_mode=evaluation_mode,
        status="completed",
        overall_accuracy=overall_accuracy,
        fluency=_normalize_ratio(response.get("PronFluency")),
        completion=completion,
        suggested_score=_normalize_percentage(response.get("SuggestedScore")),
        confidence=confidence,
        segments=tuple(segments),
        raw_output=response,
    )


def get_pronunciation_provider() -> PronunciationAssessmentProvider:
    provider = get_settings().pronunciation_provider
    if provider == "tencent_soe":
        return TencentSoeProvider()
    return DisabledPronunciationAssessmentProvider(requested_provider=provider)
