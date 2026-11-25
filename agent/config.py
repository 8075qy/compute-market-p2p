"""Agent 配置：从 .env / 环境变量加载。"""
from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


def _int(name: str, default: int) -> int:
    raw = os.getenv(name)
    return int(raw) if raw not in (None, "") else default


def _float(name: str, default: float) -> float:
    raw = os.getenv(name)
    return float(raw) if raw not in (None, "") else default


@dataclass
class AgentSettings:
    api_base_url: str = os.getenv("API_BASE_URL", "http://localhost:8000/api/v1")
    contact: str = os.getenv("AGENT_CONTACT", "")
    password: str = os.getenv("AGENT_PASSWORD", "")

    node_id: str = os.getenv("NODE_ID", "")
    node_name: str = os.getenv("NODE_NAME", "agent-node")
    gpu_model: str = os.getenv("GPU_MODEL", "RTX 3080")
    vram_gb: int = _int("VRAM_GB", 10)
    peak_tflops: float = _float("PEAK_TFLOPS", 30.0)

    heartbeat_interval: int = _int("HEARTBEAT_INTERVAL", 30)
    poll_interval: int = _int("POLL_INTERVAL", 5)
    work_dir: str = os.getenv("WORK_DIR", "./data")


settings = AgentSettings()