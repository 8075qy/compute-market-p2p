"""硬件探测：通过 nvidia-smi / rocm-smi / system_profiler 实测 GPU 型号、显存与实时运行指标。"""
from __future__ import annotations

import json
import logging
import re
import shutil
import subprocess
from dataclasses import dataclass

logger = logging.getLogger("agent.hardware")


@dataclass
class GpuInfo:
    gpu_model: str
    vram_gb: int
    driver_version: str = ""
    vendor: str = ""


@dataclass
class GpuMetrics:
    gpu_util: float = 0.0
    vram_used_gb: float = 0.0
    temp_c: float = 0.0


def _run(cmd: list[str], timeout: int = 10) -> str:
    """执行探测命令，失败时返回空字符串。"""
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout, check=False
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return ""
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def detect_gpus() -> list[GpuInfo]:
    """实测本机全部 GPU，探测不到返回空列表。"""
    if shutil.which("nvidia-smi"):
        gpus = _detect_nvidia_gpus()
        if gpus:
            return gpus
    if shutil.which("rocm-smi"):
        info = _detect_amd()
        if info:
            return [info]
    if shutil.which("system_profiler"):
        info = _detect_apple()
        if info:
            return [info]
    return []


def detect_gpu() -> GpuInfo | None:
    """实测本机 GPU 型号与显存（多卡机器返回第一张卡），探测不到返回 None。"""
    gpus = detect_gpus()
    return gpus[0] if gpus else None


def _detect_nvidia_gpus() -> list[GpuInfo]:
    out = _run(
        [
            "nvidia-smi",
            "--query-gpu=name,memory.total,driver_version",
            "--format=csv,noheader,nounits",
        ]
    )
    if not out:
        return []
    gpus: list[GpuInfo] = []
    for line in out.splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 2 or not parts[0]:
            continue
        try:
            vram_gb = round(float(parts[1]) / 1024)
        except ValueError:
            vram_gb = 0
        gpus.append(
            GpuInfo(
                gpu_model=parts[0],
                vram_gb=vram_gb,
                driver_version=parts[2] if len(parts) > 2 else "",
                vendor="nvidia",
            )
        )
    return gpus


def _detect_amd() -> GpuInfo | None:
    out = _run(["rocm-smi", "--showproductname", "--csv"])
    if not out:
        return None
    lines = out.splitlines()
    if len(lines) < 2:
        return None
    cells = [c.strip() for c in lines[1].split(",")]
    if len(cells) < 2 or not cells[1]:
        return None
    return GpuInfo(
        gpu_model=cells[1],
        vram_gb=_detect_amd_vram(),
        vendor="amd",
    )


def _detect_amd_vram() -> int:
    """通过 rocm-smi --showmeminfo vram 读取显存，格式随版本变化，读不到返回 0。"""
    out = _run(["rocm-smi", "--showmeminfo", "vram"])
    if not out:
        return 0
    match = re.search(r"Total\s+VRAM:\s*(\d+)\s*MB", out, re.IGNORECASE)
    if not match:
        return 0
    try:
        return round(int(match.group(1)) / 1024)
    except ValueError:
        return 0


def _detect_apple() -> GpuInfo | None:
    """Apple Silicon 探测：通过 system_profiler 读取 SoC 型号与统一内存。"""
    out = _run(["system_profiler", "SPHardwareDataType", "-json"], timeout=30)
    if not out:
        return None
    try:
        data = json.loads(out)
        hardware = (data.get("SPHardwareDataType") or [{}])[0]
    except (json.JSONDecodeError, IndexError, TypeError, AttributeError):
        return None
    chip = (hardware.get("chip_type") or "").strip()
    # 仅识别 Apple 自研芯片（Apple M1 / M2 / M3 / M4 ...），Intel Mac 无 chip_type
    if not chip.lower().startswith("apple"):
        return None
    return GpuInfo(
        gpu_model=chip,
        vram_gb=_parse_memory_gb(hardware.get("physical_memory") or ""),
        vendor="apple",
    )


def _parse_memory_gb(value: str) -> int:
    """解析 physical_memory 字符串（如 '64 GB' / '1.5 TB'），失败返回 0。"""
    parts = value.split()
    if not parts:
        return 0
    try:
        amount = float(parts[0])
    except ValueError:
        return 0
    unit = parts[1].upper() if len(parts) > 1 else "GB"
    if unit.startswith("TB"):
        amount *= 1024
    return round(amount)


def sample_gpu_metrics() -> GpuMetrics:
    """实测当前 GPU 汇总指标（多卡：显存求和、利用率/温度取均值），探测不到返回全 0。"""
    if shutil.which("nvidia-smi"):
        out = _run(
            [
                "nvidia-smi",
                "--query-gpu=utilization.gpu,memory.used,temperature.gpu",
                "--format=csv,noheader,nounits",
            ]
        )
        if out:
            utils: list[float] = []
            vram_used_total = 0.0
            temps: list[float] = []
            for line in out.splitlines():
                parts = [p.strip() for p in line.split(",")]
                if len(parts) < 3:
                    continue
                try:
                    utils.append(float(parts[0]))
                    vram_used_total += float(parts[1]) / 1024
                    temps.append(float(parts[2]))
                except ValueError:
                    continue
            if utils:
                return GpuMetrics(
                    gpu_util=sum(utils) / len(utils),
                    vram_used_gb=vram_used_total,
                    temp_c=sum(temps) / len(temps),
                )
    return GpuMetrics()


def detect_gpu_uuid() -> str | None:
    """实测 GPU 唯一标识（nvidia-smi UUID / rocm-smi uniqueid），探测不到返回 None。

    用于防多开（P1-5）：同一 GPU UUID 限注册节点数。浏览器/移动端无法获取，返回 None 时不受限。
    """
    if shutil.which("nvidia-smi"):
        out = _run(
            ["nvidia-smi", "--query-gpu=uuid", "--format=csv,noheader,nounits"]
        )
        if out:
            value = out.splitlines()[0].strip()
            if value and value.lower() != "n/a":
                return value
    if shutil.which("rocm-smi"):
        out = _run(["rocm-smi", "--showuniqueid", "--csv"])
        if out:
            lines = out.splitlines()
            if len(lines) >= 2:
                cells = [c.strip() for c in lines[1].split(",")]
                if len(cells) >= 2 and cells[1]:
                    return cells[1]
    return None