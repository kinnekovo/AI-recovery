import base64
import hashlib
import hmac
import json
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qs, unquote, urlparse
from uuid import uuid4

from PIL import Image

from app.integrations.tencent_avatar.provider import TencentAvatarCustomizationClient, TencentAvatarRuntime


class FakeWebSocket:
    def __init__(self) -> None:
        self.messages: list[str] = []

    def send(self, message: str) -> None:
        self.messages.append(message)


class TencentAvatarProviderTest(unittest.TestCase):
    def make_runtime(self) -> TencentAvatarRuntime:
        return TencentAvatarRuntime(
            app_key="app-key",
            access_token="access-token",
            asset_virtualman_key="asset-key",
            user_id="patient-1",
            protocol="webrtc",
            driver_type=3,
            base_url="https://gw.tvs.qq.com",
            request_timeout=30,
            ready_timeout=120,
        )

    @patch("app.integrations.tencent_avatar.provider.time.time", return_value=1700000000)
    def test_signed_url_matches_official_hmac_rule(self, _time) -> None:
        runtime = self.make_runtime()
        url = runtime._signed_url("/endpoint", {"ReqId": "request-id"})
        query = parse_qs(urlparse(url).query)
        content = "ReqId=request-id&appkey=app-key&timestamp=1700000000"
        expected = base64.b64encode(hmac.new(b"access-token", content.encode(), hashlib.sha256).digest()).decode()
        self.assertEqual(unquote(query["signature"][0]), expected)

    @patch("app.integrations.tencent_avatar.provider.time.sleep", return_value=None)
    def test_audio_is_chunked_and_finalized_like_verified_demo(self, _sleep) -> None:
        runtime = self.make_runtime()
        socket = FakeWebSocket()
        runtime.session_id = "session-id"
        runtime.ws = socket  # type: ignore[assignment]
        runtime._connected.set()

        duration = runtime.send_audio(bytes(5120 * 7 + 2))
        messages = [json.loads(item)["Payload"] for item in socket.messages]

        self.assertEqual(len(messages), 9)
        self.assertTrue(all(item["Command"] == "SEND_AUDIO" for item in messages))
        self.assertEqual([item["Data"]["Seq"] for item in messages], list(range(1, 10)))
        self.assertFalse(messages[0]["Data"]["IsFinal"])
        self.assertTrue(messages[-1]["Data"]["IsFinal"])
        self.assertEqual(messages[-1]["Data"]["Audio"], "")
        self.assertAlmostEqual(duration, (5120 * 7 + 2) / 32000)

    def test_photo_is_cropped_to_safe_square_jpeg_for_face_detection(self) -> None:
        source_path = Path(__file__).parent / f"portrait-{uuid4().hex}.png"
        try:
            Image.new("RGB", (800, 600), "#74a99a").save(source_path)
            output = TencentAvatarCustomizationClient._prepare_photo(
                str(source_path),
                {"x": 0.25, "y": 0.0, "width": 0.5, "height": 1.0},
            )
        finally:
            source_path.unlink(missing_ok=True)

        self.assertIsInstance(output, BytesIO)
        with Image.open(output) as result:
            self.assertEqual(result.format, "JPEG")
            self.assertEqual(result.size, (640, 640))

    def test_large_closeup_is_reduced_below_tencent_face_box_limit(self) -> None:
        source_path = Path(__file__).parent / f"portrait-{uuid4().hex}.jpg"
        try:
            Image.new("RGB", (2400, 2400), "#d8c2ae").save(source_path)
            output = TencentAvatarCustomizationClient._prepare_photo(str(source_path), None)
        finally:
            source_path.unlink(missing_ok=True)

        with Image.open(output) as result:
            self.assertEqual(result.size, (640, 640))

    def test_anchor_name_only_uses_tencent_supported_characters(self) -> None:
        cleaned = TencentAvatarCustomizationClient._safe_anchor_name(" 妈妈 / 测试（1） ")

        self.assertEqual(cleaned, "妈妈___测试_1")
        self.assertGreaterEqual(len(cleaned), 2)
        self.assertLessEqual(len(cleaned), 50)

    def test_photo_filename_stays_within_tencent_limit(self) -> None:
        filename = TencentAvatarCustomizationClient._new_photo_filename()

        self.assertLessEqual(len(filename), 20)
        self.assertRegex(filename, r"^[A-Za-z0-9_-]+\.jpg$")


if __name__ == "__main__":
    unittest.main()
