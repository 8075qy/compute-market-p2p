"""供给方节点 Agent 主程序：登录 → 注册节点 → 心跳 + 领取分片执行闭环。"""
from __future__ import annotations

import asyncio
import json
import logging
import signal
import zipfile
from pathlib import Path
from typing import Any

from api_client import ApiClient
from config import settings
from executor import ExecutionContext, ExecutionResult, LocalExecutor
from hardware import GpuInfo, detect_gpu, detect_gpu_uuid, detect_gpus, sample_gpu_metrics

logger = logging.getLogger("agent")


class Agent:
    def __init__(self) -> None:
        self.client = ApiClient(settings.api_base_url)
        self.executor = LocalExecutor()
        self.node_id: str = settings.node_id
        self.gpus: list[GpuInfo] = detect_gpus()
        self.gpu_info: GpuInfo | None = self.gpus[0] if self.gpus else None
        self.gpu_count: int = len(self.gpus) or 1
        self.gpu_uuid: str | None = detect_gpu_uuid()
        self._stop = asyncio.Event()
        self.models_dir = Path(settings.work_dir) / "models"
        self.runs_dir = Path(settings.work_dir) / "runs"
        self.models_dir.mkdir(parents=True, exist_ok=True)
        self.runs_dir.mkdir(parents=True, exist_ok=True)
        if self.gpu_info:
            logger.info(
                "已探测到 GPU：%d×%s（单卡 %sGB，总显存 %dGB，驱动 %s）",
                self.gpu_count,
                self.gpu_info.gpu_model,
                self.gpu_info.vram_gb,
                self.gpu_info.vram_gb * self.gpu_count,
                self.gpu_info.driver_version or "未知",
            )
        else:
            logger.warning("未探测到 GPU，将回退使用 .env 中的 GPU_MODEL / VRAM_GB")

    async def start(self) -> None:
        await self._login()
        await self._ensure_node()
        await asyncio.gather(
            self._heartbeat_loop(),
            self._poll_loop(),
        )

    async def _login(self) -> None:
        if not settings.contact or not settings.password:
            raise RuntimeError("请在 .env 中配置 AGENT_CONTACT / AGENT_PASSWORD")
        await self.client.login(settings.contact, settings.password)
        logger.info("已登录供给方账号 %s", settings.contact)

    async def _ensure_node(self) -> None:
        gpu_model = (self.gpu_info.gpu_model if self.gpu_info else "") or settings.gpu_model
        vram_gb = (self.gpu_info.vram_gb if self.gpu_info else 0) or settings.vram_gb
        matched_tflops = await self._resolve_peak_tflops(gpu_model)

        if self.node_id:
            # 复用已登记节点：实测到 GPU 时回填真实硬件信息，避免浏览器预填值长期失真
            if self.gpu_info:
                update: dict[str, Any] = {
                    "gpu_model": self.gpu_info.gpu_model,
                    "gpu_count": self.gpu_count,
                }
                if self.gpu_info.vram_gb > 0:
                    update["vram_gb"] = self.gpu_info.vram_gb
                if matched_tflops is not None:
                    update["peak_tflops"] = matched_tflops
                if self.gpu_uuid:
                    update["gpu_uuid"] = self.gpu_uuid
                try:
                    await self.client.update_node(self.node_id, update)
                    logger.info("节点 %s 已按实测硬件校准", self.node_id)
                except Exception as exc:  # noqa: BLE001
                    logger.warning("节点硬件校准失败：%s", exc)
                await self._report_benchmark(matched_tflops)
            return

        node = await self.client.register_node(
            {
                "name": settings.node_name,
                "gpu_model": gpu_model,
                "vram_gb": vram_gb,
                "peak_tflops": matched_tflops or settings.peak_tflops,
                "gpu_count": self.gpu_count,
                "gpu_uuid": self.gpu_uuid,
            }
        )
        self.node_id = str(node["id"])
        logger.info("节点已注册：%s", self.node_id)
        await self._report_benchmark(matched_tflops)

    async def _report_benchmark(self, benchmark_tflops: float | None) -> None:
        """算力对标（P1-4）：上报规格库标称值作为能力对标，异常仅告警不阻断。"""
        if benchmark_tflops is None:
            return
        try:
            await self.client.report_benchmark(self.node_id, benchmark_tflops)
            logger.info("节点 %s 已完成算力对标（%.1f TFLOPS）", self.node_id, benchmark_tflops)
        except Exception as exc:  # noqa: BLE001
            logger.warning("算力对标上报失败：%s", exc)

    async def _resolve_peak_tflops(self, gpu_model: str) -> float | None:
        """按实测 GPU 型号匹配规格库得到峰值算力，匹配不到返回 None（回退 .env）。"""
        if not gpu_model:
            return None
        try:
            spec = await self.client.match_gpu_spec(gpu_model)
        except Exception as exc:  # noqa: BLE001
            logger.warning("峰值算力匹配失败：%s", exc)
            return None
        if not spec or not spec.get("peak_tflops"):
            return None
        try:
            return float(spec["peak_tflops"])
        except (TypeError, ValueError):
            return None

    def _cached_models(self) -> list[str]:
        return [p.name for p in self.models_dir.iterdir() if p.is_file()]

    async def _heartbeat_loop(self) -> None:
        while not self._stop.is_set():
            try:
                metrics = sample_gpu_metrics()
                await self.client.heartbeat(
                    self.node_id,
                    {
                        "gpu_util": metrics.gpu_util,
                        "vram_used_gb": int(round(metrics.vram_used_gb)),
                        "temp_c": int(round(metrics.temp_c)),
                        "docker_status": "ok",
                        "cached_models": self._cached_models(),
                    },
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("心跳失败：%s", exc)
            await self._sleep(settings.heartbeat_interval)

    async def _poll_loop(self) -> None:
        while not self._stop.is_set():
            try:
                pending = await self.client.pending_executions(self.node_id)
            except Exception as exc:  # noqa: BLE001
                logger.warning("拉取待执行分片失败：%s", exc)
                await self._sleep(settings.poll_interval)
                continue

            for item in pending:
                await self._handle(item)
            await self._sleep(settings.poll_interval)

    async def _handle(self, item: dict) -> None:
        execution_id = item["execution_id"]
        logger.info(
            "领取分片 %s（任务 %s，切片 %s）",
            execution_id,
            item.get("task_no"),
            item.get("slice_index"),
        )
        try:
            await self.client.start_execution(execution_id)
            model_path = await self._ensure_model(item)
            work_dir = self.runs_dir / execution_id
            input_dir, work_unit_files = await self._prepare_batch_input(item, work_dir)
            ctx = ExecutionContext(
                execution_id=execution_id,
                task_no=item.get("task_no") or "",
                slice_index=item.get("slice_index", 0),
                command=item.get("command"),
                env_vars=item.get("env_vars") or {},
                params=item.get("params") or {},
                docker_image=item.get("docker_image"),
                model_path=model_path,
                work_dir=work_dir,
                timeout_seconds=(item.get("timeout_minutes") or 60) * 60,
                gpu_count=self.gpu_count,
                work_unit_start=item.get("work_unit_start"),
                work_unit_end=item.get("work_unit_end"),
                input_dir=input_dir,
                work_unit_files=work_unit_files,
            )
            result = await self.executor.run(ctx)
            if not result.success:
                await self.client.fail_execution(execution_id, result.error_message)
                return

            result_files = await self._upload_results(execution_id, result)
            complete_payload: dict[str, Any] = {
                "result_files": result_files,
                "proof_hash": result.compute_proof_hash(),
                "compute_duration_seconds": result.duration_seconds,
            }
            if item.get("work_unit_start") is not None and item.get("work_unit_end") is not None:
                complete_payload["completed_work_units"] = (
                    item["work_unit_end"] - item["work_unit_start"]
                )
            await self.client.complete_execution(execution_id, complete_payload)
            logger.info("分片 %s 已完成", execution_id)
        except Exception as exc:  # noqa: BLE001
            logger.exception("分片 %s 处理异常", execution_id)
            try:
                await self.client.fail_execution(execution_id, str(exc)[:500])
            except Exception:  # noqa: BLE001
                pass

    async def _prepare_batch_input(
        self, item: dict, work_dir: Path
    ) -> tuple[Path | None, list[str] | None]:
        """批处理任务：下载数据包与 manifest，解压到工作目录，返回本批次文件子集。

        工作项 i 对应 manifest 第 i 个文件，本方法按 [start, end) 截取文件列表，
        命令脚本通过 INPUT_DIR + WORK_UNIT_FILES_JSON 环境变量按区间处理。
        非批处理任务返回 (None, None)。
        """
        start = item.get("work_unit_start")
        end = item.get("work_unit_end")
        if start is None or not item.get("input_file_key"):
            return None, None

        download = await self.client.input_download_url(item["execution_id"])
        work_dir.mkdir(parents=True, exist_ok=True)

        archive_path = work_dir / "input.zip"
        await self.client.download_file(download["input_download_url"], archive_path)

        input_dir = work_dir / "input"
        input_dir.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(archive_path) as zf:
            zf.extractall(input_dir)
        archive_path.unlink(missing_ok=True)

        manifest_path = work_dir / "manifest.json"
        await self.client.download_file(download["manifest_download_url"], manifest_path)
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            files = manifest.get("files") or []
        except (ValueError, UnicodeDecodeError):
            files = []

        work_unit_files = files[start:end]
        logger.info(
            "批处理批次 %s 准备数据：工作项 [%d, %d) 共 %d 个文件",
            item["execution_id"],
            start,
            end,
            len(work_unit_files),
        )
        return input_dir, work_unit_files

    async def _ensure_model(self, item: dict) -> Path | None:
        if not item.get("model_file_key") and not item.get("model_id"):
            return None
        download = await self.client.model_download_url(item["execution_id"])
        object_key = download["object_key"]
        local_path = self.models_dir / Path(object_key).name
        if local_path.exists():
            return local_path
        await self.client.download_file(download["download_url"], local_path)
        logger.info("已缓存模型 %s", object_key)
        return local_path

    async def _upload_results(
        self, execution_id: str, result: ExecutionResult
    ) -> list[dict]:
        uploaded: list[dict] = []
        for path in result.output_files:
            presign = await self.client.presign_result_upload(
                execution_id, path.name, path.stat().st_size
            )
            await self.client.upload_file(presign["upload_url"], path)
            uploaded.append(
                {
                    "key": presign["object_key"],
                    "name": path.name,
                    "size": path.stat().st_size,
                }
            )
        return uploaded

    async def _sleep(self, seconds: int) -> None:
        try:
            await asyncio.wait_for(self._stop.wait(), timeout=seconds)
        except asyncio.TimeoutError:
            pass


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    agent = Agent()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, agent._stop.set)
        except NotImplementedError:  # 非 Unix 平台
            pass
    try:
        await agent.start()
    finally:
        await agent.client.close()


if __name__ == "__main__":
    asyncio.run(main())