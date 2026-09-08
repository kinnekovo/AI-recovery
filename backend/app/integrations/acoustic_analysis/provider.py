from dataclasses import dataclass
import math
import subprocess

from app.core.config import get_settings

try:
    import numpy as np
except ImportError:  # pragma: no cover
    np = None


@dataclass(frozen=True)
class AcousticAnalysisResult:
    speaking_duration_seconds: float
    loudness_dba: float
    long_pause_over_3s_count: int
    total_duration_seconds: float = 0.0
    loudness_dbfs: float = -120.0
    pause_over_1s_count: int = 0
    internal_pause_duration_seconds: float = 0.0
    pause_ratio: float = 0.0
    longest_pause_seconds: float = 0.0
    clipping_ratio: float = 0.0
    snr_db: float = 0.0
    too_noisy: bool = False
    clipped: bool = False
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
            total_duration_seconds=4.8,
            loudness_dbfs=-25.0,
            pause_over_1s_count=1,
            internal_pause_duration_seconds=1.0,
            pause_ratio=0.21,
            longest_pause_seconds=1.0,
            snr_db=25.0,
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
        total_duration = round(samples.size / self.sample_rate, 2)
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
        active_samples = framed[voiced].reshape(-1) if voiced_frames else samples
        loudness_dbfs = self._estimate_loudness_dbfs(active_samples)
        loudness_dba = round(loudness_dbfs + self.dba_calibration_offset, 2)
        pause_metrics = self._pause_metrics(voiced)
        clipping_ratio = round(float(np.count_nonzero(np.abs(samples) >= 0.99)) / samples.size, 4)
        snr_db = self._estimate_snr_db(rms, voiced)

        return AcousticAnalysisResult(
            speaking_duration_seconds=speaking_duration,
            loudness_dba=loudness_dba,
            long_pause_over_3s_count=pause_metrics["pause_over_3s_count"],
            total_duration_seconds=total_duration,
            loudness_dbfs=loudness_dbfs,
            pause_over_1s_count=pause_metrics["pause_over_1s_count"],
            internal_pause_duration_seconds=pause_metrics["internal_pause_duration_seconds"],
            pause_ratio=pause_metrics["pause_ratio"],
            longest_pause_seconds=pause_metrics["longest_pause_seconds"],
            clipping_ratio=clipping_ratio,
            snr_db=snr_db,
            **self._quality_fields(speaking_duration, loudness_dba, snr_db, clipping_ratio),
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
        loudness_dbfs = self._estimate_loudness_dbfs(samples)
        loudness_dba = round(loudness_dbfs + self.dba_calibration_offset, 2)
        clipping_ratio = round(float(np.count_nonzero(np.abs(samples) >= 0.99)) / max(samples.size, 1), 4)
        return AcousticAnalysisResult(
            speaking_duration_seconds=duration,
            loudness_dba=loudness_dba,
            long_pause_over_3s_count=0,
            total_duration_seconds=duration,
            loudness_dbfs=loudness_dbfs,
            clipping_ratio=clipping_ratio,
            **self._quality_fields(duration, loudness_dba, 0.0, clipping_ratio),
        )

    def _quality_fields(self, speaking_duration: float, loudness_dba: float, snr_db: float, clipping_ratio: float) -> dict:
        settings = get_settings()
        too_short = speaking_duration < settings.acoustic_min_speaking_seconds
        too_quiet = loudness_dba < settings.acoustic_min_loudness_dba
        too_noisy = 0 < snr_db < settings.acoustic_min_snr_db
        clipped = clipping_ratio > settings.acoustic_max_clipping_ratio
        reasons = []
        if too_short:
            reasons.append("too_short")
        if too_quiet:
            reasons.append("too_quiet")
        if too_noisy:
            reasons.append("too_noisy")
        if clipped:
            reasons.append("clipped")
        return {
            "quality_status": "unusable" if speaking_duration < 0.3 else "low_quality" if reasons else "pass",
            "quality_reason": "_and_".join(reasons) if reasons else "normal",
            "too_short": too_short,
            "too_quiet": too_quiet,
            "too_noisy": too_noisy,
            "clipped": clipped,
        }

    @staticmethod
    def _estimate_loudness_dbfs(samples) -> float:
        if samples.size == 0:
            return -120.0
        rms = float(np.sqrt(np.mean(np.square(samples))))
        return round(20 * math.log10(max(rms, 1e-9)), 2)

    def _pause_metrics(self, voiced) -> dict[str, float | int]:
        if not bool(np.any(voiced)):
            return {
                "pause_over_1s_count": 0,
                "pause_over_3s_count": 0,
                "internal_pause_duration_seconds": 0.0,
                "pause_ratio": 0.0,
                "longest_pause_seconds": 0.0,
            }
        voiced_indices = np.flatnonzero(voiced)
        first_voiced = int(voiced_indices[0])
        last_voiced = int(voiced_indices[-1])
        silence_runs: list[int] = []
        current_silence_frames = 0
        for is_voiced in voiced[first_voiced : last_voiced + 1]:
            if is_voiced:
                if current_silence_frames:
                    silence_runs.append(current_silence_frames)
                current_silence_frames = 0
            else:
                current_silence_frames += 1
        durations = [frames * self.frame_duration_seconds for frames in silence_runs]
        span_seconds = max((last_voiced - first_voiced + 1) * self.frame_duration_seconds, 0.1)
        total_pause = sum(durations)
        return {
            "pause_over_1s_count": sum(duration >= 1.0 for duration in durations),
            "pause_over_3s_count": sum(duration >= 3.0 for duration in durations),
            "internal_pause_duration_seconds": round(total_pause, 2),
            "pause_ratio": round(total_pause / span_seconds, 3),
            "longest_pause_seconds": round(max(durations, default=0.0), 2),
        }

    @staticmethod
    def _estimate_snr_db(frame_rms, voiced) -> float:
        if not bool(np.any(voiced)):
            return 0.0
        signal_rms = float(np.median(frame_rms[voiced]))
        noise_frames = frame_rms[~voiced]
        if noise_frames.size == 0:
            return 60.0
        noise_rms = float(np.median(noise_frames))
        return round(min(60.0, 20 * math.log10(max(signal_rms, 1e-9) / max(noise_rms, 1e-9))), 2)

    @staticmethod
    def _bundled_ffmpeg_bin() -> str | None:
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
