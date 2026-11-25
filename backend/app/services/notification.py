"""通知服务：创建、分页查询、未读数与已读标记。"""
import uuid
from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy import CursorResult, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ws_manager import manager
from app.models import Notification, NotificationType


class NotificationService:
    """站内消息通知：任务完成/失败、结算到账等事件触达用户。"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        user_id: uuid.UUID,
        type_: NotificationType,
        title: str,
        content: str,
        ref_id: uuid.UUID | None = None,
    ) -> Notification:
        notification = Notification(
            user_id=user_id,
            type=type_,
            title=title,
            content=content,
            ref_id=ref_id,
        )
        self.session.add(notification)
        await self.session.flush()
        await self._push(notification)
        return notification

    async def _push(self, notification: Notification) -> None:
        """通知创建后实时推送给目标用户；目标用户无连接时为空操作。"""
        await manager.send_to_user(
            notification.user_id,
            {
                "type": "notification",
                "data": {
                    "id": str(notification.id),
                    "type": notification.type.value,
                    "title": notification.title,
                    "content": notification.content,
                    "ref_id": str(notification.ref_id) if notification.ref_id else None,
                    "is_read": False,
                    "created_at": datetime.now(UTC).isoformat(),
                },
            },
        )

    async def emit_task_status(self, task, extra: dict | None = None) -> None:
        """推送任务状态变化，供需求方页面实时刷新列表与详情。"""
        await manager.send_event(
            task.demander_id,
            "task_status",
            {
                "task_id": str(task.id),
                "task_no": task.task_no,
                "status": task.status.value if hasattr(task.status, "value") else str(task.status),
                "assigned_node_id": str(task.assigned_node_id) if task.assigned_node_id else None,
                "retry_count": task.retry_count,
                **(extra or {}),
            },
        )

    async def emit_node_status(self, node, reason: str | None = None) -> None:
        """推送节点上下线变化，供供给方页面实时刷新节点状态。"""
        await manager.send_event(
            node.owner_id,
            "node_status",
            {
                "node_id": str(node.id),
                "name": node.name,
                "status": node.status.value if hasattr(node.status, "value") else str(node.status),
                "is_online": bool(node.is_online),
                "reason": reason,
            },
        )

    async def list_notifications(
        self, user_id: uuid.UUID, page: int, page_size: int, unread_only: bool = False
    ) -> tuple[list[Notification], int]:
        conditions = [Notification.user_id == user_id]
        if unread_only:
            conditions.append(Notification.is_read.is_(False))

        total = (
            await self.session.execute(
                select(func.count(Notification.id)).where(*conditions)
            )
        ).scalar_one()

        stmt = (
            select(Notification)
            .where(*conditions)
            .order_by(Notification.created_at.desc(), Notification.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        items = (await self.session.execute(stmt)).scalars().all()
        return list(items), total

    async def unread_count(self, user_id: uuid.UUID) -> int:
        return (
            await self.session.execute(
                select(func.count(Notification.id)).where(
                    Notification.user_id == user_id,
                    Notification.is_read.is_(False),
                )
            )
        ).scalar_one()

    async def mark_read(self, user_id: uuid.UUID, notification_id: uuid.UUID) -> bool:
        result = cast(
            "CursorResult[Any]",
            await self.session.execute(
                update(Notification)
                .where(Notification.id == notification_id, Notification.user_id == user_id)
                .values(is_read=True)
            ),
        )
        return result.rowcount > 0

    async def mark_all_read(self, user_id: uuid.UUID) -> int:
        result = cast(
            "CursorResult[Any]",
            await self.session.execute(
                update(Notification)
                .where(Notification.user_id == user_id, Notification.is_read.is_(False))
                .values(is_read=True)
            ),
        )
        return result.rowcount or 0
