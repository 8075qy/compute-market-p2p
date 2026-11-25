import pytest
from sqlalchemy import select

from app.models import Notification, NotificationType
from app.services.notification import NotificationService
from app.services.settlement import SettlementEngine


@pytest.mark.asyncio
async def test_notification_crud(db_session, test_user):
    service = NotificationService(db_session)

    created = await service.create(
        test_user.id, NotificationType.SYSTEM, "系统通知", "欢迎使用"
    )
    await db_session.commit()

    items, total = await service.list_notifications(test_user.id, 1, 20)
    assert total == 1
    assert items[0].title == "系统通知"
    assert items[0].is_read is False

    assert await service.unread_count(test_user.id) == 1
    assert await service.mark_read(test_user.id, created.id) is True
    assert await service.unread_count(test_user.id) == 0

    await service.create(test_user.id, NotificationType.SYSTEM, "第二条", "内容")
    await db_session.commit()
    assert await service.unread_count(test_user.id) == 1
    assert await service.mark_all_read(test_user.id) == 1
    assert await service.unread_count(test_user.id) == 0


@pytest.mark.asyncio
async def test_notification_ownership(db_session, test_user, test_supplier):
    service = NotificationService(db_session)
    created = await service.create(
        test_user.id, NotificationType.SYSTEM, "仅本人可见", "内容"
    )
    await db_session.commit()

    # 他人标记已读不应生效
    assert await service.mark_read(test_supplier.id, created.id) is False
    items, total = await service.list_notifications(test_supplier.id, 1, 20)
    assert total == 0


@pytest.mark.asyncio
async def test_settlement_creates_notifications(db_session, completed_execution):
    engine = SettlementEngine(db_session)
    await engine.settle_execution(completed_execution)

    notifications = (
        await db_session.execute(
            select(Notification).order_by(Notification.created_at)
        )
    ).scalars().all()

    types = {n.type for n in notifications}
    assert NotificationType.SETTLEMENT_PAID in types
    assert NotificationType.TASK_COMPLETED in types

    paid = [n for n in notifications if n.type == NotificationType.SETTLEMENT_PAID]
    assert len(paid) == 1
    assert "入账" in paid[0].content

    completed = [n for n in notifications if n.type == NotificationType.TASK_COMPLETED]
    assert len(completed) == 1
    assert "完成" in completed[0].content
