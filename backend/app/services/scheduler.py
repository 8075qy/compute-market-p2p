import contextlib
import json
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.core.redis_client import get_redis
from app.core.redis_keys import RedisKeys
from app.models import (
    Account,
    Node,
    NodeStatus,
    NotificationType,
    PlatformConfig,
    Settlement,
    SettlementRole,
    SettlementStatus,
    Task,
    TaskExecution,
    TaskStatus,
    TaskType,
)
from app.schemas.node import NodeHeartbeatRequest
from app.services.audit import AuditService
from app.services.notification import NotificationService
from app.services.settlement import SettlementEngine


async def _get_platform_config(session: AsyncSession) -> PlatformConfig:
    config = await session.get(PlatformConfig, 1)
    if not config:
        config = PlatformConfig()
        session.add(config)
        await session.flush()
    return config


async def _get_account(session: AsyncSession, user_id: uuid.UUID) -> Account:
    account = (
        await session.execute(select(Account).where(Account.user_id == user_id))
    ).scalar_one_or_none()
    if not account:
        raise RuntimeError("账户不存在")
    return account


class TaskScheduler:
    """任务调度器，按固定间隔运行。"""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.redis = get_redis()
        self.audit = AuditService(session)
        self.settlement = SettlementEngine(session)

    async def run(self) -> int:
        """兼容统一入口：执行一次调度循环。"""
        return await self.schedule_pending_tasks()

    async def schedule_pending_tasks(self) -> int:
        config = await _get_platform_config(self.session)
        cutoff = datetime.now(UTC) - timedelta(minutes=config.task_scheduling_timeout_minutes)

        await self._reset_timed_out_tasks(cutoff)

        stmt = (
            select(Task)
            .where(
                Task.status == TaskStatus.SCHEDULING,
                Task.assigned_node_id.is_(None),
            )
            .order_by(Task.created_at)
            .limit(100)
        )
        tasks = (await self.session.execute(stmt)).scalars().all()

        scheduled = 0
        for task in tasks:
            dispatched = await self._dispatch_task(task)
            if dispatched:
                scheduled += 1

        # 无论是否派发成功都提交，确保超时标记、PAUSED 暂停等状态变更持久化
        await self.session.commit()
        return scheduled

    async def _reset_timed_out_tasks(self, cutoff: datetime) -> int:
        """已分配但长时间未开始的任务视为超时，交由重试处理器重新调度。"""
        stmt = (
            select(TaskExecution)
            .join(Task, Task.id == TaskExecution.task_id)
            .where(
                Task.status.in_([TaskStatus.ASSIGNED, TaskStatus.RUNNING]),
                TaskExecution.status.in_([TaskStatus.ASSIGNED, TaskStatus.RUNNING]),
                TaskExecution.started_at.is_(None),
                Task.scheduled_at.is_not(None),
                Task.scheduled_at < cutoff,
            )
            .options(selectinload(TaskExecution.task))
        )
        executions = (await self.session.execute(stmt)).scalars().all()

        now = datetime.now(UTC)
        for execution in executions:
            execution.status = TaskStatus.FAILED
            execution.completed_at = now
            execution.error_message = "调度超时，节点未开始执行"
            await self.audit.log(
                "task.assignment_timeout",
                "task",
                execution.task_id,
                {"execution_id": str(execution.id)},
            )

        return len(executions)

    async def assign_task(self, task: Task) -> Node | None:
        """为任务选择最匹配的在线节点，并标记任务已分配。"""
        node = await self._find_best_node(task)
        if not node:
            return None

        task.assigned_node_id = node.id
        task.status = TaskStatus.ASSIGNED
        task.scheduled_at = datetime.now(UTC)
        task.updated_at = datetime.now(UTC)

        await self.audit.log(
            "task.assigned",
            "task",
            task.id,
            {"node_id": str(node.id), "attempt": task.retry_count + 1},
        )
        await self._notify_node(node.id, task.id)
        await NotificationService(self.session).emit_task_status(task)
        return node

    async def create_execution(
        self,
        task: Task,
        node: Node,
        slice_index: int = 0,
        attempt_no: int | None = None,
    ) -> TaskExecution:
        config = await _get_platform_config(self.session)
        execution = TaskExecution(
            task_id=task.id,
            node_id=node.id,
            slice_index=slice_index,
            attempt_no=attempt_no if attempt_no is not None else task.retry_count + 1,
            status=TaskStatus.ASSIGNED,
            platform_fee_rate=config.platform_fee_rate,
            # 防重放：为每次执行生成唯一挑战种子，绑定 proof_hash，防止缓存结果重复上报
            challenge_nonce=secrets.token_hex(16),
        )
        self.session.add(execution)
        await self.session.flush()
        return execution

    async def _dispatch_task(self, task: Task) -> int:
        """按任务并发度拆分为多个分片，并行派发到多个节点。

        返回本次实际派发的分片数量；返回 0 表示当前无可用节点，任务保持待调度。
        """
        if task.type == TaskType.BATCH:
            # 批处理任务：不按并发分片复制，仅进入「可领取」态，
            # 由 Agent 轮询 pending-executions 时经 Redis 原子游标动态领取工作项区间。
            # 不设置 scheduled_at，避免被「调度超时」逻辑误杀（批处理批次超时回池见 4.4）。
            task.status = TaskStatus.ASSIGNED
            task.updated_at = datetime.now(UTC)
            await self.audit.log(
                "task.assigned",
                "task",
                task.id,
                {"mode": "batch_claim", "total_work_units": task.total_work_units},
            )
            return 1

        concurrency = max(1, task.concurrency or 1)
        nodes = await self._rank_nodes(task, limit=concurrency)
        if not nodes:
            return 0

        # 预授权续冻：逐分片确保额度，余额不足时停止派发新分片（软暂停）
        dispatchable: list[Node] = []
        for node in nodes:
            if not await self.settlement.ensure_preauthorized(
                task, self._preauth_estimate(node)
            ):
                break
            dispatchable.append(node)

        if not dispatchable:
            # 余额不足以覆盖首个分片：暂停任务，等待余额恢复
            task.status = TaskStatus.PAUSED
            task.updated_at = datetime.now(UTC)
            await self.audit.log(
                "task.paused", "task", task.id, {"reason": "balance_insufficient"}
            )
            await NotificationService(self.session).emit_task_status(task)
            return 0

        task.assigned_node_id = dispatchable[0].id
        task.status = TaskStatus.ASSIGNED
        task.scheduled_at = datetime.now(UTC)
        task.updated_at = datetime.now(UTC)

        await self.audit.log(
            "task.assigned",
            "task",
            task.id,
            {
                "node_ids": [str(n.id) for n in dispatchable],
                "slices": len(dispatchable),
                "concurrency": concurrency,
            },
        )

        for slice_index, node in enumerate(dispatchable):
            await self.create_execution(task, node, slice_index=slice_index, attempt_no=1)
            await self._notify_node(node.id, task.id)

        # F1：推送调度完成与进度，需求方页面实时刷新
        notification = NotificationService(self.session)
        await notification.emit_task_status(
            task, {"slices": len(dispatchable), "concurrency": concurrency}
        )
        await notification.create(
            task.demander_id,
            NotificationType.TASK_ASSIGNED,
            "调度完成",
            f"任务 {task.task_no} 已分配到 {len(dispatchable)} 个节点开始执行",
            ref_id=task.id,
        )

        return len(dispatchable)

    async def _rank_nodes(self, task: Task, limit: int | None = None) -> list[Node]:
        """智能评分：显存匹配度 → 模型缓存命中 → 储备贡献率 → 信誉 → 负载 → 算力 → 经验。

        模型缓存命中优先（B2）：已缓存本任务模型的节点在多分片调度中优先，降低 MinIO 重复传输。
        储备贡献率（锁定储备 / 累计收益）越高越优先，实现「贡献越多、取用越优先」的互助排队规则。
        """
        stmt = select(Node).where(
            Node.is_online.is_(True),
            Node.status == NodeStatus.ONLINE,
            (Node.vram_gb * Node.gpu_count) >= task.required_vram_gb,
            Node.reputation_score >= 60,  # noqa: PLR2004
            Node.owner_id != task.demander_id,  # 防自成交：排除需求方自己的节点
        )
        nodes = (await self.session.execute(stmt)).scalars().all()
        if not nodes:
            return []

        owner_ids = {node.owner_id for node in nodes}
        accounts = (
            (await self.session.execute(select(Account).where(Account.user_id.in_(owner_ids))))
            .scalars()
            .all()
        )
        account_map = {account.user_id: account for account in accounts}

        def reserve_contribution(node: Node) -> float:
            account = account_map.get(node.owner_id)
            if not account or account.total_earned <= 0:
                return 0.0
            return account.reserve_points / account.total_earned

        def score(node: Node) -> tuple:
            cache_hit = 1 if self._model_cached(node, task) else 0
            return (
                abs(
                    node.vram_gb * node.gpu_count - task.required_vram_gb
                ),  # 总显存匹配度，越小越好
                -cache_hit,  # 缓存命中节点优先
                -reserve_contribution(node),  # 储备贡献率，越高越优先
                -node.reputation_score,  # 信誉高优先
                float(node.gpu_utilization or 0),  # 负载低优先
                -float((node.peak_tflops or 0) * node.gpu_count),  # 总算力高优先
                -node.total_tasks_completed,  # 经验优先
            )

        ranked = sorted(nodes, key=score)
        if limit is not None:
            ranked = ranked[:limit]
        return ranked

    def _model_cached(self, node: Node, task: Task) -> bool:
        """判断节点缓存列表是否命中任务模型（模型 ID 或 MinIO 对象键）。"""
        cached = node.cached_models
        if not cached:
            return False
        keys = {str(task.model_id), task.model_file_key}
        keys.discard(None)
        return bool(keys and any(k in cached for k in keys))

    def _preauth_estimate(self, node: Node) -> int:
        """单分片预授权预估：节点总算力满载一个预授权窗口的积分。"""
        total_tflops = float((node.peak_tflops or 0) * (node.gpu_count or 1))
        return SettlementEngine.estimate_points(
            total_tflops, get_settings().PREAUTH_MINUTES
        )

    async def _find_best_node(self, task: Task) -> Node | None:
        nodes = await self._rank_nodes(task, limit=1)
        return nodes[0] if nodes else None

    async def scale_out_running_tasks(self) -> int:
        """弹性扩容：为运行中、尚未达到并发上限的任务追加并行分片。"""
        stmt = (
            select(Task)
            .where(
                Task.status.in_([TaskStatus.ASSIGNED, TaskStatus.RUNNING]),
                Task.type != TaskType.BATCH,
            )
            .order_by(Task.created_at)
            .limit(100)
        )
        tasks = (await self.session.execute(stmt)).scalars().all()

        added = 0
        for task in tasks:
            if await self._scale_out_one(task):
                added += 1

        if added:
            await self.session.commit()
        return added

    async def _scale_out_one(self, task: Task) -> bool:
        """为单个任务追加一个分片；返回是否追加成功。"""
        max_concurrency = max(1, task.max_concurrency or task.concurrency)

        max_slice = (
            await self.session.execute(
                select(func.coalesce(func.max(TaskExecution.slice_index), -1)).where(
                    TaskExecution.task_id == task.id
                )
            )
        ).scalar_one()
        dispatched = max_slice + 1  # 已派发分片总数（slice_index 从 0 连续分配）

        if dispatched >= max_concurrency:
            return False

        if await self._remaining_task_budget(task) < (task.min_settlement_unit or 1000):
            return False

        node = await self._pick_new_node(task)
        if not node:
            return False

        # 预授权续冻：余额不足则停止扩容，等待余额恢复（软暂停）
        if not await self.settlement.ensure_preauthorized(
            task, self._preauth_estimate(node)
        ):
            return False

        next_slice = dispatched
        await self.create_execution(task, node, slice_index=next_slice, attempt_no=1)
        await self._notify_node(node.id, task.id)
        task.updated_at = datetime.now(UTC)

        await self.audit.log(
            "task.scale_out",
            "task",
            task.id,
            {
                "slice_index": next_slice,
                "node_id": str(node.id),
                "dispatched": dispatched + 1,
            },
        )

        await NotificationService(self.session).emit_task_status(
            task, {"scale_out": {"slice_index": next_slice, "node_id": str(node.id)}}
        )
        return True

    async def resume_paused_tasks(self) -> int:
        """恢复暂停任务：余额恢复后自动续冻并重新入队；同时检出停滞的批处理任务置暂停。

        返回本次成功恢复的任务数量。
        """
        settings = get_settings()

        # 1) 检出停滞批处理：有剩余工作项、无活跃分片且续冻失败 → 置 PAUSED
        stalled = (
            (
                await self.session.execute(
                    select(Task).where(
                        Task.type == TaskType.BATCH,
                        Task.status.in_([TaskStatus.ASSIGNED, TaskStatus.RUNNING]),
                        Task.total_work_units > 0,
                        Task.completed_work_units < Task.total_work_units,
                    )
                )
            )
            .scalars()
            .all()
        )
        for task in stalled:
            active = (
                await self.session.execute(
                    select(func.count(TaskExecution.id)).where(
                        TaskExecution.task_id == task.id,
                        TaskExecution.status.in_(
                            [TaskStatus.ASSIGNED, TaskStatus.RUNNING]
                        ),
                    )
                )
            ).scalar_one()
            if active > 0:
                continue
            required = SettlementEngine.estimate_points(
                task.required_tflops, settings.PREAUTH_MINUTES
            )
            if not await self.settlement.ensure_preauthorized(task, required):
                task.status = TaskStatus.PAUSED
                task.updated_at = datetime.now(UTC)
                await self.audit.log(
                    "task.paused", "task", task.id, {"reason": "balance_insufficient"}
                )
                await NotificationService(self.session).emit_task_status(task)

        # 2) 恢复暂停中的任务
        paused = (
            (
                await self.session.execute(
                    select(Task)
                    .where(Task.status == TaskStatus.PAUSED)
                    .order_by(Task.updated_at)
                    .limit(100)
                )
            )
            .scalars()
            .all()
        )
        resumed = 0
        for task in paused:
            required = SettlementEngine.estimate_points(
                task.required_tflops, settings.PREAUTH_MINUTES
            )
            if not await self.settlement.ensure_preauthorized(task, required):
                continue
            if task.type == TaskType.BATCH:
                task.status = TaskStatus.ASSIGNED
            else:
                task.status = TaskStatus.SCHEDULING
                with contextlib.suppress(Exception):
                    await self.redis.lpush(
                        RedisKeys.TASK_SCHEDULING_QUEUE, str(task.id)
                    )
            task.updated_at = datetime.now(UTC)
            await self.audit.log(
                "task.resumed", "task", task.id, {"reason": "balance_restored"}
            )
            await NotificationService(self.session).emit_task_status(task)
            resumed += 1

        await self.session.commit()
        return resumed

    async def _remaining_task_budget(self, task: Task) -> int:
        """任务剩余可结算预算：总预算减去已结算额，并受预授权额度约束。"""
        already_settled = (
            await self.session.execute(
                select(func.coalesce(func.sum(TaskExecution.compute_points), 0)).where(
                    TaskExecution.task_id == task.id,
                    TaskExecution.status == TaskStatus.COMPLETED,
                )
            )
        ).scalar_one() or 0
        budget_remaining = max(0, task.budget_points - already_settled)
        preauth_remaining = max(0, task.preauthorized_points - already_settled)
        return min(budget_remaining, preauth_remaining)

    async def _pick_new_node(self, task: Task) -> Node | None:
        """选新节点：排除该任务当前活跃分片所在节点，避免同节点重复分片。"""
        busy_node_ids = (
            (
                await self.session.execute(
                    select(TaskExecution.node_id).where(
                        TaskExecution.task_id == task.id,
                        TaskExecution.status.in_([TaskStatus.ASSIGNED, TaskStatus.RUNNING]),
                    )
                )
            )
            .scalars()
            .all()
        )
        busy = set(busy_node_ids)

        for node in await self._rank_nodes(task):
            if node.id not in busy:
                return node
        return None

    async def scale_in_lagging_tasks(self) -> int:
        """弹性缩容：检测并终止滞后分片，做部分结算、释放节点。

        滞后判定：运行中分片的运行时长超过阈值，且同任务已有分片完成（任务接近尾声）。
        终止方式：复用结算引擎按实际运行时长做部分结算，分片标记 COMPLETED，不影响任务收尾。
        """
        settings = get_settings()
        lag_cutoff = datetime.now(UTC) - timedelta(seconds=settings.SCALE_IN_LAG_SECONDS)

        stmt = (
            select(TaskExecution)
            .join(Task, Task.id == TaskExecution.task_id)
            .where(
                Task.status == TaskStatus.RUNNING,
                Task.type != TaskType.BATCH,
                TaskExecution.status == TaskStatus.RUNNING,
                TaskExecution.started_at.is_not(None),
                TaskExecution.started_at < lag_cutoff,
            )
            .options(selectinload(TaskExecution.task), selectinload(TaskExecution.node))
        )
        lagging = (await self.session.execute(stmt)).scalars().all()

        scaled_in = 0
        for execution in lagging:
            if await self._scale_in_one(execution):
                scaled_in += 1
        return scaled_in

    async def _scale_in_one(self, execution: TaskExecution) -> bool:
        """终止单个滞后分片；任务尚无分片完成时跳过，避免误杀正常长任务。"""
        task = execution.task
        if not task:
            return False

        completed_count = (
            await self.session.execute(
                select(func.count(TaskExecution.id)).where(
                    TaskExecution.task_id == task.id,
                    TaskExecution.status == TaskStatus.COMPLETED,
                )
            )
        ).scalar_one()
        if completed_count == 0:
            return False

        now = datetime.now(UTC)
        execution.completed_at = now
        started = execution.started_at
        if started and started.tzinfo is None:
            started = started.replace(tzinfo=UTC)
        if started:
            execution.compute_duration_seconds = max(0, int((now - started).total_seconds()))
        execution.error_message = "弹性缩容：分片滞后，提前终止并部分结算"
        # 先持久化字段，避免结算引擎 refresh 时覆盖内存中的改动
        await self.session.flush()

        await self.audit.log(
            "task.scale_in",
            "task",
            task.id,
            {
                "execution_id": str(execution.id),
                "slice_index": execution.slice_index or 0,
                "compute_duration_seconds": execution.compute_duration_seconds,
            },
        )

        # 复用结算引擎：按运行时长部分结算，分片标记 COMPLETED，节点随之释放
        await self.settlement.settle_execution(execution)
        return True

    async def _assign_task_to_node(self, task: Task, node: Node) -> None:
        """兼容旧调用：分配并创建执行记录。"""
        await self.assign_task(task)
        await self.create_execution(task, node)
        await self.session.commit()

    async def _notify_node(self, _node_id: uuid.UUID, task_id: uuid.UUID) -> None:
        """节点通过心跳轮询获取任务，这里保留扩展点。"""
        # Redis 不可用不应阻塞调度
        with contextlib.suppress(Exception):
            await self.redis.lpush(RedisKeys.TASK_SCHEDULING_QUEUE, str(task_id))


class NodeHeartbeatService:
    """节点心跳监控与离线检测。"""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.audit = AuditService(session)

    async def heartbeat(self, node_id: uuid.UUID, data: NodeHeartbeatRequest) -> Node:
        node = await self.session.get(Node, node_id)
        if not node:
            raise RuntimeError("节点不存在")

        now = datetime.now(UTC)
        was_online = node.is_online
        node.last_heartbeat_at = now
        node.is_online = True
        node.status = NodeStatus.ONLINE
        node.updated_at = now
        node.gpu_utilization = data.gpu_util if data.gpu_util is not None else data.gpu_utilization
        node.vram_used_gb = data.vram_used_gb
        node.temp_c = data.temp_c if data.temp_c is not None else data.temperature
        if data.cached_models is not None:
            node.cached_models_json = json.dumps(data.cached_models, ensure_ascii=False)

        # F1：离线节点恢复心跳时推送上线事件
        if not was_online:
            notification = NotificationService(self.session)
            await notification.emit_node_status(node)
            await notification.create(
                node.owner_id,
                NotificationType.NODE_ONLINE,
                "节点已上线",
                f"节点 {node.name} 心跳恢复，已重新上线接单",
                ref_id=node.id,
            )

        await self.session.commit()
        await self.session.refresh(node)
        return node

    async def check_offline_nodes(self) -> int:
        config = await _get_platform_config(self.session)
        threshold = datetime.now(UTC) - timedelta(minutes=config.node_offline_threshold_minutes)

        stmt = select(Node).where(
            Node.last_heartbeat_at.is_not(None),
            Node.last_heartbeat_at < threshold,
            Node.is_online.is_(True),
            Node.status == NodeStatus.ONLINE,
        )
        nodes = (await self.session.execute(stmt)).scalars().all()

        now = datetime.now(UTC)
        for node in nodes:
            node.is_online = False
            node.status = NodeStatus.OFFLINE
            node.updated_at = now
            await self.audit.log(
                "node.auto_offline",
                "node",
                node.id,
                {"reason": "heartbeat_timeout"},
            )
            await self._reassign_node_tasks(node.id)

            # F1：推送节点下线事件并通知机主
            notification = NotificationService(self.session)
            await notification.emit_node_status(node, reason="heartbeat_timeout")
            await notification.create(
                node.owner_id,
                NotificationType.NODE_OFFLINE,
                "节点已离线",
                f"节点 {node.name} 心跳超时已离线，正在执行的调度将重新分配",
                ref_id=node.id,
            )

        if nodes:
            await self.session.commit()
        return len(nodes)

    async def _reassign_node_tasks(self, node_id: uuid.UUID) -> None:
        """将节点上尚未开始的执行标记为失败，由重试处理器重新调度。"""
        stmt = (
            select(TaskExecution)
            .join(Task, Task.id == TaskExecution.task_id)
            .where(
                TaskExecution.node_id == node_id,
                TaskExecution.status == TaskStatus.ASSIGNED,
                Task.status.in_([TaskStatus.ASSIGNED, TaskStatus.RUNNING]),
            )
        )
        executions = (await self.session.execute(stmt)).scalars().all()

        now = datetime.now(UTC)
        for execution in executions:
            execution.status = TaskStatus.FAILED
            execution.completed_at = now
            execution.error_message = "节点离线，任务重新调度"
            await self.audit.log(
                "task.reassigned",
                "task",
                execution.task_id,
                {"reason": "node_offline", "node_id": str(node_id)},
            )


class TaskRetryHandler:
    """失败任务重试处理。"""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.audit = AuditService(session)
        self.settlement = SettlementEngine(session)
        self.redis = get_redis()

    async def handle_failed_executions(self) -> int:
        stmt = (
            select(TaskExecution)
            .join(Task, Task.id == TaskExecution.task_id)
            .where(
                TaskExecution.status == TaskStatus.FAILED,
                TaskExecution.completed_at.is_not(None),
                Task.status.in_([TaskStatus.ASSIGNED, TaskStatus.RUNNING]),
            )
            .options(
                selectinload(TaskExecution.task),
                selectinload(TaskExecution.node),
            )
        )
        failed_executions = (await self.session.execute(stmt)).scalars().all()

        handled = 0
        for execution in failed_executions:
            await self._handle_one(execution)
            handled += 1

        if handled:
            await self.session.commit()
        return handled

    async def handle_failed_execution(self, execution: TaskExecution) -> None:
        await self.session.refresh(execution, ["task", "node"])
        await self._handle_one(execution)
        await self.session.commit()

    async def _handle_one(self, execution: TaskExecution) -> None:
        task = execution.task
        if not task:
            return
        if task.status not in (TaskStatus.ASSIGNED, TaskStatus.RUNNING):
            return

        concurrency = max(1, task.concurrency or 1)
        if concurrency > 1:
            await self._handle_parallel_failure(task, execution)
        else:
            max_retries = task.max_retries if task.max_retries is not None else 3
            if task.retry_count >= max_retries:
                await self._fail_task_permanently(task, execution)
            else:
                await self._retry_task(task, execution)

    async def _handle_parallel_failure(self, task: Task, execution: TaskExecution) -> None:
        """并行分片失败：仅重试失败分片，其余分片继续执行；分片耗尽重试则整体失败。"""
        max_retries = task.max_retries if task.max_retries is not None else 3
        slice_index = execution.slice_index or 0

        if execution.attempt_no < max_retries:
            node = await self._pick_node(task)
            if not node:
                # 暂无可用节点，保持失败状态，等待下一轮重试处理器再次调度
                return

            scheduler = TaskScheduler(self.session)
            await scheduler.create_execution(
                task,
                node,
                slice_index=slice_index,
                attempt_no=execution.attempt_no + 1,
            )
            task.retry_count += 1
            task.updated_at = datetime.now(UTC)
            await self.audit.log(
                "task.slice_retry",
                "task",
                task.id,
                {
                    "slice_index": slice_index,
                    "failed_attempt": execution.attempt_no,
                    "next_attempt": execution.attempt_no + 1,
                    "node_id": str(node.id),
                    "reason": execution.error_message,
                },
            )
        else:
            await self._fail_task_permanently(task, execution)

    async def _pick_node(self, task: Task) -> Node | None:
        scheduler = TaskScheduler(self.session)
        return await scheduler._find_best_node(task)

    async def _retry_task(self, task: Task, failed_exec: TaskExecution) -> None:
        task.retry_count += 1
        task.assigned_node_id = None
        task.status = TaskStatus.SCHEDULING
        task.scheduled_at = None
        task.started_at = None
        task.error_message = failed_exec.error_message
        task.updated_at = datetime.now(UTC)

        await self.audit.log(
            "task.retry_scheduled",
            "task",
            task.id,
            {
                "failed_attempt": failed_exec.attempt_no,
                "next_attempt": task.retry_count + 1,
                "reason": failed_exec.error_message,
            },
        )
        with contextlib.suppress(Exception):
            await self.redis.lpush(RedisKeys.TASK_SCHEDULING_QUEUE, str(task.id))

        # F1：推送重新调度状态
        await NotificationService(self.session).emit_task_status(
            task, {"reason": failed_exec.error_message}
        )

    async def _fail_task_permanently(self, task: Task, last_exec: TaskExecution) -> None:
        task.status = TaskStatus.FAILED
        task.completed_at = datetime.now(UTC)
        task.error_message = (
            f"超过最大重试次数({task.max_retries})，最后错误: {last_exec.error_message}"
        )
        task.updated_at = datetime.now(UTC)

        # 并行任务：中止仍在执行的其余分片，避免其后续再结算造成重复支出
        in_flight = (
            (
                await self.session.execute(
                    select(TaskExecution).where(
                        TaskExecution.task_id == task.id,
                        TaskExecution.status.in_([TaskStatus.ASSIGNED, TaskStatus.RUNNING]),
                    )
                )
            )
            .scalars()
            .all()
        )
        for sl in in_flight:
            sl.status = TaskStatus.FAILED
            sl.completed_at = datetime.now(UTC)
            sl.error_message = "任务整体失败，分片已中止"

        account = await _get_account(self.session, task.demander_id)

        # 已结算的分片不再退还，仅退还未结算预算，避免与已付供给方重复支出
        already_settled = (
            await self.session.execute(
                select(func.coalesce(func.sum(TaskExecution.compute_points), 0)).where(
                    TaskExecution.task_id == task.id,
                    TaskExecution.status == TaskStatus.COMPLETED,
                )
            )
        ).scalar_one() or 0

        frozen = min(task.preauthorized_points, account.frozen_points)
        refund = max(0, min(frozen, task.preauthorized_points - already_settled))
        account.frozen_points -= frozen
        account.balance_points += refund

        if refund > 0:
            self.session.add(
                Settlement(
                    settlement_no=f"R{datetime.now(UTC).strftime('%Y%m%d')}{task.id.hex[:8]}",
                    user_id=task.demander_id,
                    task_id=task.id,
                    execution_id=last_exec.id,
                    role=SettlementRole.DEMANDER,
                    compute_points=0,
                    platform_fee_rate=last_exec.platform_fee_rate,
                    platform_fee_points=0,
                    net_points=refund,
                    destination_account="原路退回",
                    status=SettlementStatus.REFUNDED,
                    settled_at=datetime.now(UTC),
                )
            )

        await self.audit.log(
            "task.failed_permanently",
            "task",
            task.id,
            {
                "total_retries": task.retry_count,
                "refunded_points": refund,
                "already_settled_points": already_settled,
            },
        )

        # F3：通知需求方任务失败
        notification = NotificationService(self.session)
        await notification.create(
            task.demander_id,
            NotificationType.TASK_FAILED,
            "任务失败",
            f"任务 {task.task_no} 执行失败：{task.error_message}",
            ref_id=task.id,
        )
        # F1：推送失败状态
        await notification.emit_task_status(task)
