"""执行器：抽象执行接口 + 本地命令执行器（Docker 沙箱为预留扩展点）。"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import shlex
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ExecutionContext:
    execution_id: str
    task_no: str
    slice_index: int
    command: str | None
    env_vars: dict[str, str]
    params: dict
    docker_image: str | None
    model_path: Path | None
    work_dir: Path
    timeout_seconds: int
    gpu_count: int = 1
    # 批处理任务工作项半开区间 [start, end) 与解压后的数据目录
    work_unit_start: int | None = None
    work_unit_end: int | None = None
    input_dir: Path | None = None
    work_unit_files: list[str] | None = None


@dataclass
class ExecutionResult:
    success: bool
    output_files: list[Path] = field(default_factory=list)
    error_message: str = ""
    duration_seconds: int = 0

    def compute_proof_hash(self) -> str:
        """结果文件内容哈希，作为算力证明（D1 第一阶段）。"""
        digest = hashlib.sha256()
        for path in sorted(self.output_files, key=lambda p: p.name):
            digest.update(path.name.encode("utf-8"))
            digest.update(path.read_bytes())
        return digest.hexdigest()


class Executor:
    async def run(self, ctx: ExecutionContext) -> ExecutionResult:
        raise NotImplementedError


class LocalExecutor(Executor):
    """本地执行器：直接在当前主机运行任务命令，适用于单机联调。"""

    async def run(self, ctx: ExecutionContext) -> ExecutionResult:
        ctx.work_dir.mkdir(parents=True, exist_ok=True)
        env = {**os.environ, **ctx.env_vars}
        env["PARAMS_JSON"] = json.dumps(ctx.params, ensure_ascii=False)
        if ctx.model_path:
            env["MODEL_PATH"] = str(ctx.model_path)
        # 批处理任务：注入数据目录与本批次工作项区间，供命令脚本按区间取文件
        if ctx.input_dir:
            env["INPUT_DIR"] = str(ctx.input_dir)
        if ctx.work_unit_start is not None:
            env["WORK_UNIT_START"] = str(ctx.work_unit_start)
        if ctx.work_unit_end is not None:
            env["WORK_UNIT_END"] = str(ctx.work_unit_end)
        if ctx.work_unit_files is not None:
            env["WORK_UNIT_FILES_JSON"] = json.dumps(
                ctx.work_unit_files, ensure_ascii=False
            )
        # 多卡节点默认暴露全部卡（0..N-1），供张量并行；任务显式指定时以任务 env 为准
        if "CUDA_VISIBLE_DEVICES" not in env and ctx.gpu_count > 1:
            env["CUDA_VISIBLE_DEVICES"] = ",".join(str(i) for i in range(ctx.gpu_count))

        if not ctx.command:
            return ExecutionResult(success=False, error_message="任务未提供可执行命令")
        cmd = shlex.split(ctx.command)

        started = time.monotonic()
        try:
            proc = await asyncio.to_thread(
                subprocess.run,
                cmd,
                cwd=ctx.work_dir,
                env=env,
                capture_output=True,
                text=True,
                timeout=ctx.timeout_seconds,
            )
        except subprocess.TimeoutExpired:
            return ExecutionResult(
                success=False,
                error_message=f"执行超时（{ctx.timeout_seconds}s）",
            )
        duration = int(time.monotonic() - started)

        if proc.returncode != 0:
            return ExecutionResult(
                success=False,
                error_message=(proc.stderr or proc.stdout or "执行失败")[:500],
                duration_seconds=duration,
            )

        # 将标准输出落盘，保证纯文本类任务也有结果文件可上报
        stdout_file = ctx.work_dir / "stdout.txt"
        stdout_file.write_text(proc.stdout or "", encoding="utf-8")
        output_files = [
            p
            for p in sorted(ctx.work_dir.iterdir())
            if p.is_file() and not p.name.startswith(".") and p.name != stdout_file.name
        ]
        return ExecutionResult(
            success=True,
            output_files=[stdout_file, *output_files],
            duration_seconds=duration,
        )