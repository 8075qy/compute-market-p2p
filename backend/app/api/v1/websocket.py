"""WebSocket 实时通知推送端点。"""
import uuid

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from app.core.security import decode_token
from app.core.ws_manager import manager

router = APIRouter()


@router.websocket("/ws/notifications")
async def notifications_websocket(
    websocket: WebSocket,
    token: str = Query(default=""),
) -> None:
    """建立长连接后，服务端在用户产生新通知时实时推送。"""
    payload = decode_token(token) if token else None
    if not payload or payload.get("type") != "access":
        await websocket.close(code=1008, reason="Unauthorized")
        return

    try:
        user_id = uuid.UUID(payload["sub"])
    except (KeyError, ValueError, TypeError):
        await websocket.close(code=1008, reason="Invalid token")
        return

    await websocket.accept()
    await manager.connect(user_id, websocket)
    try:
        while True:
            message = await websocket.receive_text()
            if message == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        pass
    finally:
        await manager.disconnect(user_id, websocket)
