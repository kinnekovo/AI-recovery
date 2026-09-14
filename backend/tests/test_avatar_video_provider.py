import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from app.integrations.avatar_video.provider import (
    AvatarVideoProviderError,
    MockAvatarVideoProvider,
    SadTalkerAvatarVideoProvider,
    get_avatar_video_provider,
)
from app.modules.avatar_videos.service import avatar_video_cache_key


def settings(**overrides):
    values = {
        "avatar_video_provider": "mock",
        "sadtalker_home": None,
        "sadtalker_python": None,
        "sadtalker_timeout_seconds": 180,
        "sadtalker_preprocess": "crop",
        "sadtalker_face_size": 512,
        "sadtalker_use_enhancer": False,
        "ffmpeg_bin": "ffmpeg",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


class AvatarVideoProviderTest(unittest.TestCase):
    def test_mock_provider_requires_inputs_and_writes_mp4_placeholder(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            image = root / "portrait.jpg"
            audio = root / "speech.wav"
            image.write_bytes(b"image")
            audio.write_bytes(b"audio")
            output = MockAvatarVideoProvider().generate(image, audio, root / "output")
            self.assertTrue(output.is_file())
            self.assertEqual(output.suffix, ".mp4")
            self.assertGreater(output.stat().st_size, 12)
            with self.assertRaises(AvatarVideoProviderError) as context:
                MockAvatarVideoProvider().generate(root / "missing.jpg", audio, root / "missing-output")
            self.assertEqual(context.exception.code, "input_missing")

    def test_factory_uses_mock_and_rejects_unknown_provider(self) -> None:
        with patch("app.integrations.avatar_video.provider.get_settings", return_value=settings()):
            self.assertIsInstance(get_avatar_video_provider(), MockAvatarVideoProvider)
        with patch("app.integrations.avatar_video.provider.get_settings", return_value=settings(avatar_video_provider="unknown")):
            with self.assertRaises(AvatarVideoProviderError) as context:
                get_avatar_video_provider()
        self.assertEqual(context.exception.code, "unknown_provider")

    def test_cache_key_is_stable_and_changes_when_avatar_or_audio_changes(self) -> None:
        now = datetime.now(timezone.utc)
        avatar = SimpleNamespace(id=uuid4(), updated_at=now)
        agent = SimpleNamespace(avatar_file_id=avatar.id, avatar_file=avatar)
        audio = SimpleNamespace(id=uuid4())
        first = avatar_video_cache_key(agent, audio, "mock")
        second = avatar_video_cache_key(agent, audio, "mock")
        changed_audio = avatar_video_cache_key(agent, SimpleNamespace(id=uuid4()), "mock")
        changed_provider = avatar_video_cache_key(agent, audio, "sadtalker|crop|512|enhancer=False")
        self.assertEqual(first, second)
        self.assertNotEqual(first, changed_audio)
        self.assertNotEqual(first, changed_provider)
        self.assertEqual(len(first), 64)

    def test_sadtalker_normalizes_video_to_browser_mp4(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source.mp4"
            source.write_bytes(b"source")
            with patch("app.integrations.avatar_video.provider.get_settings", return_value=settings(sadtalker_home=str(root))):
                provider = SadTalkerAvatarVideoProvider()
            def fake_run(command, **_kwargs):
                Path(command[-1]).write_bytes(b"browser-mp4")
                return SimpleNamespace(returncode=0, stderr="", stdout="")
            with patch("app.integrations.avatar_video.provider.subprocess.run", side_effect=fake_run):
                output = provider._normalize_for_browser(source, root)
            self.assertEqual(output.name, "source_web.mp4")
            self.assertEqual(output.read_bytes(), b"browser-mp4")

    def test_sadtalker_normalization_falls_back_when_ffmpeg_lacks_libx264(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source.mp4"
            source.write_bytes(b"source")
            with patch("app.integrations.avatar_video.provider.get_settings", return_value=settings(sadtalker_home=str(root))):
                provider = SadTalkerAvatarVideoProvider()
            calls: list[list[str]] = []

            def fake_run(command, **_kwargs):
                calls.append(command)
                if command[command.index("-c:v") + 1] == "h264_nvenc":
                    Path(command[-1]).write_bytes(b"browser-mp4")
                    return SimpleNamespace(returncode=0, stderr="", stdout="")
                return SimpleNamespace(returncode=1, stderr="encoder unavailable", stdout="")

            with patch("app.integrations.avatar_video.provider.subprocess.run", side_effect=fake_run):
                output = provider._normalize_for_browser(source, root)
            self.assertEqual(output.read_bytes(), b"browser-mp4")
            self.assertEqual([call[call.index("-c:v") + 1] for call in calls], ["libx264", "h264_nvenc"])


if __name__ == "__main__":
    unittest.main()
