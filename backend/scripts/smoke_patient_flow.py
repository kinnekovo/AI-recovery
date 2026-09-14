from __future__ import annotations

from io import BytesIO
from pathlib import Path
import base64
import math
import os
import sys
import tempfile
from unittest.mock import patch
import uuid
import wave

sys.path.append(str(Path(__file__).resolve().parents[1]))

os.environ["STORAGE_ROOT"] = str(Path(tempfile.gettempdir()) / "speech_rehab_smoke_storage")
os.environ["SPEECH_EVAL_PROVIDER"] = "mock"
os.environ["ASR_PROVIDER"] = "mock"
os.environ["ACOUSTIC_PROVIDER"] = "mock"
os.environ["TTS_PROVIDER"] = "mock"
os.environ["LLM_FEEDBACK_PROVIDER"] = "mock"

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import get_settings
from app.integrations.acoustic_analysis.provider import AcousticAnalysisResult
from app.integrations.asr.provider import ASRTranscriptionResult
from app.main import create_app


PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="
)


def main() -> int:
    if not database_available():
        return 1
    client = TestClient(create_app())
    username = f"smoke_patient_{uuid.uuid4().hex[:10]}"
    password = "smoke123456"

    post(client, "/api/auth/register", json={"username": username, "password": password, "role": "patient"})
    login = post(client, "/api/auth/login", json={"username": username, "password": password})
    token = login["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    expect_error(
        client,
        "post",
        "/api/training/avatar-speech",
        400,
        headers=headers,
        json={"scene": "task_demo", "text": "请跟我说这一句：今天天气很好。"},
    )

    agent = post(
        client,
        "/api/agents",
        headers=headers,
        json={
            "name": "陪练",
            "relationship": "家人",
            "personality_style": "温柔鼓励",
            "image_consent_confirmed": True,
            "voice_consent_confirmed": True,
        },
    )
    agent_id = agent["id"]
    agent_with_avatar = upload(
        client,
        f"/api/agents/{agent_id}/avatar",
        headers=headers,
        field="avatar_file",
        filename="avatar.png",
        content=PNG_1X1,
        content_type="image/png",
    )
    assert agent_with_avatar["avatar_url"].startswith("/api/files/")
    avatar_file = client.get(agent_with_avatar["avatar_url"], headers=headers)
    assert avatar_file.status_code == 200
    assert avatar_file.content
    upload(
        client,
        f"/api/agents/{agent_id}/voice",
        headers=headers,
        field="audio_file",
        filename="voice.wav",
        content=wav_bytes(),
        content_type="audio/wav",
    )
    welcome = post(client, f"/api/agents/{agent_id}/welcome-audio", headers=headers)
    assert welcome["audio_url"].startswith("/api/files/")
    intro_speech = post(
        client,
        "/api/training/avatar-speech",
        headers=headers,
        json={"scene": "training_intro", "text": "今天我们从简单的小任务开始，我会先说明，再陪你练习。"},
    )
    assert intro_speech["audio_url"].startswith("/api/files/")
    assert intro_speech["provider"] == "mock"

    recommendation = get(client, "/api/training/recommendation", headers=headers)
    task_ids = [item["id"] for item in recommendation.get("task_sequence", [])]
    session = post(
        client,
        "/api/training/session",
        headers=headers,
        json={
            "type": recommendation["recommended_type"],
            "recommendation_source": recommendation["source"],
            "recommendation_headline": recommendation["headline"],
            "recommendation_task_ids": task_ids,
        },
    )
    assert session["session_tasks"], "training session should contain at least one task"
    session_task_id = session["session_tasks"][0]["id"]

    speech = post(
        client,
        "/api/training/avatar-speech",
        headers=headers,
        json={
            "scene": "task_demo",
            "session_id": session["id"],
            "session_task_id": session_task_id,
            "text": "请跟我说这一句：今天天气很好。",
        },
    )
    assert speech["audio_url"].startswith("/api/files/")
    assert speech["provider"] == "mock"

    expect_error(
        client,
        "post",
        "/api/training/avatar-speech",
        400,
        headers=headers,
        json={"scene": "task_demo", "text": ""},
    )
    expect_error(
        client,
        "post",
        "/api/training/avatar-speech",
        400,
        headers=headers,
        json={"scene": "task_demo", "text": "慢慢来。" * 60},
    )
    expect_error(
        client,
        "post",
        "/api/training/avatar-speech",
        404,
        headers=headers,
        json={"scene": "task_demo", "session_task_id": str(uuid.uuid4()), "text": "请跟我说这一句：今天天气很好。"},
    )

    attempt = post(client, "/api/attempts", headers=headers, json={"session_task_id": session_task_id})
    upload(
        client,
        f"/api/attempts/{attempt['id']}/audio",
        headers=headers,
        field="audio_file",
        filename="attempt.wav",
        content=wav_bytes(),
        content_type="audio/wav",
    )
    expect_error(client, "post", f"/api/attempts/{attempt['id']}/analyze", 422, headers=headers)
    failed_attempt = get(client, f"/api/attempts/{attempt['id']}", headers=headers)
    assert failed_attempt["analysis_status"] == "failed"
    assert failed_attempt["analysis_error_code"] in {"acoustic:mock_provider", "asr:mock_provider"}
    reset_attempt = upload(
        client,
        f"/api/attempts/{attempt['id']}/audio",
        headers=headers,
        field="audio_file",
        filename="attempt-retry.wav",
        content=wav_bytes(),
        content_type="audio/wav",
    )
    assert reset_attempt["analysis_status"] == "pending"
    assert reset_attempt["analysis_error_code"] is None
    with patch(
        "app.modules.scoring.service.transcribe_with_fallback",
        return_value=ASRTranscriptionResult(
            text="今天天气很好",
            provider_name="tencent",
            requested_provider="tencent",
        ),
    ), patch(
        "app.modules.scoring.service.get_acoustic_analysis_provider",
        return_value=SmokeAcousticProvider(),
    ):
        feedback = post(client, f"/api/attempts/{attempt['id']}/analyze", headers=headers)
    assert feedback["process_metrics"]["script_accuracy"] >= 0
    assert feedback["feedback"], "analysis should return patient feedback"

    report = get(client, "/api/reports/latest", headers=headers)
    assert report["training_count"] >= 1
    print(f"patient smoke flow ok: {username}")
    return 0


def database_available() -> bool:
    try:
        engine = create_engine(get_settings().effective_database_url, pool_pre_ping=True)
        with engine.connect() as connection:
            connection.execute(text("select 1"))
    except SQLAlchemyError as exc:
        print(f"database unavailable: {exc.__class__.__name__}")
        return False
    return True


def get(client: TestClient, path: str, **kwargs):
    return unwrap(client.get(path, **kwargs))


def post(client: TestClient, path: str, **kwargs):
    return unwrap(client.post(path, **kwargs))


def upload(
    client: TestClient,
    path: str,
    *,
    headers: dict[str, str],
    field: str,
    filename: str,
    content: bytes,
    content_type: str,
):
    return unwrap(client.post(path, headers=headers, files={field: (filename, BytesIO(content), content_type)}))


def expect_error(client: TestClient, method: str, path: str, status_code: int, **kwargs) -> None:
    response = getattr(client, method)(path, **kwargs)
    if response.status_code != status_code:
        raise AssertionError(f"{method.upper()} {path} expected {status_code}, got {response.status_code}: {response.text}")


def unwrap(response):
    if response.status_code >= 400:
        raise AssertionError(f"{response.request.method} {response.request.url.path} failed: {response.status_code} {response.text}")
    payload = response.json()
    if payload.get("code") != 0:
        raise AssertionError(f"{response.request.method} {response.request.url.path} failed: {payload}")
    return payload["data"]


def wav_bytes() -> bytes:
    output = BytesIO()
    sample_rate = 16000
    frames = int(sample_rate * 1.2)
    with wave.open(output, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        for index in range(frames):
            value = int(12000 * math.sin(2 * math.pi * 440 * index / sample_rate))
            wav.writeframesraw(value.to_bytes(2, byteorder="little", signed=True))
    return output.getvalue()


class SmokeAcousticProvider:
    provider_name = "local"

    def analyze(self, audio_path: str) -> AcousticAnalysisResult:
        return AcousticAnalysisResult(
            speaking_duration_seconds=1.2,
            loudness_dba=66.0,
            long_pause_over_3s_count=0,
            total_duration_seconds=1.2,
            loudness_dbfs=-24.0,
            snr_db=24.0,
            quality_status="pass",
            quality_reason="normal",
        )


if __name__ == "__main__":
    raise SystemExit(main())
