"""Validate the standalone SadTalker runtime before enabling the production worker.

The dry check is safe to run repeatedly. Add --image and --audio to perform the
official CLI smoke test and verify that it produced a non-empty MP4.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


SHARED_CHECKPOINTS = (
    "mapping_00109-model.pth.tar",
    "mapping_00229-model.pth.tar",
)


def run(
    command: list[str], *, cwd: Path | None = None, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command, cwd=cwd, env=env, text=True, encoding="utf-8", errors="replace", capture_output=True, check=False
    )


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--python", required=True, help="SadTalker venv 中的 python.exe")
    parser.add_argument("--home", required=True, help="SadTalker 根目录")
    parser.add_argument("--ffmpeg", default="ffmpeg", help="ffmpeg 可执行文件")
    parser.add_argument("--image", help="用于真实验收的授权正面照")
    parser.add_argument("--audio", help="用于真实验收的 WAV 音频")
    parser.add_argument("--size", type=int, choices=(256, 512), default=512)
    args = parser.parse_args()

    home = Path(args.home).resolve()
    python = Path(args.python).resolve()
    require(home.joinpath("inference.py").is_file(), "未找到 SadTalker inference.py。")
    require(python.is_file(), "未找到 SadTalker 虚拟环境的 python.exe。")
    require(shutil.which(args.ffmpeg) or Path(args.ffmpeg).is_file(), "未找到 ffmpeg，请设置 FFMPEG_BIN。")

    torch_check = run([str(python), "-c", "import torch; print(torch.__version__); print(torch.cuda.is_available()); print(torch.cuda.get_device_name(0) if torch.cuda.is_available() else '')"])
    require(torch_check.returncode == 0, f"Torch 无法导入：{torch_check.stderr.strip()}")
    lines = torch_check.stdout.splitlines()
    require(len(lines) >= 2 and lines[1].strip() == "True", f"GPU 不可用：{torch_check.stdout.strip()}")
    print(f"GPU 环境通过：{lines[0]} / {lines[2] if len(lines) > 2 else 'CUDA'}")

    checkpoint_dir = home / "checkpoints"
    required_checkpoints = (*SHARED_CHECKPOINTS, f"SadTalker_V0.0.2_{args.size}.safetensors")
    missing = [name for name in required_checkpoints if not checkpoint_dir.joinpath(name).is_file()]
    require(not missing, f"缺少官方模型权重：{', '.join(missing)}")
    print("官方模型权重齐全。")

    if not args.image and not args.audio:
        return
    require(bool(args.image and args.audio), "真实验收必须同时提供 --image 和 --audio。")
    image = Path(args.image).resolve()
    audio = Path(args.audio).resolve()
    require(image.is_file() and audio.is_file(), "验收照片或音频文件不存在。")
    with tempfile.TemporaryDirectory(prefix="sadtalker-smoke-") as temp_dir:
        runtime_dir = Path(temp_dir)
        staged_image = runtime_dir / f"source{image.suffix.lower() or '.jpg'}"
        staged_audio = runtime_dir / f"audio{audio.suffix.lower() or '.wav'}"
        result_dir = runtime_dir / "results"
        shutil.copy2(image, staged_image)
        shutil.copy2(audio, staged_audio)
        command = [
            str(python), str(home / "inference.py"), "--source_image", str(staged_image),
            "--driven_audio", str(staged_audio), "--result_dir", str(result_dir),
            "--preprocess", "crop", "--size", str(args.size),
        ]
        runtime_environment = os.environ.copy()
        ffmpeg_path = Path(args.ffmpeg)
        if ffmpeg_path.is_file():
            runtime_environment["PATH"] = (
                f"{ffmpeg_path.parent}{os.pathsep}{runtime_environment.get('PATH', '')}"
            )
        result = run(command, cwd=home, env=runtime_environment)
        require(result.returncode == 0, f"SadTalker CLI 失败：{(result.stderr or result.stdout)[-1200:]}")
        videos = sorted(result_dir.rglob("*.mp4"), key=lambda item: item.stat().st_mtime, reverse=True)
        require(bool(videos) and videos[0].stat().st_size > 0, "SadTalker 未产生非空 MP4。")
        probe = run([args.ffmpeg, "-v", "error", "-i", str(videos[0]), "-f", "null", "-"])
        require(probe.returncode == 0, f"输出 MP4 无法解码：{probe.stderr[-1200:]}")
        print(f"真实 MP4 验收通过：{videos[0]}（{videos[0].stat().st_size} bytes）")


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as exc:
        print(f"SadTalker 验收失败：{exc}", file=sys.stderr)
        raise SystemExit(1)
