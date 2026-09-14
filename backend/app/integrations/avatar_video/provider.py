from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from uuid import uuid4

from app.core.config import get_settings
from app.core.redaction import provider_error_summary


class AvatarVideoProviderError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class AvatarVideoProvider:
    name = "base"

    def cache_identity(self) -> str:
        return self.name

    def generate(self, image_path: Path, audio_path: Path, output_dir: Path) -> Path:
        raise NotImplementedError


class MockAvatarVideoProvider(AvatarVideoProvider):
    """A deterministic non-empty placeholder used only for queue tests and demos."""

    name = "mock"

    def generate(self, image_path: Path, audio_path: Path, output_dir: Path) -> Path:
        if not image_path.is_file() or not audio_path.is_file():
            raise AvatarVideoProviderError("input_missing", "数字人视频的头像或音频文件不存在。")
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"mock_avatar_{uuid4().hex}.mp4"
        # This is intentionally a test-only placeholder. The UI falls back to WAV if a
        # browser cannot decode it; production uses the SadTalker provider.
        output_path.write_bytes(b"\x00\x00\x00\x18ftypisom\x00\x00\x02\x00isomiso2avc1mp41")
        return output_path


class SadTalkerAvatarVideoProvider(AvatarVideoProvider):
    name = "sadtalker"

    def __init__(self) -> None:
        settings = get_settings()
        self.home = Path(settings.sadtalker_home) if settings.sadtalker_home else None
        self.python = settings.sadtalker_python or "python"
        self.ffmpeg_bin = settings.ffmpeg_bin or "ffmpeg"
        self.timeout_seconds = settings.sadtalker_timeout_seconds
        self.preprocess = settings.sadtalker_preprocess
        self.face_size = settings.sadtalker_face_size
        self.use_enhancer = settings.sadtalker_use_enhancer

    def cache_identity(self) -> str:
        return f"{self.name}|{self.preprocess}|{self.face_size}|enhancer={self.use_enhancer}"

    def generate(self, image_path: Path, audio_path: Path, output_dir: Path) -> Path:
        if not self.home or not (self.home / "inference.py").is_file():
            raise AvatarVideoProviderError("config_missing", "SadTalker 运行目录未配置或缺少 inference.py。")
        if not image_path.is_file() or not audio_path.is_file():
            raise AvatarVideoProviderError("input_missing", "数字人视频的头像或音频文件不存在。")
        output_dir.mkdir(parents=True, exist_ok=True)
        # OpenCV used by SadTalker cannot reliably open Unicode paths on Windows.
        # Stage both inputs and every intermediate result under an ASCII temp path.
        with tempfile.TemporaryDirectory(prefix="sadtalker-") as temp_dir:
            runtime_dir = Path(temp_dir)
            staged_image = runtime_dir / f"source{image_path.suffix.lower() or '.jpg'}"
            staged_audio = runtime_dir / f"audio{audio_path.suffix.lower() or '.wav'}"
            result_dir = runtime_dir / "results"
            shutil.copy2(image_path, staged_image)
            shutil.copy2(audio_path, staged_audio)
            command = [
                self.python,
                str(self.home / "inference.py"),
                "--source_image",
                str(staged_image),
                "--driven_audio",
                str(staged_audio),
                "--result_dir",
                str(result_dir),
                "--preprocess",
                self.preprocess,
                "--size",
                str(self.face_size),
            ]
            if self.use_enhancer:
                command.extend(["--enhancer", "gfpgan"])
            runtime_environment = os.environ.copy()
            ffmpeg_path = Path(self.ffmpeg_bin)
            if ffmpeg_path.is_file():
                runtime_environment["PATH"] = (
                    f"{ffmpeg_path.parent}{os.pathsep}{runtime_environment.get('PATH', '')}"
                )
            try:
                result = subprocess.run(
                    command,
                    cwd=str(self.home),
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    env=runtime_environment,
                    timeout=self.timeout_seconds,
                    check=False,
                )
            except subprocess.TimeoutExpired as exc:
                raise AvatarVideoProviderError("timeout", "动态形象生成超时，已保留音频示范。") from exc
            except OSError as exc:
                raise AvatarVideoProviderError("runtime_unavailable", "SadTalker 运行环境无法启动。") from exc
            if result.returncode != 0:
                detail = result.stderr or result.stdout or "unknown error"
                raise AvatarVideoProviderError("generation_failed", provider_error_summary("SadTalker 生成失败", RuntimeError(detail)))
            videos = sorted(result_dir.rglob("*.mp4"), key=lambda path: path.stat().st_mtime, reverse=True)
            if not videos or videos[0].stat().st_size == 0:
                raise AvatarVideoProviderError("empty_result", "SadTalker 未生成有效视频。")
            normalized = self._normalize_for_browser(videos[0], result_dir)
            final_path = output_dir / f"sadtalker_{uuid4().hex}.mp4"
            shutil.copy2(normalized, final_path)
            return final_path

    def _normalize_for_browser(self, source: Path, output_dir: Path) -> Path:
        """Make the result reliably playable by Chromium/Safari before it is stored."""
        normalized = output_dir / f"{source.stem}_web.mp4"
        # The bundled FFmpeg on some Windows devices omits libx264. Every option
        # below still creates baseline H.264/yuv420p, so Chromium can play it.
        for video_codec in ("libx264", "h264_nvenc", "h264_mf"):
            normalized.unlink(missing_ok=True)
            command = [
                self.ffmpeg_bin,
                "-y",
                "-i",
                str(source),
                "-map",
                "0:v:0",
                "-map",
                "0:a?",
                "-c:v",
                video_codec,
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac",
                "-movflags",
                "+faststart",
                str(normalized),
            ]
            try:
                result = subprocess.run(
                    command,
                    cwd=str(self.home),
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=max(30, self.timeout_seconds // 2),
                    check=False,
                )
            except (OSError, subprocess.TimeoutExpired) as exc:
                raise AvatarVideoProviderError("normalize_unavailable", "生成的视频无法转为浏览器兼容格式。") from exc
            if result.returncode == 0 and normalized.is_file() and normalized.stat().st_size > 0:
                return normalized
        raise AvatarVideoProviderError("normalize_failed", "生成的视频转码失败，未保存不兼容文件。")


def get_avatar_video_provider() -> AvatarVideoProvider:
    provider = get_settings().avatar_video_provider
    if provider == "mock":
        return MockAvatarVideoProvider()
    if provider == "sadtalker":
        return SadTalkerAvatarVideoProvider()
    if provider == "disabled":
        raise AvatarVideoProviderError("disabled", "动态形象生成功能尚未启用。")
    raise AvatarVideoProviderError("unknown_provider", f"不支持的动态形象 Provider：{provider}")
