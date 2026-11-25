import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import BusinessError, NotFoundError, ParamError
from app.models import (
    Account,
    AuditLog,
    Node,
    NodeStatus,
    NotificationType,
    PlatformConfig,
    Task,
    TaskExecution,
    TaskStatus,
    User,
    UserRole,
    VerificationStatus,
)
from app.schemas.admin import (
    AdminNodeForceOfflineRequest,
    AdminUserSetActiveRequest,
    PlatformConfigUpdate,
)
from app.services.audit import AuditService
from app.services.notification import NotificationService
from app.services.verification import VerificationService


class AdminService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.audit = AuditService(session)

    async def get_dashboard(self) -> dict:
        # 在线节点数
        online_nodes = (
            await self.session.execute(select(func.count(Node.id)).where(Node.is_online))
        ).scalar_one()

        # 待调度任务数
        pending_tasks = (
            await self.session.execute(
                select(func.count(Task.id)).where(Task.status == TaskStatus.SCHEDULING)
            )
        ).scalar_one()

        # 今日平台抽成积分
        today_start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
        today_fee = (
            await self.session.execute(
                select(func.coalesce(func.sum(TaskExecution.platform_fee_points), 0)).where(
                    TaskExecution.completed_at >= today_start,
                    TaskExecution.status == TaskStatus.COMPLETED,
                )
            )
        ).scalar_one()

        # 当前抽成比例
        config = await self.get_config()
        fee_rate = config.platform_fee_rate

        return {
            "online_nodes": online_nodes,
            "pending_tasks": pending_tasks,
            "today_fee_points": today_fee or 0,
            "fee_rate": fee_rate,
        }

    async def get_config(self) -> PlatformConfig:
        config = await self.session.get(PlatformConfig, 1)
        if not config:
            config = PlatformConfig()
            self.session.add(config)
            await self.session.flush()
        return config

    async def update_config(
        self, data: PlatformConfigUpdate, admin_id: uuid.UUID
    ) -> PlatformConfig:
        config = await self.get_config()
        old_rate = config.platform_fee_rate

        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            if (
                key == "platform_fee_rate" and value is not None and not 0 <= value <= 10000  # noqa: PLR2004
            ):
                raise ParamError("抽成比例不得超过 100%")
            setattr(config, key, value)

        config.updated_at = datetime.now(UTC)
        config.updated_by = admin_id

        await self.audit.log(
            "config.updated",
            "platform_config",
            None,
            {
                "old_fee_rate": old_rate,
                "new_fee_rate": config.platform_fee_rate,
                "updated_by": str(admin_id),
                "changes": update_data,
            },
            user_id=admin_id,
        )

        await self.session.commit()
        await self.session.refresh(config)
        return config

    async def get_all_nodes(
        self, page: int = 1, page_size: int = 20, status: NodeStatus | None = None
    ) -> tuple[list[Node], int]:
        stmt = select(Node).options(selectinload(Node.owner))
        if status:
            stmt = stmt.where(Node.status == status)

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await self.session.execute(count_stmt)).scalar_one()

        stmt = stmt.order_by(Node.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        result = await self.session.execute(stmt)
        nodes = result.scalars().all()

        return list(nodes), total

    async def force_node_offline(
        self, node_id: uuid.UUID, data: AdminNodeForceOfflineRequest, admin_id: uuid.UUID
    ) -> Node:
        node = await self.session.get(Node, node_id)
        if not node:
            raise NotFoundError("节点不存在")

        node.status = NodeStatus.OFFLINE
        node.is_online = False
        node.updated_at = datetime.now(UTC)

        # 取消该节点上正在调度中的任务
        stmt = select(Task).where(
            Task.assigned_node_id == node_id,
            Task.status.in_([TaskStatus.SCHEDULING, TaskStatus.ASSIGNED]),
        )
        result = await self.session.execute(stmt)
        tasks = result.scalars().all()
        for task in tasks:
            task.assigned_node_id = None
            task.status = TaskStatus.SCHEDULING
            task.scheduled_at = None

        # 将该节点上未开始的执行记录标记为失败，交由重试处理器
        executions = (
            (
                await self.session.execute(
                    select(TaskExecution).where(
                        TaskExecution.node_id == node_id,
                        TaskExecution.status == TaskStatus.ASSIGNED,
                    )
                )
            )
            .scalars()
            .all()
        )
        now = datetime.now(UTC)
        for execution in executions:
            execution.status = TaskStatus.FAILED
            execution.completed_at = now
            execution.error_message = f"管理员强制下线节点: {data.reason}"

        await self.audit.log(
            "node.force_offline", "node", node_id, {"reason": data.reason}, user_id=admin_id
        )

        # F1：推送节点下线事件并通知机主
        notification = NotificationService(self.session)
        await notification.emit_node_status(node, reason=data.reason)
        await notification.create(
            node.owner_id,
            NotificationType.NODE_OFFLINE,
            "节点被强制下线",
            f"节点 {node.name} 已被管理员强制下线，原因：{data.reason}",
            ref_id=node.id,
        )

        await self.session.commit()
        await self.session.refresh(node)
        return node

    async def get_all_tasks(
        self, page: int = 1, page_size: int = 20, status: TaskStatus | None = None
    ) -> tuple[list[Task], int]:
        stmt = select(Task).options(selectinload(Task.demander))
        if status:
            stmt = stmt.where(Task.status == status)

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await self.session.execute(count_stmt)).scalar_one()

        stmt = stmt.order_by(Task.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        result = await self.session.execute(stmt)
        tasks = result.scalars().all()

        return list(tasks), total

    async def cancel_task_scheduling(self, task_id: uuid.UUID, admin_id: uuid.UUID) -> Task:
        task = await self.session.get(Task, task_id)
        if not task:
            raise NotFoundError("任务不存在")

        if task.status not in [TaskStatus.PENDING, TaskStatus.SCHEDULING]:
            raise BusinessError("仅待调度状态的任务可取消")

        # 解冻预算
        account = (
            await self.session.execute(select(Account).where(Account.user_id == task.demander_id))
        ).scalar_one_or_none()
        if account:
            frozen = min(task.preauthorized_points, account.frozen_points)
            account.frozen_points -= frozen
            account.balance_points += frozen

        task.status = TaskStatus.CANCELLED
        task.completed_at = datetime.now(UTC)
        task.updated_at = datetime.now(UTC)

        await self.audit.log(
            "task.admin_cancelled", "task", task_id, {"task_no": task.task_no}, user_id=admin_id
        )

        # F1：推送取消状态并通知需求方
        notification = NotificationService(self.session)
        await notification.emit_task_status(task, {"reason": "admin_cancelled"})
        await notification.create(
            task.demander_id,
            NotificationType.TASK_CANCELLED,
            "任务已被取消",
            f"任务 {task.task_no} 已被管理员取消调度，冻结预算已退回",
            ref_id=task.id,
        )

        await self.session.commit()
        await self.session.refresh(task)
        return task

    async def get_audit_logs(
        self,
        page: int = 1,
        page_size: int = 20,
        event_type: str | None = None,
        entity_type: str | None = None,
        user_id: uuid.UUID | None = None,
    ) -> tuple[list[AuditLog], int]:
        stmt = select(AuditLog)
        if event_type:
            stmt = stmt.where(AuditLog.event_type == event_type)
        if entity_type:
            stmt = stmt.where(AuditLog.entity_type == entity_type)
        if user_id:
            stmt = stmt.where(AuditLog.user_id == user_id)

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await self.session.execute(count_stmt)).scalar_one()

        stmt = (
            stmt.order_by(AuditLog.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await self.session.execute(stmt)
        logs = result.scalars().all()

        return list(logs), total

    async def verify_audit_chain(
        self, start_from: datetime | None = None
    ) -> tuple[bool, list[str]]:
        return await self.audit.verify_chain(start_from)

    async def list_verification_records(
        self,
        page: int = 1,
        page_size: int = 20,
        status: VerificationStatus | None = None,
    ) -> tuple[list, int]:
        service = VerificationService(self.session)
        return await service.list_records(page, page_size, status)

    async def run_verification(self, record_id: uuid.UUID, admin_id: uuid.UUID):
        service = VerificationService(self.session)
        return await service.run_verification(record_id, operator_id=admin_id)

    @staticmethod
    def _serialize_user(user: User) -> dict:
        account = user.account
        return {
            "id": user.id,
            "username": user.username,
            "phone": user.phone,
            "email": user.email,
            "nickname": user.nickname,
            "roles": user.roles,
            "is_active": user.is_active,
            "balance_points": account.balance_points if account else 0,
            "frozen_points": account.frozen_points if account else 0,
            "reserve_points": account.reserve_points if account else 0,
            "total_earned": account.total_earned if account else 0,
            "total_spent": account.total_spent if account else 0,
            "created_at": user.created_at,
        }

    async def get_users(
        self,
        page: int = 1,
        page_size: int = 20,
        keyword: str | None = None,
        role: str | None = None,
        is_active: bool | None = None,
    ) -> tuple[list[dict], int]:
        stmt = select(User).options(selectinload(User.account))

        if keyword:
            like = f"%{keyword.strip()}%"
            stmt = stmt.where(
                (User.username.ilike(like))
                | (User.phone.ilike(like))
                | (User.email.ilike(like))
                | (User.nickname.ilike(like))
            )
        if is_active is not None:
            stmt = stmt.where(User.is_active == is_active)

        stmt = stmt.order_by(User.created_at.desc())
        result = await self.session.execute(stmt)
        users = result.scalars().all()

        # 角色过滤：遍历 roles JSON 数组，兼容 PostgreSQL 与测试 SQLite
        if role:
            if role not in {item.value for item in UserRole}:
                raise ParamError("无效的角色筛选条件")
            target = UserRole(role)
            users = [u for u in users if u.has_role(target)]

        total = len(users)
        start = (page - 1) * page_size
        page_users = users[start : start + page_size]

        return [self._serialize_user(u) for u in page_users], total

    async def _get_user_with_account(self, user_id: uuid.UUID) -> User | None:
        stmt = select(User).where(User.id == user_id).options(selectinload(User.account))
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_user_detail(self, user_id: uuid.UUID) -> dict:
        user = await self._get_user_with_account(user_id)
        if not user:
            raise NotFoundError("用户不存在")
        return self._serialize_user(user)

    async def set_user_active(
        self, user_id: uuid.UUID, data: AdminUserSetActiveRequest, admin_id: uuid.UUID
    ) -> dict:
        if user_id == admin_id:
            raise BusinessError("不能封禁自己")

        user = await self._get_user_with_account(user_id)
        if not user:
            raise NotFoundError("用户不存在")
        if user.has_role(UserRole.ADMIN):
            raise BusinessError("不能操作管理员账户")

        user.is_active = data.is_active
        user.updated_at = datetime.now(UTC)

        action = "enabled" if data.is_active else "disabled"
        await self.audit.log(
            f"user.{action}",
            "user",
            user_id,
            {"reason": data.reason, "is_active": data.is_active, "operator": str(admin_id)},
            user_id=admin_id,
        )

        await self.session.commit()
        return self._serialize_user(user)
