"""Apply reproducible compatibility checks to the separately installed SadTalker venv.

Usage (from backend):
    python scripts/prepare_sadtalker_runtime.py --python ../runtimes/SadTalker/.venv/Scripts/python.exe
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


OLD_IMPORT = "from torchvision.transforms.functional_tensor import rgb_to_grayscale"
NEW_IMPORT = "from torchvision.transforms.functional import rgb_to_grayscale"


def site_packages(python: str) -> Path:
    command = [python, "-c", "import sysconfig; print(sysconfig.get_paths()['purelib'])"]
    result = subprocess.run(command, capture_output=True, text=True, check=True)
    return Path(result.stdout.strip())


def patch_basicsr(python: str) -> None:
    target = site_packages(python) / "basicsr" / "data" / "degradations.py"
    if not target.is_file():
        raise RuntimeError(f"未找到 BasicSR 兼容补丁目标：{target}")
    content = target.read_text(encoding="utf-8")
    if NEW_IMPORT in content:
        print("BasicSR 与新版 torchvision 已兼容，无需修改。")
        return
    if OLD_IMPORT not in content:
        raise RuntimeError("BasicSR 的 torchvision 导入形式未知，已停止，未修改运行环境。")
    target.write_text(content.replace(OLD_IMPORT, NEW_IMPORT), encoding="utf-8")
    print(f"已应用 BasicSR/torchvision 兼容补丁：{target}")


def verify_import(python: str) -> None:
    command = [python, "-c", "from basicsr.data.degradations import rgb_to_grayscale; print('BasicSR import OK')"]
    subprocess.run(command, check=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--python", required=True, help="SadTalker 虚拟环境中的 python.exe")
    args = parser.parse_args()
    patch_basicsr(args.python)
    verify_import(args.python)


if __name__ == "__main__":
    try:
        main()
    except (OSError, subprocess.CalledProcessError, RuntimeError) as exc:
        print(f"SadTalker 运行环境准备失败：{exc}", file=sys.stderr)
        raise SystemExit(1)
