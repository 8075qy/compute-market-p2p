"""节点执行闭环服务：领取待执行分片、上报开始/完成/失败，驱动结算与重试。"""
import json
import secrets
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.core.exceptions import BusinessError, NotFoundError
from app.core.redis_client import get_redis
from app.core.redis_keys import RedisKeys
from app.models import (
    Node,
    NotificationType,
    Task,
    TaskExecution,
    TaskStatus,
    TaskType,
)
from app.schemas.node import ExecutionCompleteRequest
from app.services.audit import AuditService
from app.services.batch_input import manifest_key_for
from app.services.notification import NotificationService
from app.services.scheduler import TaskRetryHandler
from app.services.settlement import SettlementEngine
from app.services.verification import VerificationService


class ExecutionService:
    """供给方节点执行端的闭环接口业务层。"""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.audit = AuditService(session)
        self.settlement = SettlementEngine(session)

    async def _get_owned_execution(
        self, execution_id: uuid.UUID, user_id: uuid.UUID
    ) -> TaskExecution:
        """校验执行记录归属：执行记录的节点必须属于当前用户。"""
        stmt = (
            select(TaskExecution)
            .join(Node, Node.id == TaskExecution.node_id)
            .where(TaskExecution.id == execution_id, Node.owner_id == user_id)
            .options(
                selectinload(TaskExecution.task),
                selectinload(TaskExecution.node),
            )
        )
        execution = (await self.session.execute(stmt)).scalar_one_or_none()
        if not execution:
            raise NotFoundError("执行记录不存在或无权访问")
        return execution

    async def get_pending_executions(
        self, node_id: uuid.UUID, user_id: uuid.UUID
    ) -> list[dict]:
        """拉取分配给该节点的待执行分片（ASSIGNED 状态），并动态领取一个批处理批次。"""
        node = await self.session.get(Node, node_id)
        if not node or node.owner_id != user_id:
            raise NotFoundError("节点不存在或无权访问")

        # 动态领取一个批处理批次（拉取式分配：轮询即领取，Redis 原子游标切分工作项区间）
        claimed = await self._claim_batch_work(node)
        if claimed is not None:
            await self.session.commit()

        stmt = (
            select(TaskExecution)
            .where(
                TaskExecution.node_id == node_id,
                TaskExecution.status == TaskStatus.ASSIGNED,
            )
            .options(selectinload(TaskExecution.task))
            .order_by(TaskExecution.created_at)
        )
        executions = (await self.session.execute(stmt)).scalars().all()

        result: list[dict] = []
        for e in executions:
            task = e.task
            env_vars = dict(task.env_vars) if task else {}
            # 防重放：注入本次执行的挑战种子，Agent 据此使结果唯一化并绑定 proof_hash
            env_vars["PROOF_NONCE"] = e.challenge_nonce or ""
            result.append(
                {
                    "execution_id": e.id,
                    "task_id": e.task_id,
                    "task_no": task.task_no if task else None,
                    "slice_index": e.slice_index or 0,
                    "attempt_no": e.attempt_no,
                    "model_source": task.model_source if task else "",
                    "model_id": task.model_id if task else None,
                    "model_file_key": task.model_file_key if task else None,
                    "model_file_size": task.model_file_size if task else None,
                    "params": task.params if task else {},
                    "command": task.command if task else None,
                    "env_vars": env_vars,
                    "challenge_nonce": e.challenge_nonce or "",
                    "timeout_minutes": task.timeout_minutes if task else 60,
                    "docker_image": (
                        task.docker_image if task and task.docker_image else node.docker_image
                    ),
                    "work_unit_start": e.work_unit_start,
                    "work_unit_end": e.work_unit_end,
                    "input_file_key": task.input_file_key if task else None,
                    "manifest_key": (
                        manifest_key_for(task.input_file_key)
                        if task and task.input_file_key
                        else None
                    ),
                    "created_at": e.created_at,
                }
            )
        return result

    async def _claim_batch_work(self, node: Node) -> TaskExecution | None:
        """为节点动态领取一个批处理批次，即时生成一条 ASSIGNED 执行记录。

        采用 Redis 原子游标 INCRBY 切分半开区间 [start, end)，保证并发领取不重叠、
        区间连续覆盖 [0, total_work_units)。每批大小 K 取值：batch_size > 0 用之，
        否则按节点算力档位取默认值（单卡 / 整机）。无剩余工作项时返回 None。
        """
        settings = get_settings()
        stmt = (
            select(Task)
            .where(
                Task.type == TaskType.BATCH,
                Task.status.in_([TaskStatus.ASSIGNED, TaskStatus.RUNNING]),
                Task.total_work_units > 0,
            )
            .order_by(Task.created_at)
        )
        tasks = (await self.session.execute(stmt)).scalars().all()

        redis = get_redis()
        for task in tasks:
            total = task.total_work_units
            if total is None or total <= 0:
                continue

            cursor_key = RedisKeys.BATCH_CURSOR.format(task_id=task.id)
            # 快速预判：已分配完的任务跳过，避免游标无界增长
            cursor = int(await redis.get(cursor_key) or 0)
            if cursor >= total:
                continue

            if task.batch_size > 0:
                batch_size = task.batch_size
            elif node.gpu_count > 1:
                batch_size = settings.BATCH_SIZE_MULTI_GPU
            else:
                batch_size = settings.BATCH_SIZE_SINGLE_GPU

            # 原子领取：INCRBY 返回递增后的值，减去 K 得到区间起点
            start = await redis.incrby(cursor_key, batch_size) - batch_size
            if start >= total:
                # 并发下已被其他节点抢完
                continue
            end = min(start + batch_size, total)

            # 预授权续冻：余额不足则跳过该批处理任务，等待余额恢复（软暂停）
            required = SettlementEngine.estimate_points(
                float((node.peak_tflops or 0) * (node.gpu_count or 1)),
                settings.PREAUTH_MINUTES,
            )
            if not await self.settlement.ensure_preauthorized(task, required):
                continue

            execution = TaskExecution(
                task_id=task.id,
                node_id=node.id,
                # 批处理按工作项起点作为分片索引，保证 (task_id, slice_index, attempt_no) 唯一
                slice_index=start,
                attempt_no=1,
                status=TaskStatus.ASSIGNED,
                work_unit_start=start,
                work_unit_end=end,
                platform_fee_rate=settings.DEFAULT_PLATFORM_FEE_RATE,
                challenge_nonce=secrets.token_hex(16),
            )
            self.session.add(execution)
            await self.session.flush()

            # 任务从「可领取」态进入运行态
            if task.status == TaskStatus.ASSIGNED:
                task.status = TaskStatus.RUNNING
                task.started_at = datetime.now(UTC)
            task.updated_at = datetime.now(UTC)

            await self.audit.log(
                "batch.claimed",
                "execution",
                execution.id,
                {
                    "task_id": str(task.id),
                    "node_id": str(node.id),
                    "work_unit_start": start,
                    "work_unit_end": end,
                },
                user_id=node.owner_id,
            )
            return execution
        return None

    async def start_execution(
        self, execution_id: uuid.UUID, user_id: uuid.UUID
    ) -> TaskExecution:
        """上报执行开始：ASSIGNED → RUNNING。"""
        execution = await self._get_owned_execution(execution_id, user_id)
        if execution.status == TaskStatus.COMPLETED:
            raise BusinessError("执行记录已完成，无法重复开始")
        if execution.status != TaskStatus.ASSIGNED:
            raise BusinessError(f"当前状态({execution.status.value})无法开始执行")

        now = datetime.now(UTC)
        execution.status = TaskStatus.RUNNING
        execution.started_at = now
        execution.updated_at = now
        if execution.task and execution.task.status == TaskStatus.ASSIGNED:
            execution.task.status = TaskStatus.RUNNING
            execution.task.started_at = now
            execution.task.updated_at = now

        await self.audit.log(
            "execution.started",
            "execution",
            execution.id,
            {"node_id": str(execution.node_id)},
            user_id=user_id,
        )
        # F1：推送任务进入运行状态
        if execution.task:
            notification = NotificationService(self.session)
            await notification.emit_task_status(execution.task)
            await notification.create(
                execution.task.demander_id,
                NotificationType.TASK_STARTED,
                "任务开始执行",
                f"任务 {execution.task.task_no} 已由节点开始执行",
                ref_id=execution.task.id,
            )
        await self.session.commit()
        await self.session.refresh(execution)
        return execution

    def _clamp_duration(
        self, execution: TaskExecution, reported_seconds: int
    ) -> int:
        """算力时长上限截断：上报时长不得超过「开始到现在的墙钟时间」，防止虚报时长多结算。"""
        reported = max(0, int(reported_seconds))
        started_at = execution.started_at
        if started_at:
            # SQLite 读取时区字段会丢失 tzinfo（值为 UTC），统一补齐时区再计算
            if started_at.tzinfo is None:
                started_at = started_at.replace(tzinfo=UTC)
            elapsed = max(
                0,
                int((datetime.now(UTC) - started_at).total_seconds()),
            )
            return min(reported, elapsed)
        return reported

    async def complete_execution(
        self,
        execution_id: uuid.UUID,
        user_id: uuid.UUID,
        data: ExecutionCompleteRequest,
    ) -> TaskExecution:
        """上报完成：写入结果与证明 → 触发结算。"""
        execution = await self._get_owned_execution(execution_id, user_id)
        if execution.status == TaskStatus.COMPLETED:
            raise BusinessError("执行记录已完成，请勿重复上报")
        if execution.status != TaskStatus.RUNNING:
            raise BusinessError(f"当前状态({execution.status.value})无法完成")

        if data.result_files and not data.proof_hash:
            raise BusinessError("缺少算力证明(proof_hash)，请提供结果内容哈希")

        execution.proof_hash = data.proof_hash
        if data.compute_duration_seconds is not None:
            execution.compute_duration_seconds = self._clamp_duration(
                execution, data.compute_duration_seconds
            )
        if data.execution_log_key:
            execution.execution_log_key = data.execution_log_key

        # 结果文件按分片追加到任务 result_files_json（按 key 去重），最终统一返回给需求方
        if data.result_files and execution.task:
            task = execution.task
            try:
                files = json.loads(task.result_files_json) if task.result_files_json else []
            except (TypeError, ValueError):
                files = []
            existing_keys = {f.get("key") for f in files if isinstance(f, dict)}
            for f in data.result_files:
                if isinstance(f, dict) and f.get("key") and f["key"] not in existing_keys:
                    files.append(f)
                    existing_keys.add(f["key"])
            task.result_files_json = json.dumps(files, ensure_ascii=False)

        # 批处理批次：累计完成的工作项数到任务（幂等：重复上报已在入口拦截）
        if execution.work_unit_start is not None and execution.work_unit_end is not None:
            completed = data.completed_work_units
            if completed is None:
                completed = execution.work_unit_end - execution.work_unit_start
            execution.completed_work_units = max(0, int(completed))
            if execution.task:
                execution.task.completed_work_units += execution.completed_work_units

        # 先落库再结算：settle_execution 内部会 refresh 执行记录，避免未落库字段被覆盖
        await self.session.flush()
        await self.settlement.settle_execution(execution)
        await self.session.refresh(execution)

        # D1 第二阶段：结算完成后按比例随机抽样进入复核
        await VerificationService(self.session).maybe_sample(execution, data.result_files)
        return execution

    async def fail_execution(
        self, execution_id: uuid.UUID, user_id: uuid.UUID, error_message: str
    ) -> TaskExecution:
        """上报失败：标记 FAILED → 触发分片重试。"""
        execution = await self._get_owned_execution(execution_id, user_id)
        if execution.status not in (TaskStatus.ASSIGNED, TaskStatus.RUNNING):
            raise BusinessError(f"当前状态({execution.status.value})无法标记失败")

        now = datetime.now(UTC)
        execution.status = TaskStatus.FAILED
        execution.completed_at = now
        execution.error_message = error_message or "节点执行失败"
        execution.updated_at = now

        await self.audit.log(
            "execution.failed",
            "execution",
            execution.id,
            {"reason": execution.error_message},
            user_id=user_id,
        )
        # 落库后触发重试：批处理批次按区间回退待分配池，其余走既有重试处理器
        await self.session.flush()
        if execution.work_unit_start is not None and execution.work_unit_end is not None:
            await self._requeue_batch_execution(execution, user_id)
            await self.session.commit()
        else:
            retry = TaskRetryHandler(self.session)
            await retry.handle_failed_execution(execution)
        await self.session.refresh(execution)
        return execution

    async def _requeue_batch_execution(
        self, execution: TaskExecution, user_id: uuid.UUID
    ) -> None:
        """批处理批次失败回池：按原区间重新生成一条 ASSIGNED 执行记录（attempt_no+1）。

        工作项区间不变，仅尝试次数递增，保证该批次负责的工作项能被重新领取并完成；
        超过任务最大重试次数后保持 FAILED，避免无限回池。
        """
        task = execution.task
        if not task:
            return
        max_retries = task.max_retries if task.max_retries is not None else 3
        if execution.attempt_no >= max_retries:
            return

        retry_execution = TaskExecution(
            task_id=execution.task_id,
            node_id=execution.node_id,
            slice_index=execution.work_unit_start,
            attempt_no=execution.attempt_no + 1,
            status=TaskStatus.ASSIGNED,
            work_unit_start=execution.work_unit_start,
            work_unit_end=execution.work_unit_end,
            platform_fee_rate=execution.platform_fee_rate,
            challenge_nonce=secrets.token_hex(16),
        )
        self.session.add(retry_execution)
        await self.session.flush()

        await self.audit.log(
            "batch.requeued",
            "execution",
            retry_execution.id,
            {
                "task_id": str(task.id),
                "node_id": str(execution.node_id),
                "work_unit_start": execution.work_unit_start,
                "work_unit_end": execution.work_unit_end,
                "previous_attempt": execution.attempt_no,
                "next_attempt": execution.attempt_no + 1,
            },
            user_id=user_id,
        )
