import math
import subprocess

from app.core.config import get_settings

try:
    import numpy as np
except ImportError:  # pragma: no cover
    np = None


def analyze_prosody(audio_path: str) -> dict:
    if np is None:
        return {"status": "unavailable", "reason": "numpy_missing"}
    settings = get_settings()
    ffmpeg = settings.ffmpeg_bin
    if not ffmpeg:
        try:
            import imageio_ffmpeg

            ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        except ImportError:
            return {"status": "unavailable", "reason": "ffmpeg_missing"}
    try:
        completed = subprocess.run(
            [ffmpeg, "-hide_banner", "-loglevel", "error", "-i", audio_path, "-vn", "-ac", "1", "-ar", "16000", "-f", "s16le", "pipe:1"],
            check=True,
            capture_output=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return {"status": "unavailable", "reason": "decode_failed"}
    samples = np.frombuffer(completed.stdout, dtype=np.int16).astype(np.float32) / 32768.0
    if samples.size < 16000:
        return {"status": "unavailable", "reason": "too_short"}
    frame_size, hop = 640, 320
    frames = [samples[start : start + frame_size] for start in range(0, samples.size - frame_size + 1, hop)]
    if not frames:
        return {"status": "unavailable", "reason": "too_short"}
    rms = np.array([math.sqrt(float(np.mean(np.square(frame)))) for frame in frames])
    dbfs = 20 * np.log10(np.maximum(rms, 1e-9))
    voiced = dbfs > settings.acoustic_voice_threshold_dbfs
    pause_metrics = _pause_and_rhythm_metrics(voiced, hop / 16000)
    f0_values = [_estimate_f0(frame, 16000) for frame, active in zip(frames, voiced) if active]
    f0_values = np.array([item for item in f0_values if item is not None])
    if f0_values.size < 3:
        return {
            "status": "unavailable",
            "reason": "insufficient_voiced_frames",
            "f0_median_hz": None,
            "f0_p10_hz": None,
            "f0_p90_hz": None,
            "pitch_range_semitones": None,
            "pitch_variability": None,
            "voiced_ratio": round(float(np.mean(voiced)), 3),
            **pause_metrics,
        }
    pitch_range = 12 * math.log2(float(np.percentile(f0_values, 90)) / float(np.percentile(f0_values, 10)))
    return {
        "status": "completed",
        "f0_median_hz": round(float(np.median(f0_values)), 2),
        "f0_p10_hz": round(float(np.percentile(f0_values, 10)), 2),
        "f0_p90_hz": round(float(np.percentile(f0_values, 90)), 2),
        "pitch_range_semitones": round(pitch_range, 2),
        "pitch_variability": round(float(np.std(f0_values)), 2),
        "voiced_ratio": round(float(np.mean(voiced)), 3),
        "loudness_mean_dbfs": round(float(np.mean(dbfs[voiced])), 2),
        "loudness_std_db": round(float(np.std(dbfs[voiced])), 2),
        "frame_count": len(frames),
        "total_duration_seconds": round(samples.size / 16000, 3),
        **pause_metrics,
    }


def _estimate_f0(frame, sample_rate: int) -> float | None:
    centered = frame - np.mean(frame)
    if float(np.max(np.abs(centered))) < 0.01:
        return None
    correlation = np.correlate(centered, centered, mode="full")[len(centered) - 1 :]
    minimum_lag, maximum_lag = int(sample_rate / 350), int(sample_rate / 70)
    window = correlation[minimum_lag:maximum_lag]
    if window.size == 0:
        return None
    lag = minimum_lag + int(np.argmax(window))
    if correlation[lag] < correlation[0] * 0.2:
        return None
    return round(sample_rate / lag, 2)


def _pause_and_rhythm_metrics(voiced, frame_seconds: float) -> dict:
    runs: list[tuple[bool, int]] = []
    for active in voiced:
        if runs and runs[-1][0] == bool(active):
            runs[-1] = (runs[-1][0], runs[-1][1] + 1)
        else:
            runs.append((bool(active), 1))
    voiced_durations = [count * frame_seconds for active, count in runs if active]
    internal_pauses = [
        count * frame_seconds
        for index, (active, count) in enumerate(runs)
        if not active and 0 < index < len(runs) - 1
    ]
    leading_silence = runs[0][1] * frame_seconds if runs and not runs[0][0] else 0.0
    final_pause = runs[-1][1] * frame_seconds if runs and not runs[-1][0] else 0.0
    speech_duration = sum(voiced_durations)
    pause_duration = sum(internal_pauses)
    intervals = np.array(voiced_durations, dtype=float) if np is not None else []
    rhythm_cv = float(np.std(intervals) / np.mean(intervals)) if len(intervals) >= 2 and np.mean(intervals) > 0 else None
    return {
        "speech_duration_seconds": round(speech_duration, 3),
        "internal_pause_seconds": round(pause_duration, 3),
        "pause_ratio": round(pause_duration / (speech_duration + pause_duration), 3) if speech_duration + pause_duration else 0.0,
        "pause_count": len(internal_pauses),
        "longest_pause_seconds": round(max(internal_pauses, default=0.0), 3),
        "leading_silence_seconds": round(leading_silence, 3),
        "sentence_final_pause_seconds": round(final_pause, 3),
        "rhythm_interval_cv": round(rhythm_cv, 3) if rhythm_cv is not None else None,
    }
