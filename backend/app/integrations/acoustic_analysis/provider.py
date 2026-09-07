from dataclasses import dataclass
import math
import subprocess

from app.core.config import get_settings

try:
    import numpy as np
except ImportError:  # pragma: no cover - exercised when local provider is used without dependency install.
    np = None


@dataclass(frozen=True)
class AcousticAnalysisResult:
    speaking_duration_seconds: float
    loudness_dba: float
    long_pause_over_3s_count: int
    quality_status: str = "pass"
    quality_reason: str = "normal"
    too_short: bool = False
    too_quiet: bool = False


class AcousticAnalysisProvider:
    provider_name = "base"

    def analyze(self, audio_path: str) -> AcousticAnalysisResult:
        raise NotImplementedError


class MockAcousticAnalysisProvider(AcousticAnalysisProvider):
    provider_name = "mock"

    def __init__(self, requested_provider: str = "mock") -> None:
        self.requested_provider = requested_provider

    def analyze(self, audio_path: str) -> AcousticAnalysisResult:
        return AcousticAnalysisResult(
            speaking_duration_seconds=3.8,
            loudness_dba=65.0,
            long_pause_over_3s_count=1,
            quality_status="pass",
            quality_reason="mock_pass",
        )


class LocalAcousticAnalysisProvider(AcousticAnalysisProvider):
    provider_name = "local"
    sample_rate = 16000
    frame_duration_seconds = 0.03

    def __init__(self) -> None:
        settings = get_settings()
        self.ffmpeg_bin = settings.ffmpeg_bin or self._bundled_ffmpeg_bin()
        self.dba_calibration_offset = settings.acoustic_dba_calibration_offset
        self.voice_threshold_dbfs = settings.acoustic_voice_threshold_dbfs

    def analyze(self, audio_path: str) -> AcousticAnalysisResult:
        if np is None:
            raise RuntimeError("缺少 numpy，无法执行本地声学分析，请先安装 backend requirements。")
        if not self.ffmpeg_bin:
            raise RuntimeError("未找到 ffmpeg，请安装 imageio-ffmpeg 或设置 FFMPEG_BIN。")

        samples = self._decode_audio(audio_path)
        if samples.size == 0:
            return AcousticAnalysisResult(
                speaking_duration_seconds=0.0,
                loudness_dba=0.0,
                long_pause_over_3s_count=0,
                quality_status="unusable",
                quality_reason="empty_audio",
                too_short=True,
                too_quiet=True,
            )

        frame_size = max(int(self.sample_rate * self.frame_duration_seconds), 1)
        frame_count = samples.size // frame_size
        if frame_count == 0:
            return self._short_audio_result(samples)

        framed = samples[: frame_count * frame_size].reshape(frame_count, frame_size)
        rms = np.sqrt(np.mean(np.square(framed), axis=1))
        dbfs = 20 * np.log10(np.maximum(rms, 1e-9))
        voiced = dbfs > self.voice_threshold_dbfs
        voiced_frames = int(np.count_nonzero(voiced))
        speaking_duration = round(voiced_frames * self.frame_duration_seconds, 2)
        framed_samples = samples[: frame_count * frame_size]
        active_samples = framed_samples[np.repeat(voiced, frame_size)]
        loudness = self._estimate_loudness(active_samples if active_samples.size else samples)

        return AcousticAnalysisResult(
            speaking_duration_seconds=speaking_duration,
            loudness_dba=loudness,
            long_pause_over_3s_count=self._count_long_pauses(voiced),
            **self._quality_fields(speaking_duration, loudness),
        )

    def _decode_audio(self, audio_path: str):
        command = [
            self.ffmpeg_bin,
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            audio_path,
            "-vn",
            "-ac",
            "1",
            "-ar",
            str(self.sample_rate),
            "-f",
            "s16le",
            "pipe:1",
        ]
        try:
            completed = subprocess.run(command, check=True, capture_output=True)
        except (OSError, subprocess.CalledProcessError) as exc:
            raise RuntimeError("音频解码失败，请确认录音格式可被 ffmpeg 读取。") from exc
        pcm = np.frombuffer(completed.stdout, dtype=np.int16)
        return pcm.astype(np.float32) / 32768.0

    def _short_audio_result(self, samples) -> AcousticAnalysisResult:
        duration = round(samples.size / self.sample_rate, 2)
        return AcousticAnalysisResult(
            speaking_duration_seconds=duration,
            loudness_dba=self._estimate_loudness(samples),
            long_pause_over_3s_count=0,
            **self._quality_fields(duration, self._estimate_loudness(samples)),
        )

    def _quality_fields(self, speaking_duration: float, loudness: float) -> dict:
        settings = get_settings()
        too_short = speaking_duration < settings.acoustic_min_speaking_seconds
        too_quiet = loudness < settings.acoustic_min_loudness_dba
        if too_short and too_quiet:
            return {
                "quality_status": "low_quality",
                "quality_reason": "too_short_and_quiet",
                "too_short": True,
                "too_quiet": True,
            }
        if too_short:
            return {
                "quality_status": "low_quality",
                "quality_reason": "too_short",
                "too_short": True,
                "too_quiet": False,
            }
        if too_quiet:
            return {
                "quality_status": "low_quality",
                "quality_reason": "too_quiet",
                "too_short": False,
                "too_quiet": True,
            }
        return {
            "quality_status": "pass",
            "quality_reason": "normal",
            "too_short": False,
            "too_quiet": False,
        }

    def _estimate_loudness(self, samples) -> float:
        if samples.size == 0:
            return 0.0
        rms = float(np.sqrt(np.mean(np.square(samples))))
        dbfs = 20 * math.log10(max(rms, 1e-9))
        return round(dbfs + self.dba_calibration_offset, 2)

    def _count_long_pauses(self, voiced) -> int:
        if not bool(np.any(voiced)):
            return 0
        voiced_indices = np.flatnonzero(voiced)
        first_voiced = int(voiced_indices[0])
        last_voiced = int(voiced_indices[-1])
        pauses = 0
        current_silence_frames = 0
        minimum_pause_frames = math.ceil(3.0 / self.frame_duration_seconds)
        for is_voiced in voiced[first_voiced : last_voiced + 1]:
            if is_voiced:
                if current_silence_frames >= minimum_pause_frames:
                    pauses += 1
                current_silence_frames = 0
            else:
                current_silence_frames += 1
        return pauses

    def _bundled_ffmpeg_bin(self) -> str | None:
        try:
            import imageio_ffmpeg
        except ImportError:
            return None
        return imageio_ffmpeg.get_ffmpeg_exe()


def get_acoustic_analysis_provider() -> AcousticAnalysisProvider:
    settings = get_settings()
    if settings.acoustic_provider == "local":
        return LocalAcousticAnalysisProvider()
    return MockAcousticAnalysisProvider(requested_provider=settings.acoustic_provider)
