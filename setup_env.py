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
    """Read base plus local full-feature dependencies without replacing torch."""
    root = Path(__file__).parent
    paths = [root / "requirements.txt", root / "requirements-full.txt"]
    excluded_prefixes = ("--extra-index-url", "torch==", "transformers==")
    dependencies: list[str] = []
    for path in paths:
        if not path.exists():
            continue
        dependencies.extend(
            line
            for raw_line in path.read_text(encoding="utf-8-sig").splitlines()
            if (line := raw_line.strip())
            and not line.startswith("#")
            and not line.startswith(excluded_prefixes)
        )
    return list(dict.fromkeys(dependencies))

def run(command: list[str]) -> None:
    print("Running:", " ".join(command))
    subprocess.run(command, check=True)

def has_nvidia_gpu() -> bool:
    if shutil.which("nvidia-smi") is None:
        print("nvidia-smi not found; falling back to CPU install.")
        return False
    try:
        subprocess.run(["nvidia-smi"], check=True, capture_output=True, text=True, timeout=10)
        return True
    except Exception as exc:  # noqa: BLE001
        print(f"GPU detection failed: {exc}. Falling back to CPU install.")
        return False

def installed_gpu_torch() -> bool:
    try:
        torch = importlib.import_module("torch")
    except ImportError:
        return False
    return "+cu" in str(torch.__version__) or bool(torch.cuda.is_available())

def install_torch(use_gpu: bool) -> None:
    if installed_gpu_torch():
        print("Detected an already-installed GPU build of torch; skipping install to avoid overwriting it.")
        return
    index_url = CUDA_INDEX_URL if use_gpu else CPU_INDEX_URL
    version = TORCH_VERSION if use_gpu else f"{TORCH_VERSION}+cpu"
    run([sys.executable, "-m", "pip", "install", f"torch=={version}", "--index-url", index_url])

def self_check() -> None:
    torch = importlib.import_module("torch")
    cuda_available = bool(torch.cuda.is_available())
    device_name = torch.cuda.get_device_name(0) if cuda_available else "CPU"
    print(f"torch version: {torch.__version__}")
    print(f"CUDA available: {cuda_available}")
    print(f"Device: {device_name}")
    print(f"GPU acceleration enabled: {device_name}" if cuda_available else "No NVIDIA GPU detected; installed the CPU build.")

def main() -> None:
    try:
        install_torch(has_nvidia_gpu())
        run([sys.executable, "-m", "pip", "install", *local_requirements()])
        run([sys.executable, "-m", "pip", "install", f"transformers=={TRANSFORMERS_VERSION}"])
        self_check()
    except subprocess.CalledProcessError as exc:
        raise SystemExit(f"Install failed: {exc}. Check your network, pip, or Python environment, then retry.") from exc

if __name__ == "__main__":
    main()
