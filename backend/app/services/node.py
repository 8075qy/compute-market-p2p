import json
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.core.exceptions import BusinessError, NotFoundError
from app.core.redis_client import get_redis
from app.core.redis_keys import RedisKeys
from app.models import BenchmarkStatus, Node, NodeStatus, TaskExecution, TaskStatus, User
from app.schemas.node import BenchmarkReportRequest, NodeCreate, NodeHeartbeatRequest, NodeUpdate
from app.services.audit import AuditService
from app.services.gpu_spec import GpuSpecService


class NodeService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.redis = get_redis()
        self.audit = AuditService(session)

    async def create_node(self, user_id: uuid.UUID, data: NodeCreate) -> Node:
        user = await self.session.get(User, user_id)
        if not user:
            raise NotFoundError("用户不存在")

        # 女巫攻击检测（P2-7）：单账号注册节点数超上限视为批量刷供给
        max_nodes_per_user = get_settings().MAX_NODES_PER_USER
        owned_count = (
            await self.session.execute(select(func.count(Node.id)).where(Node.owner_id == user_id))
        ).scalar_one()
        if owned_count >= max_nodes_per_user:
            raise BusinessError(f"单账号注册节点数已达上限（{max_nodes_per_user}），疑似女巫攻击")

        # 防多开（P1-5）：同一 GPU 唯一标识（gpu_uuid）允许注册的节点数受限
        if data.gpu_uuid:
            max_nodes = get_settings().MAX_NODES_PER_GPU
            existing_count = (
                await self.session.execute(
                    select(func.count(Node.id)).where(Node.gpu_uuid == data.gpu_uuid)
                )
            ).scalar_one()
            if existing_count >= max_nodes:
                raise BusinessError(f"该 GPU 已注册节点数达到上限（{max_nodes}），疑似多开")

        # 硬件谎报检测（P1-4）：登记算力需与规格库标称值一致，超出容差视为谎报
        tolerance_pct = get_settings().GPU_SPEC_TFLOPS_TOLERANCE_PCT
        spec = await GpuSpecService(self.session).match(data.gpu_model)
        if spec and data.peak_tflops > float(spec.peak_tflops) * (1 + tolerance_pct / 100):
            raise BusinessError("登记的峰值算力超出该 GPU 型号官方标称值，疑似谎报")

        node = Node(
            owner_id=user_id,
            name=data.name,
            gpu_model=data.gpu_model,
            vram_gb=data.vram_gb,
            peak_tflops=data.peak_tflops,
            gpu_count=data.gpu_count,
            region_province=data.region_province,
            region_city=data.region_city,
            region_district=data.region_district,
            docker_image=data.docker_image,
            config_json=data.config_json,
            gpu_uuid=data.gpu_uuid,
        )
        self.session.add(node)
        await self.session.flush()

        await self.audit.log(
            "node.created",
            "node",
            node.id,
            {
                "name": node.name,
                "gpu_model": node.gpu_model,
                "vram_gb": node.vram_gb,
                "gpu_uuid": node.gpu_uuid,
            },
            user_id=user_id,
        )

        await self.session.commit()
        await self.session.refresh(node)
        return node

    async def get_nodes(
        self,
        user_id: uuid.UUID,
        page: int = 1,
        page_size: int = 20,
        status: NodeStatus | None = None,
    ) -> tuple[list[Node], int]:
        stmt = select(Node).where(Node.owner_id == user_id)
        if status:
            stmt = stmt.where(Node.status == status)

        # 总数
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await self.session.execute(count_stmt)).scalar_one()

        # 分页
        stmt = stmt.order_by(Node.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        result = await self.session.execute(stmt)
        nodes = result.scalars().all()

        return list(nodes), total

    async def get_marketplace_nodes(
        self, page: int = 1, page_size: int = 20
    ) -> tuple[list[Node], int]:
        """算力市场：列出所有在线共享节点，按信誉分与最近心跳排序。"""
        stmt = (
            select(Node)
            .options(selectinload(Node.owner))
            .where(Node.status == NodeStatus.ONLINE, Node.is_online.is_(True))
        )

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await self.session.execute(count_stmt)).scalar_one()

        stmt = (
            stmt.order_by(Node.reputation_score.desc(), Node.last_heartbeat_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await self.session.execute(stmt)
        nodes = result.scalars().all()

        return list(nodes), total

    async def get_node(self, node_id: uuid.UUID, user_id: uuid.UUID) -> Node:
        stmt = select(Node).where(Node.id == node_id, Node.owner_id == user_id)
        result = await self.session.execute(stmt)
        node = result.scalar_one_or_none()
        if not node:
            raise NotFoundError("节点不存在")
        return node

    async def update_node(self, node_id: uuid.UUID, user_id: uuid.UUID, data: NodeUpdate) -> Node:
        node = await self.get_node(node_id, user_id)

        update_data = data.model_dump(exclude_unset=True)
        cached_models = update_data.pop("cached_models", None)
        if cached_models is not None:
            node.cached_models_json = json.dumps(cached_models, ensure_ascii=False)

        hardware_changed = (
            ("gpu_model" in update_data and update_data["gpu_model"] != node.gpu_model)
            or ("vram_gb" in update_data and update_data["vram_gb"] != node.vram_gb)
            or ("gpu_count" in update_data and update_data["gpu_count"] != node.gpu_count)
            or (
                "peak_tflops" in update_data
                and float(update_data["peak_tflops"]) != float(node.peak_tflops)
            )
        )

        for key, value in update_data.items():
            setattr(node, key, value)

        # 硬件关键规格变更后，原对标结果失效，需重新对标（防止谎报后改小算力绕过校验）
        if hardware_changed:
            node.benchmark_status = BenchmarkStatus.PENDING
            node.benchmark_tflops = None
            node.benchmarked_at = None

        node.updated_at = datetime.now(UTC)
        await self.session.commit()
        await self.session.refresh(node)
        return node

    async def report_benchmark(
        self, node_id: uuid.UUID, user_id: uuid.UUID, data: BenchmarkReportRequest
    ) -> Node:
        """算力对标（P1-4）：上报实测算力，与登记值交叉验证，谎报标记 failed 并扣信誉分。"""
        node = await self.get_node(node_id, user_id)
        tolerance_pct = get_settings().GPU_SPEC_TFLOPS_TOLERANCE_PCT
        now = datetime.now(UTC)
        node.benchmark_tflops = data.benchmark_tflops
        node.benchmarked_at = now

        if float(node.peak_tflops) > data.benchmark_tflops * (1 + tolerance_pct / 100):
            node.benchmark_status = BenchmarkStatus.FAILED
            node.reputation_score = max(0, node.reputation_score - 10)
            await self.audit.log(
                "node.benchmark_failed",
                "node",
                node_id,
                {
                    "claimed_tflops": float(node.peak_tflops),
                    "benchmark_tflops": data.benchmark_tflops,
                },
                user_id=user_id,
            )
        else:
            node.benchmark_status = BenchmarkStatus.VERIFIED
            await self.audit.log(
                "node.benchmark_verified",
                "node",
                node_id,
                {
                    "claimed_tflops": float(node.peak_tflops),
                    "benchmark_tflops": data.benchmark_tflops,
                },
                user_id=user_id,
            )

        node.updated_at = now
        await self.session.commit()
        await self.session.refresh(node)
        return node

    async def set_online(self, node_id: uuid.UUID, user_id: uuid.UUID) -> Node:
        node = await self.get_node(node_id, user_id)
        if node.status == NodeStatus.MAINTENANCE:
            raise BusinessError("维护状态节点无法上线")

        node.status = NodeStatus.ONLINE
        node.is_online = True
        node.last_heartbeat_at = None
        node.updated_at = datetime.now(UTC)

        # Redis 标记在线
        await self.redis.setex(RedisKeys.NODE_ONLINE_FLAG.format(node_id=node_id), 360, "1")
        await self.redis.zadd(
            RedisKeys.NODE_HEARTBEAT_ZSET, {str(node_id): datetime.now(UTC).timestamp()}
        )

        await self.audit.log("node.online", "node", node_id, {}, user_id=user_id)
        await self.session.commit()
        await self.session.refresh(node)
        return node

    async def set_offline(self, node_id: uuid.UUID, user_id: uuid.UUID) -> Node:
        node = await self.get_node(node_id, user_id)
        node.status = NodeStatus.OFFLINE
        node.is_online = False
        node.updated_at = datetime.now(UTC)

        await self.redis.delete(RedisKeys.NODE_ONLINE_FLAG.format(node_id=node_id))
        await self.redis.zrem(RedisKeys.NODE_HEARTBEAT_ZSET, str(node_id))

        await self.audit.log("node.offline", "node", node_id, {}, user_id=user_id)
        await self.session.commit()
        await self.session.refresh(node)
        return node

    async def delete_node(self, node_id: uuid.UUID, user_id: uuid.UUID) -> None:
        node = await self.get_node(node_id, user_id)
        if node.status != NodeStatus.OFFLINE:
            raise BusinessError("仅离线节点可删除")
        if node.is_online:
            raise BusinessError("节点仍在线，请先下线")

        # 检查是否有执行中的任务
        stmt = select(TaskExecution).where(
            TaskExecution.node_id == node_id,
            TaskExecution.status.in_([TaskStatus.ASSIGNED, TaskStatus.RUNNING]),
        )
        result = await self.session.execute(stmt)
        if result.scalar_one_or_none():
            raise BusinessError("节点有执行中的任务，无法删除")

        await self.audit.log("node.deleted", "node", node_id, {"name": node.name}, user_id=user_id)
        await self.session.delete(node)
        await self.session.commit()

    async def heartbeat(self, node_id: uuid.UUID, data: NodeHeartbeatRequest) -> dict:
        node = await self.session.get(Node, node_id)
        if not node:
            raise NotFoundError("节点不存在")

        now = datetime.now(UTC)
        node.last_heartbeat_at = now
        node.is_online = True
        node.status = NodeStatus.ONLINE
        node.updated_at = now
        node.gpu_utilization = data.gpu_util if data.gpu_util is not None else data.gpu_utilization
        node.vram_used_gb = data.vram_used_gb
        node.temp_c = data.temp_c if data.temp_c is not None else data.temperature
        if data.cached_models is not None:
            node.cached_models_json = json.dumps(data.cached_models, ensure_ascii=False)

        # 更新 Redis
        await self.redis.setex(RedisKeys.NODE_ONLINE_FLAG.format(node_id=node_id), 360, "1")
        await self.redis.zadd(RedisKeys.NODE_HEARTBEAT_ZSET, {str(node_id): now.timestamp()})

        # 检查是否有待执行任务
        stmt = select(func.count(TaskExecution.id)).where(
            TaskExecution.node_id == node_id, TaskExecution.status == TaskStatus.ASSIGNED
        )
        tasks_pending = (await self.session.execute(stmt)).scalar_one()

        await self.session.commit()

        return {"online": True, "tasks_pending": tasks_pending}

    async def get_node_detail(self, node_id: uuid.UUID, user_id: uuid.UUID) -> dict:
        node = await self.get_node(node_id, user_id)

        # 今日统计
        today_start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
        stmt = select(
            func.count(TaskExecution.id), func.coalesce(func.sum(TaskExecution.compute_points), 0)
        ).where(
            TaskExecution.node_id == node_id,
            TaskExecution.status == TaskStatus.COMPLETED,
            TaskExecution.completed_at >= today_start,
        )
        result = await self.session.execute(stmt)
        today_tasks, today_points = result.one()

        return {
            "node": node,
            "today_stats": {
                "tasks": today_tasks or 0,
                "points": today_points or 0,
            },
        }

    async def get_node_earnings(
        self, node_id: uuid.UUID, user_id: uuid.UUID, period: str = "month"
    ) -> dict:
        await self.get_node(node_id, user_id)

        # 根据周期计算时间范围
        now = datetime.now(UTC)
        if period == "day":
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif period == "week":
            start = now - timedelta(days=now.weekday())
            start = start.replace(hour=0, minute=0, second=0, microsecond=0)
        elif period == "month":
            start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        else:
            start = None

        stmt = select(
            func.count(TaskExecution.id),
            func.coalesce(func.sum(TaskExecution.supplier_earnings_points), 0),
        ).where(
            TaskExecution.node_id == node_id,
            TaskExecution.status == TaskStatus.COMPLETED,
        )
        if start:
            stmt = stmt.where(TaskExecution.completed_at >= start)

        result = await self.session.execute(stmt)
        total_tasks, total_points = result.one()

        # 按期间分组（简化）
        return {
            "total_points": total_points or 0,
            "by_period": [
                {"period": period, "tasks": total_tasks or 0, "points": total_points or 0}
            ],
        }

    async def get_node_executions(
        self,
        node_id: uuid.UUID,
        user_id: uuid.UUID,
        page: int = 1,
        page_size: int = 20,
        status: TaskStatus | None = None,
    ) -> tuple[list[TaskExecution], int]:
        await self.get_node(node_id, user_id)

        stmt = select(TaskExecution).where(TaskExecution.node_id == node_id)
        if status:
            stmt = stmt.where(TaskExecution.status == status)

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await self.session.execute(count_stmt)).scalar_one()

        stmt = (
            stmt.options(selectinload(TaskExecution.task))
            .order_by(TaskExecution.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await self.session.execute(stmt)
        executions = result.scalars().all()

        return list(executions), total
