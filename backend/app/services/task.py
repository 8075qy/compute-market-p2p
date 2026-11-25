import json
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.core.exceptions import BusinessError, NotFoundError, ParamError
from app.core.redis_client import get_redis
from app.core.redis_keys import RedisKeys
from app.models import (
    Account,
    PlatformConfig,
    Task,
    TaskExecution,
    TaskStatus,
    TaskType,
    User,
)
from app.schemas.task import TaskCreate, TaskListQuery
from app.services.audit import AuditService
from app.services.batch_input import load_manifest_count
from app.services.notification import NotificationService
from app.services.settlement import SettlementEngine


class TaskService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.redis = get_redis()
        self.audit = AuditService(session)
        self.settlement = SettlementEngine(session)

    async def _get_account(self, user_id: uuid.UUID) -> Account:
        account = (
            await self.session.execute(select(Account).where(Account.user_id == user_id))
        ).scalar_one_or_none()
        if not account:
            raise NotFoundError("账户不存在")
        return account

    async def create_task(self, user_id: uuid.UUID, data: TaskCreate) -> Task:
        user = await self.session.get(User, user_id)
        if not user:
            raise NotFoundError("用户不存在")

        config = await self._get_platform_config()
        min_unit = config.min_settlement_unit

        # 预算校验必须在任何记账动作之前完成
        if data.budget_points < min_unit:
            raise ParamError(
                f"预算低于最小结算单位 {min_unit} 分（{min_unit / 100:g} 积分），请调整"
            )

        # 批处理任务：校验数据包并回填工作项总数（在冻结预算前，避免无效数据包动账）
        total_work_units: int | None = None
        if data.type == TaskType.BATCH:
            if not data.input_file_key:
                raise ParamError("批处理任务需要先上传输入数据包")
            total_work_units = await load_manifest_count(data.input_file_key)

        account = await self._get_account(user_id)
        # 预授权：仅冻结预估首段用量（按 required_tflops 满载一个预授权窗口预估）
        preauth = min(
            data.budget_points,
            SettlementEngine.estimate_points(
                data.required_tflops, get_settings().PREAUTH_MINUTES
            ),
        )
        if account.balance_points < preauth:
            raise BusinessError("积分余额不足，无法完成首段预授权")
        account.frozen_points += preauth
        account.balance_points -= preauth

        task_no = await self._generate_task_no()
        task = Task(
            task_no=task_no,
            demander_id=user_id,
            type=data.type,
            title=data.title,
            description=data.description,
            model_source=data.model_source,
            model_id=uuid.UUID(data.model_id) if data.model_id else None,
            model_file_key=data.model_file_key,
            model_file_size=data.model_file_size,
            docker_image=data.docker_image,
            command=data.command,
            env_vars_json=json.dumps(data.env_vars, ensure_ascii=False, sort_keys=True)
            if data.env_vars
            else None,
            params_json=json.dumps(data.params, ensure_ascii=False, sort_keys=True),
            concurrency=data.concurrency,
            min_concurrency=data.min_concurrency,
            max_concurrency=data.max_concurrency,
            timeout_minutes=data.timeout_minutes,
            required_vram_gb=data.required_vram_gb,
            required_tflops=data.required_tflops,
            budget_points=data.budget_points,
            preauthorized_points=preauth,
            min_settlement_unit=min_unit,
            status=TaskStatus.SCHEDULING,
            max_retries=config.max_task_retries,
            input_file_key=data.input_file_key,
            input_file_size=data.input_file_size,
            batch_size=data.batch_size or 0,
            total_work_units=total_work_units,
        )
        self.session.add(task)
        await self.session.flush()

        await self.redis.lpush(RedisKeys.TASK_SCHEDULING_QUEUE, str(task.id))

        await self.audit.log(
            "task.created",
            "task",
            task.id,
            {
                "task_no": task_no,
                "type": data.type.value,
                "budget_points": data.budget_points,
                "required_vram_gb": data.required_vram_gb,
            },
            user_id=user_id,
        )

        await self.session.commit()
        await self.session.refresh(task)
        return task

    async def _generate_task_no(self) -> str:
        now = datetime.now(UTC)
        prefix = f"T{now.strftime('%Y%m%d')}"
        count = (
            await self.session.execute(
                select(func.count(Task.id)).where(Task.task_no.like(f"{prefix}%"))
            )
        ).scalar_one()
        return f"{prefix}{count + 1:04d}"

    async def get_tasks(
        self, user_id: uuid.UUID, query: TaskListQuery
    ) -> tuple[list[Task], int]:
        stmt = select(Task).where(Task.demander_id == user_id)
        if query.status:
            stmt = stmt.where(Task.status == query.status)
        if query.type:
            stmt = stmt.where(Task.type == query.type)

        total = (
            await self.session.execute(select(func.count()).select_from(stmt.subquery()))
        ).scalar_one()

        stmt = (
            stmt.order_by(Task.created_at.desc())
            .offset((query.page - 1) * query.page_size)
            .limit(query.page_size)
        )
        tasks = (await self.session.execute(stmt)).scalars().all()
        return list(tasks), total

    async def get_task(self, task_id: uuid.UUID, user_id: uuid.UUID) -> Task:
        stmt = (
            select(Task)
            .where(Task.id == task_id, Task.demander_id == user_id)
            .options(
                selectinload(Task.executions),
                selectinload(Task.settlements),
            )
        )
        task = (await self.session.execute(stmt)).scalar_one_or_none()
        if not task:
            raise NotFoundError("任务不存在")
        return task

    async def cancel_task(self, task_id: uuid.UUID, user_id: uuid.UUID) -> Task:
        task = await self.get_task(task_id, user_id)

        if task.status in (TaskStatus.COMPLETED, TaskStatus.CANCELLED, TaskStatus.FAILED):
            raise BusinessError("当前状态的任务不可取消")

        now = datetime.now(UTC)

        # 结束仍在进行中的执行记录
        executions = (
            await self.session.execute(
                select(TaskExecution).where(
                    TaskExecution.task_id == task.id,
                    TaskExecution.status.in_(
                        [TaskStatus.ASSIGNED, TaskStatus.RUNNING]
                    ),
                )
            )
        ).scalars().all()
        for execution in executions:
            execution.status = TaskStatus.CANCELLED
            execution.completed_at = now
            if execution.started_at:
                execution.compute_duration_seconds = max(
                    0, int((now - execution.started_at).total_seconds())
                )

        # 退还冻结预算（仅退还预授权中尚未结算的部分，已结算分片不退）
        account = await self._get_account(user_id)
        already_settled = (
            await self.session.execute(
                select(func.coalesce(func.sum(TaskExecution.compute_points), 0)).where(
                    TaskExecution.task_id == task.id,
                    TaskExecution.status == TaskStatus.COMPLETED,
                )
            )
        ).scalar_one() or 0
        frozen = min(task.preauthorized_points, account.frozen_points)
        refund = max(0, frozen - already_settled)
        account.frozen_points = max(0, account.frozen_points - frozen)
        account.balance_points += refund
        task.preauthorized_points = 0

        task.status = TaskStatus.CANCELLED
        task.completed_at = now
        task.updated_at = now

        await self.audit.log(
            "task.cancelled",
            "task",
            task_id,
            {"task_no": task.task_no, "refunded_points": refund},
            user_id=user_id,
        )
        # F1：推送取消状态
        await NotificationService(self.session).emit_task_status(task)
        await self.session.commit()
        await self.session.refresh(task)
        return task

    async def retry_task(self, task_id: uuid.UUID, user_id: uuid.UUID) -> Task:
        task = await self.get_task(task_id, user_id)

        if task.status != TaskStatus.FAILED:
            raise BusinessError("仅失败状态的任务可重试")

        # 失败任务在退款后重新预授权（仅冻结预估首段用量）
        account = await self._get_account(user_id)
        preauth = min(
            task.budget_points,
            SettlementEngine.estimate_points(
                task.required_tflops, get_settings().PREAUTH_MINUTES
            ),
        )
        if account.balance_points < preauth:
            raise BusinessError("积分余额不足，无法重新提交该任务")
        account.balance_points -= preauth
        account.frozen_points += preauth
        task.preauthorized_points = preauth

        task.status = TaskStatus.SCHEDULING
        task.assigned_node_id = None
        task.scheduled_at = None
        task.completed_at = None
        task.error_message = None
        task.retry_count = 0
        task.updated_at = datetime.now(UTC)

        await self.redis.lpush(RedisKeys.TASK_SCHEDULING_QUEUE, str(task.id))

        await self.audit.log(
            "task.retried",
            "task",
            task_id,
            {"task_no": task.task_no, "preauthorized_points": preauth},
            user_id=user_id,
        )
        # F1：推送重新调度状态
        await NotificationService(self.session).emit_task_status(task)
        await self.session.commit()
        await self.session.refresh(task)
        return task

    async def get_task_logs(
        self, task_id: uuid.UUID, user_id: uuid.UUID, attempt_no: int | None = None
    ) -> dict:
        await self.get_task(task_id, user_id)

        stmt = select(TaskExecution).where(TaskExecution.task_id == task_id)
        if attempt_no:
            stmt = stmt.where(TaskExecution.attempt_no == attempt_no)
        else:
            stmt = stmt.order_by(TaskExecution.attempt_no.desc()).limit(1)

        execution = (await self.session.execute(stmt)).scalar_one_or_none()
        if not execution or not execution.execution_log_key:
            raise NotFoundError("执行日志不存在")

        from app.core.minio_client import get_presigned_url

        download_url = await get_presigned_url(execution.execution_log_key)
        return {
            "download_url": download_url,
            "expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
        }

    async def get_task_result(self, task_id: uuid.UUID, user_id: uuid.UUID) -> dict:
        task = await self.get_task(task_id, user_id)

        if task.status != TaskStatus.COMPLETED or not task.result_files_json:
            raise NotFoundError("任务未完成或无结果文件")

        files = json.loads(task.result_files_json)
        from app.core.minio_client import get_presigned_url

        for file in files:
            file["download_url"] = await get_presigned_url(file["key"])
        return {"files": files}

    async def _get_platform_config(self) -> PlatformConfig:
        config = await self.session.get(PlatformConfig, 1)
        if not config:
            config = PlatformConfig()
            self.session.add(config)
            await self.session.flush()
        return config
