from __future__ import annotations

import importlib
import shutil
import subprocess
import sys
from pathlib import Path

TORCH_VERSION = "2.12.1"
TRANSFORMERS_VERSION = "5.13.0"
CUDA_INDEX_URL = "https://download.pytorch.org/whl/cu130"
CPU_INDEX_URL = "https://download.pytorch.org/whl/cpu"


def local_requirements() -> list[str]:
    """Read shared app dependencies while excluding cloud-only ML packages."""
    path = Path(__file__).with_name("requirements.txt")
    excluded_prefixes = ("--extra-index-url", "torch==", "transformers==")
    return [
        line
        for raw_line in path.read_text(encoding="utf-8-sig").splitlines()
        if (line := raw_line.strip())
        and not line.startswith("#")
        and not line.startswith(excluded_prefixes)
    ]

def run(command: list[str]) -> None:
    print("执行：", " ".join(command))
    subprocess.run(command, check=True)

def has_nvidia_gpu() -> bool:
    if shutil.which("nvidia-smi") is None:
        print("未找到 nvidia-smi，将回退 CPU 安装。")
        return False
    try:
        subprocess.run(["nvidia-smi"], check=True, capture_output=True, text=True, timeout=10)
        return True
    except Exception as exc:  # noqa: BLE001
        print(f"GPU 探测失败：{exc}。将回退 CPU 安装。")
        return False

def installed_gpu_torch() -> bool:
    try:
        torch = importlib.import_module("torch")
    except ImportError:
        return False
    return "+cu" in str(torch.__version__) or bool(torch.cuda.is_available())

def install_torch(use_gpu: bool) -> None:
    if installed_gpu_torch():
        print("检测到已安装 GPU 版 torch，跳过安装，避免覆盖。")
        return
    index_url = CUDA_INDEX_URL if use_gpu else CPU_INDEX_URL
    version = TORCH_VERSION if use_gpu else f"{TORCH_VERSION}+cpu"
    run([sys.executable, "-m", "pip", "install", f"torch=={version}", "--index-url", index_url])

def self_check() -> None:
    torch = importlib.import_module("torch")
    cuda_available = bool(torch.cuda.is_available())
    device_name = torch.cuda.get_device_name(0) if cuda_available else "CPU"
    print(f"torch 版本：{torch.__version__}")
    print(f"CUDA 可用：{cuda_available}")
    print(f"设备：{device_name}")
    print(f"已启用 GPU 加速：{device_name}" if cuda_available else "未检测到 NVIDIA GPU，已安装 CPU 版本。")

def main() -> None:
    try:
        install_torch(has_nvidia_gpu())
        run([sys.executable, "-m", "pip", "install", *local_requirements()])
        run([sys.executable, "-m", "pip", "install", f"transformers=={TRANSFORMERS_VERSION}"])
        self_check()
    except subprocess.CalledProcessError as exc:
        raise SystemExit(f"安装失败：{exc}。请检查网络、pip 或 Python 环境后重试。") from exc

if __name__ == "__main__":
    main()
