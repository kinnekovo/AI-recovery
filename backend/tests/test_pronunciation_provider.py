import os
import sys
import tempfile
import unittest
from pathlib import Path
from subprocess import CompletedProcess
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse
from unittest.mock import patch

from app.core.config import get_settings
from app.integrations.pronunciation_assessment.provider import (
    PronunciationProviderError,
    TencentSoeProvider,
    get_pronunciation_provider,
    parse_tencent_soe_response,
)


class PronunciationProviderTest(unittest.TestCase):
    def tearDown(self) -> None:
        for key in ("PRONUNCIATION_PROVIDER", "TENCENTCLOUD_SECRET_ID", "TENCENTCLOUD_SECRET_KEY", "TENCENT_SOE_APP_ID", "TENCENT_SOE_ENGINE_TYPE"):
            os.environ.pop(key, None)
        get_settings.cache_clear()

    def test_disabled_provider_never_generates_a_mock_score(self) -> None:
        os.environ["PRONUNCIATION_PROVIDER"] = "disabled"
        get_settings.cache_clear()
        result = get_pronunciation_provider().evaluate("unused.wav", "今天天气很好", "sentence")
        self.assertEqual(result.status, "unavailable")
        self.assertIsNone(result.overall_accuracy)
        self.assertEqual(result.error_code, "provider_disabled")

    def test_parser_preserves_word_phone_and_tone_evidence(self) -> None:
        result = parse_tencent_soe_response(
            {
                "Response": {
                    "PronAccuracy": 0.91,
                    "PronFluency": 86,
                    "PronCompletion": 0.95,
                    "SuggestedScore": 90,
                    "Words": [
                        {
                            "ReferenceWord": "好",
                            "Word": "号",
                            "MemBeginTime": 120,
                            "MemEndTime": 390,
                            "PronAccuracy": 72,
                            "PronFluency": 0.8,
                            "MatchTag": 3,
                            "Tone": {"Valid": True, "RefTone": 3, "Tone": 2},
                            "PhoneInfos": [{"ReferencePhone": "hao", "Phone": "hao", "PronAccuracy": 0.8, "MatchTag": 0}],
                        }
                    ],
                }
            },
            "sentence",
        )
        self.assertEqual(result.overall_accuracy, 91.0)
        self.assertEqual(result.fluency, 0.86)
        self.assertEqual(result.completion, 0.95)
        self.assertEqual(result.segments[0].match_type, "substitution")
        self.assertFalse(result.segments[0].tone_correct)
        self.assertEqual(result.segments[1].level, "phoneme")

    def test_tencent_soe_transcodes_browser_audio_before_request(self) -> None:
        os.environ["TENCENTCLOUD_SECRET_ID"] = "id"
        os.environ["TENCENTCLOUD_SECRET_KEY"] = "key"
        os.environ["TENCENT_SOE_APP_ID"] = "123456"
        get_settings.cache_clear()
        with tempfile.NamedTemporaryFile(suffix=".webm") as audio:
            audio.write(b"webm-placeholder")
            audio.flush()

            def fake_transcode(command, check, capture_output):
                Path(command[-1]).write_bytes(b"RIFF-wav-placeholder")
                return CompletedProcess(command, 0)

            provider = TencentSoeProvider()
            with patch("app.integrations.pronunciation_assessment.provider.subprocess.run", side_effect=fake_transcode) as run:
                prepared = provider._prepare_wav(audio.name)
            try:
                self.assertEqual(prepared.read_bytes()[:4], b"RIFF")
                command = run.call_args.args[0]
                self.assertIn("16000", command)
                self.assertIn("pcm_s16le", command)
            finally:
                prepared.unlink(missing_ok=True)

    def test_tencent_provider_requires_credentials(self) -> None:
        os.environ["TENCENTCLOUD_SECRET_ID"] = ""
        os.environ["TENCENTCLOUD_SECRET_KEY"] = ""
        get_settings.cache_clear()
        with self.assertRaises(PronunciationProviderError) as raised:
            TencentSoeProvider().evaluate("missing.wav", "测试", "sentence")
        self.assertEqual(raised.exception.code, "config_missing")

    def test_parser_rejects_a_response_without_evaluation_fields(self) -> None:
        with self.assertRaises(PronunciationProviderError) as raised:
            parse_tencent_soe_response({"Response": {"RequestId": "only-request-id"}}, "sentence")
        self.assertEqual(raised.exception.code, "bad_response")

    def test_tencent_soe_new_version_sends_a_wav_recording_without_network(self) -> None:
        os.environ["TENCENTCLOUD_SECRET_ID"] = "id"
        os.environ["TENCENTCLOUD_SECRET_KEY"] = "key"
        os.environ["TENCENT_SOE_APP_ID"] = "123456"
        get_settings.cache_clear()
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as audio:
            audio.write(b"RIFF-test-wav")
            audio_path = audio.name

        class FakeWebSocketApp:
            def __init__(self, _url, on_open, on_message, on_error, on_close):
                self.sent = None
                self.closed = False
                self.events = []
                self.on_open = on_open
                self.on_message = on_message
                self.on_error = on_error
                self.on_close = on_close
                self.sock = SimpleNamespace(send_binary=self.send_binary, send=self.send)

            def run_forever(self):
                self.events.append("open")
                self.on_open(self)

            def send_binary(self, payload):
                self.events.append("send")
                self.sent = payload
                self.events.append("message")
                self.on_message(
                    self,
                    '{"code":0,"final":1,"result":{"PronAccuracy":88,"PronFluency":80,"PronCompletion":100,"SuggestedScore":86,"Words":[]}}',
                )

            def send(self, payload):
                self.events.append("end")
                self.end_frame = payload

            def close(self):
                self.closed = True

        connections = []
        websocket = SimpleNamespace(
            WebSocketApp=lambda *args, **kwargs: connections.append(FakeWebSocketApp(*args, **kwargs)) or connections[-1],
        )
        try:
            with patch("app.integrations.pronunciation_assessment.provider.TencentSoeProvider._prepare_wav", return_value=Path(audio_path)):
                with patch.dict(sys.modules, {"websocket": websocket}):
                    result = TencentSoeProvider().evaluate(audio_path, "今天天气很好", "sentence")
            connection = connections[0]
            self.assertEqual(result.status, "completed")
            self.assertEqual(result.provider_version, "soe-new-wss-v1")
            self.assertEqual(connection.sent, b"RIFF-test-wav")
            self.assertEqual(connection.end_frame, '{"type": "end"}')
            self.assertEqual(connection.events, ["open", "send", "message", "end"])
            self.assertTrue(connection.closed)
        finally:
            Path(audio_path).unlink(missing_ok=True)

    def test_tencent_soe_new_version_signs_a_recording_request(self) -> None:
        os.environ["TENCENTCLOUD_SECRET_ID"] = "id"
        os.environ["TENCENTCLOUD_SECRET_KEY"] = "key"
        os.environ["TENCENT_SOE_APP_ID"] = "123456"
        get_settings.cache_clear()
        with patch("app.integrations.pronunciation_assessment.provider.time.time", return_value=1_700_000_000):
            with patch("app.integrations.pronunciation_assessment.provider.random.randint", return_value=7):
                url = TencentSoeProvider()._build_websocket_url("今天很好", 1)
        parsed = urlparse(url)
        query = parse_qs(parsed.query)
        self.assertEqual(parsed.path, "/soe/api/123456")
        self.assertEqual(query["server_engine_type"], ["16k_zh"])
        self.assertEqual(query["rec_mode"], ["1"])
        self.assertEqual(query["voice_format"], ["1"])
        self.assertEqual(query["ref_text"], ["今天很好"])
        self.assertIn("signature", query)


if __name__ == "__main__":
    unittest.main()
