"""GPU 规格库：预置常见 GPU 型号的显存与峰值算力参考值，减少节点登记手填。"""

from __future__ import annotations

import json

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import GpuSpec

# 模糊匹配所需的最短查询串长度
MIN_FUZZY_MATCH_LEN = 3

# 峰值算力口径：NVIDIA 游戏卡/AMD/Apple/Intel 采用 FP32，数据中心卡采用官方宣传峰值
GPU_SPEC_SEED: list[dict] = [
    # NVIDIA 游戏卡
    {
        "gpu_model": "NVIDIA GeForce RTX 2060",
        "vendor": "nvidia",
        "vram_gb": 6,
        "peak_tflops": 6.5,
        "aliases": ["RTX 2060", "2060"],
    },
    {
        "gpu_model": "NVIDIA GeForce RTX 2060 Super",
        "vendor": "nvidia",
        "vram_gb": 8,
        "peak_tflops": 7.2,
        "aliases": ["RTX 2060 Super", "2060 Super"],
    },
    {
        "gpu_model": "NVIDIA GeForce RTX 2070",
        "vendor": "nvidia",
        "vram_gb": 8,
        "peak_tflops": 7.5,
        "aliases": ["RTX 2070", "2070"],
    },
    {
        "gpu_model": "NVIDIA GeForce RTX 2070 Super",
        "vendor": "nvidia",
        "vram_gb": 8,
        "peak_tflops": 9.1,
        "aliases": ["RTX 2070 Super", "2070 Super"],
    },
    {
        "gpu_model": "NVIDIA GeForce RTX 2080",
        "vendor": "nvidia",
        "vram_gb": 8,
        "peak_tflops": 10.1,
        "aliases": ["RTX 2080", "2080"],
    },
    {
        "gpu_model": "NVIDIA GeForce RTX 2080 Super",
        "vendor": "nvidia",
        "vram_gb": 8,
        "peak_tflops": 11.2,
        "aliases": ["RTX 2080 Super", "2080 Super"],
    },
    {
        "gpu_model": "NVIDIA GeForce RTX 2080 Ti",
        "vendor": "nvidia",
        "vram_gb": 11,
        "peak_tflops": 13.5,
        "aliases": ["RTX 2080 Ti", "2080 Ti"],
    },
    {
        "gpu_model": "NVIDIA GeForce RTX 3060",
        "vendor": "nvidia",
        "vram_gb": 12,
        "peak_tflops": 13,
        "aliases": ["RTX 3060", "3060"],
    },
    {
        "gpu_model": "NVIDIA GeForce RTX 3060 Ti",
        "vendor": "nvidia",
        "vram_gb": 8,
        "peak_tflops": 16,
        "aliases": ["RTX 3060 Ti", "3060 Ti"],
    },
    {
        "gpu_model": "NVIDIA GeForce RTX 3070",
        "vendor": "nvidia",
        "vram_gb": 8,
        "peak_tflops": 20,
        "aliases": ["RTX 3070", "3070"],
    },
    {
        "gpu_model": "NVIDIA GeForce RTX 3070 Ti",
        "vendor": "nvidia",
        "vram_gb": 8,
        "peak_tflops": 22,
        "aliases": ["RTX 3070 Ti", "3070 Ti"],
    },
    {
        "gpu_model": "NVIDIA GeForce RTX 3080",
        "vendor": "nvidia",
        "vram_gb": 10,
        "peak_tflops": 30,
        "aliases": ["RTX 3080", "3080"],
    },
    {
        "gpu_model": "NVIDIA GeForce RTX 3080 Ti",
        "vendor": "nvidia",
        "vram_gb": 12,
        "peak_tflops": 34,
        "aliases": ["RTX 3080 Ti", "3080 Ti"],
    },
    {
        "gpu_model": "NVIDIA GeForce RTX 3090",
        "vendor": "nvidia",
        "vram_gb": 24,
        "peak_tflops": 36,
        "aliases": ["RTX 3090", "3090"],
    },
    {
        "gpu_model": "NVIDIA GeForce RTX 3090 Ti",
        "vendor": "nvidia",
        "vram_gb": 24,
        "peak_tflops": 40,
        "aliases": ["RTX 3090 Ti", "3090 Ti"],
    },
    {
        "gpu_model": "NVIDIA GeForce RTX 4070",
        "vendor": "nvidia",
        "vram_gb": 12,
        "peak_tflops": 29,
        "aliases": ["RTX 4070", "4070"],
    },
    {
        "gpu_model": "NVIDIA GeForce RTX 4070 Ti",
        "vendor": "nvidia",
        "vram_gb": 12,
        "peak_tflops": 40,
        "aliases": ["RTX 4070 Ti", "4070 Ti"],
    },
    {
        "gpu_model": "NVIDIA GeForce RTX 4080",
        "vendor": "nvidia",
        "vram_gb": 16,
        "peak_tflops": 49,
        "aliases": ["RTX 4080", "4080"],
    },
    {
        "gpu_model": "NVIDIA GeForce RTX 4090",
        "vendor": "nvidia",
        "vram_gb": 24,
        "peak_tflops": 83,
        "aliases": ["RTX 4090", "4090"],
    },
    # NVIDIA 数据中心卡
    {
        "gpu_model": "NVIDIA A100 40GB",
        "vendor": "nvidia",
        "vram_gb": 40,
        "peak_tflops": 156,
        "aliases": ["A100 40G", "A100 40GB", "A100"],
    },
    {
        "gpu_model": "NVIDIA A100 80GB",
        "vendor": "nvidia",
        "vram_gb": 80,
        "peak_tflops": 156,
        "aliases": ["A100 80G", "A100 80GB"],
    },
    {
        "gpu_model": "NVIDIA H100 80GB",
        "vendor": "nvidia",
        "vram_gb": 80,
        "peak_tflops": 300,
        "aliases": ["H100 80G", "H100 80GB", "H100"],
    },
    {
        "gpu_model": "NVIDIA V100 16GB",
        "vendor": "nvidia",
        "vram_gb": 16,
        "peak_tflops": 15.7,
        "aliases": ["V100 16G", "V100 16GB", "V100"],
    },
    {
        "gpu_model": "NVIDIA V100 32GB",
        "vendor": "nvidia",
        "vram_gb": 32,
        "peak_tflops": 15.7,
        "aliases": ["V100 32G", "V100 32GB"],
    },
    {
        "gpu_model": "NVIDIA A10",
        "vendor": "nvidia",
        "vram_gb": 24,
        "peak_tflops": 31.2,
        "aliases": ["A10"],
    },
    {
        "gpu_model": "NVIDIA A40",
        "vendor": "nvidia",
        "vram_gb": 48,
        "peak_tflops": 37.4,
        "aliases": ["A40"],
    },
    {
        "gpu_model": "NVIDIA L40S",
        "vendor": "nvidia",
        "vram_gb": 48,
        "peak_tflops": 91.6,
        "aliases": ["L40S", "L40"],
    },
    # Apple M 系列（显存为统一内存，取常见基础配置）
    {
        "gpu_model": "Apple M1",
        "vendor": "apple",
        "vram_gb": 8,
        "peak_tflops": 2.6,
        "aliases": ["M1"],
    },
    {
        "gpu_model": "Apple M1 Pro",
        "vendor": "apple",
        "vram_gb": 16,
        "peak_tflops": 5.2,
        "aliases": ["M1 Pro"],
    },
    {
        "gpu_model": "Apple M1 Max",
        "vendor": "apple",
        "vram_gb": 32,
        "peak_tflops": 10.4,
        "aliases": ["M1 Max"],
    },
    {
        "gpu_model": "Apple M1 Ultra",
        "vendor": "apple",
        "vram_gb": 64,
        "peak_tflops": 21,
        "aliases": ["M1 Ultra"],
    },
    {
        "gpu_model": "Apple M2",
        "vendor": "apple",
        "vram_gb": 8,
        "peak_tflops": 3.6,
        "aliases": ["M2"],
    },
    {
        "gpu_model": "Apple M2 Pro",
        "vendor": "apple",
        "vram_gb": 16,
        "peak_tflops": 6.8,
        "aliases": ["M2 Pro"],
    },
    {
        "gpu_model": "Apple M2 Max",
        "vendor": "apple",
        "vram_gb": 32,
        "peak_tflops": 13.5,
        "aliases": ["M2 Max"],
    },
    {
        "gpu_model": "Apple M2 Ultra",
        "vendor": "apple",
        "vram_gb": 64,
        "peak_tflops": 27,
        "aliases": ["M2 Ultra"],
    },
    {
        "gpu_model": "Apple M3",
        "vendor": "apple",
        "vram_gb": 8,
        "peak_tflops": 4.1,
        "aliases": ["M3"],
    },
    {
        "gpu_model": "Apple M3 Pro",
        "vendor": "apple",
        "vram_gb": 18,
        "peak_tflops": 7.4,
        "aliases": ["M3 Pro"],
    },
    {
        "gpu_model": "Apple M3 Max",
        "vendor": "apple",
        "vram_gb": 36,
        "peak_tflops": 14.2,
        "aliases": ["M3 Max"],
    },
    {
        "gpu_model": "Apple M4",
        "vendor": "apple",
        "vram_gb": 8,
        "peak_tflops": 4.5,
        "aliases": ["M4"],
    },
    {
        "gpu_model": "Apple M4 Pro",
        "vendor": "apple",
        "vram_gb": 24,
        "peak_tflops": 7.5,
        "aliases": ["M4 Pro"],
    },
    {
        "gpu_model": "Apple M4 Max",
        "vendor": "apple",
        "vram_gb": 36,
        "peak_tflops": 14.4,
        "aliases": ["M4 Max"],
    },
    # AMD
    {
        "gpu_model": "AMD Radeon RX 6800 XT",
        "vendor": "amd",
        "vram_gb": 16,
        "peak_tflops": 20.7,
        "aliases": ["RX 6800 XT", "6800 XT"],
    },
    {
        "gpu_model": "AMD Radeon RX 6900 XT",
        "vendor": "amd",
        "vram_gb": 16,
        "peak_tflops": 23,
        "aliases": ["RX 6900 XT", "6900 XT"],
    },
    {
        "gpu_model": "AMD Radeon RX 7900 XTX",
        "vendor": "amd",
        "vram_gb": 24,
        "peak_tflops": 61.4,
        "aliases": ["RX 7900 XTX", "7900 XTX"],
    },
    {
        "gpu_model": "AMD Instinct MI250X",
        "vendor": "amd",
        "vram_gb": 128,
        "peak_tflops": 47.9,
        "aliases": ["MI250X", "MI250"],
    },
    {
        "gpu_model": "AMD Instinct MI300X",
        "vendor": "amd",
        "vram_gb": 192,
        "peak_tflops": 1300,
        "aliases": ["MI300X", "MI300"],
    },
    # Intel
    {
        "gpu_model": "Intel Arc A770",
        "vendor": "intel",
        "vram_gb": 16,
        "peak_tflops": 19.7,
        "aliases": ["Arc A770", "A770"],
    },
]


async def seed_gpu_specs(session: AsyncSession) -> None:
    """幂等预置 GPU 规格数据，已存在数据时跳过。"""
    count = await session.scalar(select(func.count()).select_from(GpuSpec))
    if count:
        return
    for item in GPU_SPEC_SEED:
        session.add(
            GpuSpec(
                gpu_model=item["gpu_model"],
                vendor=item["vendor"],
                vram_gb=item["vram_gb"],
                peak_tflops=item["peak_tflops"],
                aliases_json=json.dumps(item["aliases"], ensure_ascii=False),
            )
        )
    await session.commit()


class GpuSpecService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_specs(self) -> list[GpuSpec]:
        result = await self.session.execute(select(GpuSpec).order_by(GpuSpec.id))
        return list(result.scalars())

    async def match(self, model: str) -> GpuSpec | None:
        """按型号匹配规格：精确匹配型号/别名，再模糊包含匹配。"""
        target = model.strip().lower()
        if not target:
            return None

        specs = await self.list_specs()

        # 精确匹配规范型号
        for spec in specs:
            if spec.gpu_model.lower() == target:
                return spec

        # 精确匹配别名
        for spec in specs:
            if target in [a.lower() for a in spec.aliases]:
                return spec

        # 模糊匹配：型号名包含查询串，优先返回最短型号（更通用）
        if len(target) >= MIN_FUZZY_MATCH_LEN:
            candidates = [s for s in specs if target in s.gpu_model.lower()]
            if candidates:
                return min(candidates, key=lambda s: len(s.gpu_model))
            candidates = [s for s in specs if s.gpu_model.lower() in target]
            if candidates:
                return max(candidates, key=lambda s: len(s.gpu_model))

        return None
