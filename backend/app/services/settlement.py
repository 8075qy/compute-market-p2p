import csv
import io
import json
import math
import uuid
from datetime import UTC, datetime
from decimal import ROUND_CEILING, Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import BusinessError, NotFoundError
from app.models import (
    Account,
    Node,
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
from app.services.audit import AuditService
from app.services.notification import NotificationService


class SettlementEngine:
    """按算力时长结算积分，并保证幂等与账实一致。"""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.audit = AuditService(session)

    async def _get_account(self, user_id: uuid.UUID) -> Account:
        account = (
            await self.session.execute(select(Account).where(Account.user_id == user_id))
        ).scalar_one_or_none()
        if not account:
            raise NotFoundError("账户不存在")
        return account

    async def settle_execution(self, execution: TaskExecution) -> Settlement:
        await self.session.refresh(execution, ["task", "node"])
        task = execution.task
        node = execution.node

        if not task or not node:
            raise BusinessError("执行记录缺少任务或节点信息")

        # 幂等：同一执行记录只结算一次
        if execution.status == TaskStatus.COMPLETED:
            existing = (
                await self.session.execute(
                    select(Settlement).where(
                        Settlement.execution_id == execution.id,
                        Settlement.role == SettlementRole.SUPPLIER,
                        Settlement.status == SettlementStatus.SETTLED,
                    )
                )
            ).scalar_one_or_none()
            if existing:
                return existing
            raise BusinessError("执行记录已结算")

        config = await self._get_platform_config()

        compute_points = execution.compute_points
        if compute_points is None:
            compute_points = self._calculate_points(execution)
        # 实际消耗不得超过任务剩余预算（多分片共享同一预算池）
        remaining_budget = await self._remaining_budget(task, execution)
        compute_points = max(0, min(compute_points, remaining_budget))

        platform_fee = 0
        supplier_earnings = compute_points

        reserve_points = compute_points * config.reserve_ratio // 100
        free_points = compute_points - reserve_points

        execution.compute_points = compute_points
        execution.platform_fee_points = platform_fee
        execution.supplier_earnings_points = supplier_earnings
        execution.reserve_points = reserve_points
        execution.status = TaskStatus.COMPLETED
        execution.completed_at = execution.completed_at or datetime.now(UTC)

        # 供给方入账：储备分进储备池，自由分进可用余额
        supplier_account = await self._get_account(node.owner_id)
        supplier_account.balance_points += free_points
        supplier_account.reserve_points += reserve_points
        supplier_account.total_earned += supplier_earnings
        node.total_points_earned += supplier_earnings
        node.total_tasks_completed += 1

        supplier_settlement = Settlement(
            settlement_no=await self._generate_settlement_no("S"),
            user_id=node.owner_id,
            task_id=task.id,
            execution_id=execution.id,
            role=SettlementRole.SUPPLIER,
            compute_points=compute_points,
            platform_fee_rate=0,
            platform_fee_points=platform_fee,
            net_points=supplier_earnings,
            destination_account="算力账户",
            status=SettlementStatus.SETTLED,
            settled_at=datetime.now(UTC),
        )
        self.session.add(supplier_settlement)
        await self.session.flush()

        # 全部分片完成后统一解冻预算、退还未使用部分并标记任务完成
        if await self._all_slices_completed(task):
            await self._finalize_task(task, node, execution)

        await self.audit.log(
            "settlement.created",
            "settlement",
            supplier_settlement.id,
            {
                "task_id": str(task.id),
                "execution_id": str(execution.id),
                "slice_index": execution.slice_index or 0,
                "billing_seconds": round(self._billing_duration_seconds(execution), 3),
                "effective_tflops": str(self._effective_tflops(execution)),
                "compute_points": compute_points,
                "fee_rate": 0,
                "platform_fee": platform_fee,
                "supplier_earnings": supplier_earnings,
                "free_points": free_points,
                "reserve_points": reserve_points,
            },
        )

        # F3：通知供给方结算到账
        notification = NotificationService(self.session)
        await notification.create(
            node.owner_id,
            NotificationType.SETTLEMENT_PAID,
            "结算到账",
            f"任务 {task.task_no} 分片结算完成，已入账 {supplier_earnings} 分",
            ref_id=task.id,
        )

        # F1：推送调度进度（已完成分片数 / 总分片数）
        total_slices = (
            await self.session.execute(
                select(func.count(TaskExecution.id)).where(
                    TaskExecution.task_id == task.id
                )
            )
        ).scalar_one()
        completed_slices = (
            await self.session.execute(
                select(func.count(TaskExecution.id)).where(
                    TaskExecution.task_id == task.id,
                    TaskExecution.status == TaskStatus.COMPLETED,
                )
            )
        ).scalar_one()
        await notification.emit_task_status(
            task,
            {"progress": {"completed": completed_slices, "total": total_slices}},
        )

        await self.session.commit()
        await self.session.refresh(supplier_settlement)
        return supplier_settlement

    async def _remaining_budget(
        self, task: Task, current_execution: TaskExecution
    ) -> int:
        """任务剩余可结算预算：受「总预算」与「预授权额度」双重约束。"""
        already_settled = (
            await self.session.execute(
                select(func.coalesce(func.sum(TaskExecution.compute_points), 0)).where(
                    TaskExecution.task_id == task.id,
                    TaskExecution.id != current_execution.id,
                    TaskExecution.status == TaskStatus.COMPLETED,
                )
            )
        ).scalar_one() or 0
        budget_remaining = max(0, task.budget_points - already_settled)
        preauth_remaining = max(0, task.preauthorized_points - already_settled)
        return min(budget_remaining, preauth_remaining)

    async def _settled_points(self, task: Task) -> int:
        """任务已结算积分总额（含当前执行）。"""
        settled = (
            await self.session.execute(
                select(func.coalesce(func.sum(TaskExecution.compute_points), 0)).where(
                    TaskExecution.task_id == task.id,
                    TaskExecution.status == TaskStatus.COMPLETED,
                )
            )
        ).scalar_one()
        return settled or 0

    async def ensure_preauthorized(self, task: Task, required_points: int) -> bool:
        """确保任务预授权额度 ≥ required_points；不足则从需求方余额续冻。

        返回是否满足预授权。续冻失败（余额不足或已达预算上限）返回 False，
        此时调用方应停止派发新分片并视情况将任务置为 PAUSED。
        """
        required_points = max(1, int(required_points))
        settled = await self._settled_points(task)
        remaining_preauth = max(0, task.preauthorized_points - settled)
        if remaining_preauth >= required_points:
            return True

        shortfall = required_points - remaining_preauth
        topup = min(shortfall, max(0, task.budget_points - task.preauthorized_points))
        if topup <= 0:
            return False

        account = await self._get_account(task.demander_id)
        if account.balance_points < topup:
            return False
        account.balance_points -= topup
        account.frozen_points += topup
        task.preauthorized_points += topup
        return True

    @staticmethod
    def estimate_points(tflops: float | None, minutes: int) -> int:
        """预估积分：按给定算力满载运行 minutes 分钟，向上取整，最低 1 分。"""
        minutes = max(1, int(minutes))
        try:
            value = Decimal(str(tflops)) if tflops is not None else Decimal(0)
        except (ValueError, TypeError):
            value = Decimal(0)
        if value <= 0:
            return 1
        points = value * minutes / Decimal(60)
        return max(1, int(points.to_integral_value(rounding=ROUND_CEILING)))

    async def _all_slices_completed(self, task: Task) -> bool:
        """任务所有分片是否均已结算完成。"""
        if task.type == TaskType.BATCH:
            # 批处理：工作项全部完成且无活跃批次。
            # 失败回池会留下 FAILED 记录，不计入活跃判定，避免任务永远无法收尾。
            total = task.total_work_units or 0
            if task.completed_work_units < total:
                return False
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
            return active == 0

        pending = (
            await self.session.execute(
                select(func.count(TaskExecution.id)).where(
                    TaskExecution.task_id == task.id,
                    TaskExecution.status != TaskStatus.COMPLETED,
                )
            )
        ).scalar_one()
        return pending == 0

    async def _finalize_task(
        self, task: Task, node: Node, execution: TaskExecution
    ) -> None:
        """全部分片完成后：汇总结算，解冻预算、退还剩余、标记任务完成。"""
        total_compute = (
            await self.session.execute(
                select(func.coalesce(func.sum(TaskExecution.compute_points), 0)).where(
                    TaskExecution.task_id == task.id,
                    TaskExecution.status == TaskStatus.COMPLETED,
                )
            )
        ).scalar_one() or 0

        demander_account = await self._get_account(task.demander_id)
        frozen = min(task.preauthorized_points, demander_account.frozen_points)
        refund = max(0, frozen - total_compute)
        demander_account.frozen_points = max(0, demander_account.frozen_points - frozen)
        demander_account.balance_points += refund
        demander_account.total_spent += total_compute

        self.session.add(
            Settlement(
                settlement_no=await self._generate_settlement_no("D"),
                user_id=task.demander_id,
                task_id=task.id,
                execution_id=execution.id,
                role=SettlementRole.DEMANDER,
                compute_points=total_compute,
                platform_fee_rate=0,
                platform_fee_points=0,
                net_points=-total_compute,
                destination_account="算力账户",
                status=SettlementStatus.SETTLED,
                settled_at=datetime.now(UTC),
            )
        )

        if refund > 0:
            self.session.add(
                Settlement(
                    settlement_no=await self._generate_settlement_no("R"),
                    user_id=task.demander_id,
                    task_id=task.id,
                    execution_id=execution.id,
                    role=SettlementRole.DEMANDER,
                    compute_points=0,
                    platform_fee_rate=0,
                    platform_fee_points=0,
                    net_points=refund,
                    destination_account="原路退回",
                    status=SettlementStatus.REFUNDED,
                    settled_at=datetime.now(UTC),
                )
            )

        # C1：分片结果合并——按 key 去重、稳定排序后写回，需求方获得完整结果清单
        result_count = 0
        if task.result_files_json:
            try:
                files = json.loads(task.result_files_json)
            except (TypeError, ValueError):
                files = []
            seen: set[str] = set()
            merged: list[dict] = []
            for f in files:
                if isinstance(f, dict) and f.get("key") and f["key"] not in seen:
                    seen.add(f["key"])
                    merged.append(f)
            task.result_files_json = json.dumps(merged, ensure_ascii=False)
            result_count = len(merged)

        task.status = TaskStatus.COMPLETED
        task.completed_at = datetime.now(UTC)
        task.assigned_node_id = node.id

        await self.audit.log(
            "task.completed",
            "task",
            task.id,
            {
                "total_compute_points": total_compute,
                "refunded_points": refund,
                "result_file_count": result_count,
            },
        )

        # F3：通知需求方任务完成
        notification = NotificationService(self.session)
        await notification.create(
            task.demander_id,
            NotificationType.TASK_COMPLETED,
            "任务完成",
            f"任务 {task.task_no} 已全部完成，共生成 {result_count} 个结果文件",
            ref_id=task.id,
        )
        # F1：推送完成状态
        await notification.emit_task_status(task)

    def _billing_duration_seconds(self, execution: TaskExecution) -> float:
        """计费用时：优先取上报时长；为 0 时回退到起止时间差，保留亚秒精度。"""
        reported = execution.compute_duration_seconds
        if reported is not None and reported > 0:
            return float(reported)
        if not execution.started_at:
            return 0.0
        started = execution.started_at
        if started.tzinfo is None:
            started = started.replace(tzinfo=UTC)
        end = execution.completed_at or datetime.now(UTC)
        if end.tzinfo is None:
            end = end.replace(tzinfo=UTC)
        return max(0.0, (end - started).total_seconds())

    def _effective_tflops(self, execution: TaskExecution) -> Decimal:
        """实际算力 = 单卡峰值 × 卡数 × 实测利用率；无利用率样本时按满载计。"""
        node = execution.node
        if not node:
            return Decimal(0)

        peak = Decimal(str(node.peak_tflops or 0))
        gpu_count = max(1, int(node.gpu_count or 1))

        utilization = node.gpu_utilization
        if utilization is None or float(utilization) <= 0:
            ratio = Decimal(1)
        else:
            ratio = min(Decimal(str(utilization)) / Decimal(100), Decimal(1))

        return peak * Decimal(gpu_count) * ratio

    def _calculate_points(self, execution: TaskExecution) -> int:
        """按「实际算力 × 时长」计费：实际算力单价 1 分/TFLOPS·小时，按分钟向上取整。"""
        duration_seconds = self._billing_duration_seconds(execution)
        if duration_seconds <= 0:
            return 0

        billed_minutes = max(1, math.ceil(duration_seconds / 60))
        tflops = self._effective_tflops(execution)
        points = Decimal(billed_minutes) * tflops / Decimal(60)
        return int(points.to_integral_value(rounding=ROUND_CEILING))

    async def _get_platform_config(self) -> PlatformConfig:
        config = await self.session.get(PlatformConfig, 1)
        if not config:
            config = PlatformConfig()
            self.session.add(config)
            await self.session.flush()
        return config

    async def _generate_settlement_no(self, prefix: str) -> str:
        now = datetime.now(UTC)
        date_prefix = f"{prefix}{now.strftime('%Y%m%d')}"
        count = (
            await self.session.execute(
                select(func.count(Settlement.id)).where(
                    Settlement.settlement_no.like(f"{date_prefix}%")
                )
            )
        ).scalar_one()
        return f"{date_prefix}{count + 1:04d}"

    async def get_user_settlements(  # noqa: PLR0913, PLR0917
        self,
        user_id: uuid.UUID,
        page: int = 1,
        page_size: int = 20,
        status: SettlementStatus | None = None,
        role: SettlementRole | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> tuple[list[Settlement], int]:
        stmt = (
            select(Settlement)
            .where(Settlement.user_id == user_id)
            .options(
                selectinload(Settlement.task),
                selectinload(Settlement.execution),
            )
        )
        if status:
            stmt = stmt.where(Settlement.status == status)
        if role:
            stmt = stmt.where(Settlement.role == role)
        if start_date:
            stmt = stmt.where(Settlement.created_at >= start_date)
        if end_date:
            stmt = stmt.where(Settlement.created_at <= end_date)

        total = (
            await self.session.execute(select(func.count()).select_from(stmt.subquery()))
        ).scalar_one()

        stmt = (
            stmt.order_by(Settlement.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        settlements = (await self.session.execute(stmt)).scalars().all()
        return list(settlements), total

    async def get_settlement(
        self, settlement_id: uuid.UUID, user_id: uuid.UUID
    ) -> Settlement:
        stmt = (
            select(Settlement)
            .where(Settlement.id == settlement_id, Settlement.user_id == user_id)
            .options(
                selectinload(Settlement.task),
                selectinload(Settlement.execution),
            )
        )
        settlement = (await self.session.execute(stmt)).scalar_one_or_none()
        if not settlement:
            raise NotFoundError("结算记录不存在")
        return settlement

    async def export_settlements(
        self,
        user_id: uuid.UUID,
        status: SettlementStatus | None = None,
        role: SettlementRole | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> str:
        """导出 CSV 到 MinIO，返回 object key。"""
        settlements, _ = await self.get_user_settlements(
            user_id,
            page=1,
            page_size=10000,
            status=status,
            role=role,
            start_date=start_date,
            end_date=end_date,
        )

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(
            [
                "结算单号",
                "任务单号",
                "算力时长(秒)",
                "结算积分(分)",
                "抽成比例(万分比)",
                "抽成积分(分)",
                "净变动积分(分)",
                "去向账户",
                "状态",
                "结算时间",
                "角色",
            ]
        )
        for item in settlements:
            writer.writerow(
                [
                    item.settlement_no,
                    item.task.task_no if item.task else "",
                    item.execution.compute_duration_seconds or 0
                    if item.execution
                    else 0,
                    item.compute_points,
                    item.platform_fee_rate,
                    item.platform_fee_points,
                    item.net_points,
                    item.destination_account,
                    item.status.value,
                    item.settled_at.isoformat() if item.settled_at else "",
                    item.role.value,
                ]
            )

        from app.core.minio_client import upload_bytes

        object_key = (
            f"exports/settlement_{user_id}_"
            f"{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}.csv"
        )
        await upload_bytes(
            object_key, output.getvalue().encode("utf-8"), "text/csv"
        )
        return object_key
