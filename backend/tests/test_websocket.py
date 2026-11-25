"""WebSocket 通知实时推送测试。"""
import uuid

import pytest

from app.core.ws_manager import manager
from app.models import (
    NotificationType,
    Task,
    TaskStatus,
    TaskType,
    UserRole,
)
from app.services.notification import NotificationService
from tests.conftest import create_user


class FakeWebSocket:
    def __init__(self) -> None:
        self.messages: list[dict] = []

    async def send_json(self, data: dict) -> None:
        self.messages.append(data)


@pytest.mark.asyncio
async def test_ws_manager_send_only_to_connected():
    user_id = uuid.uuid4()
    ws = FakeWebSocket()
    await manager.connect(user_id, ws)

    await manager.send_to_user(user_id, {"type": "notification", "data": {}})
    assert len(ws.messages) == 1

    await manager.disconnect(user_id, ws)
    await manager.send_to_user(user_id, {"type": "notification", "data": {}})
    assert len(ws.messages) == 1


@pytest.mark.asyncio
async def test_create_pushes_notification(db_session):
    user = await create_user(db_session, "13800138001", UserRole.USER)
    ws = FakeWebSocket()
    await manager.connect(user.id, ws)
    try:
        notification = await NotificationService(db_session).create(
            user_id=user.id,
            type_=NotificationType.SYSTEM,
            title="系统通知",
            content="内容",
        )
        assert len(ws.messages) == 1
        message = ws.messages[0]
        assert message["type"] == "notification"
        assert message["data"]["id"] == str(notification.id)
        assert message["data"]["type"] == "system"
        assert message["data"]["title"] == "系统通知"
        assert message["data"]["is_read"] is False
    finally:
        await manager.disconnect(user.id, ws)


@pytest.mark.asyncio
async def test_create_without_connection_is_noop(db_session):
    user = await create_user(db_session, "13800138002", UserRole.USER)
    notification = await NotificationService(db_session).create(
        user_id=user.id,
        type_=NotificationType.SYSTEM,
        title="无连接",
        content="内容",
    )
    assert notification.id is not None


@pytest.mark.asyncio
async def test_emit_task_status_pushes_event(db_session, test_user):
    task = Task(
        task_no="T202601010002",
        demander_id=test_user.id,
        type=TaskType.INFERENCE,
        title="状态推送任务",
        model_source="platform",
        params_json="{}",
        required_vram_gb=8,
        budget_points=5000,
        min_settlement_unit=1000,
        status=TaskStatus.RUNNING,
    )
    db_session.add(task)
    await db_session.commit()
    await db_session.refresh(task)

    ws = FakeWebSocket()
    await manager.connect(test_user.id, ws)
    try:
        await NotificationService(db_session).emit_task_status(
            task, {"progress": {"completed": 1, "total": 2}}
        )
        assert len(ws.messages) == 1
        message = ws.messages[0]
        assert message["type"] == "task_status"
        assert message["data"]["task_id"] == str(task.id)
        assert message["data"]["status"] == "running"
        assert message["data"]["progress"] == {"completed": 1, "total": 2}
    finally:
        await manager.disconnect(test_user.id, ws)


@pytest.mark.asyncio
async def test_emit_node_status_pushes_event(db_session, test_supplier, online_node):
    ws = FakeWebSocket()
    await manager.connect(test_supplier.id, ws)
    try:
        await NotificationService(db_session).emit_node_status(
            online_node, reason="heartbeat_timeout"
        )
        assert len(ws.messages) == 1
        message = ws.messages[0]
        assert message["type"] == "node_status"
        assert message["data"]["node_id"] == str(online_node.id)
        assert message["data"]["status"] == "online"
        assert message["data"]["reason"] == "heartbeat_timeout"
    finally:
        await manager.disconnect(test_supplier.id, ws)
