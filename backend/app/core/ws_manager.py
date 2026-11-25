"""WebSocket 连接管理器：按用户维护连接，用于通知实时推送。"""
import asyncio
import uuid
from typing import Any, Protocol


class WebSocketLike(Protocol):
    """最小发送接口，便于测试替身与真实 WebSocket 共用。"""

    async def send_json(self, data: Any) -> None: ...


class ConnectionManager:
    """进程内 WebSocket 连接管理，单机部署足够；多实例部署需替换为 Redis pub/sub。"""

    def __init__(self) -> None:
        self._connections: dict[uuid.UUID, set[WebSocketLike]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, user_id: uuid.UUID, websocket: WebSocketLike) -> None:
        async with self._lock:
            self._connections.setdefault(user_id, set()).add(websocket)

    async def disconnect(self, user_id: uuid.UUID, websocket: WebSocketLike) -> None:
        async with self._lock:
            conns = self._connections.get(user_id)
            if not conns:
                return
            conns.discard(websocket)
            if not conns:
                self._connections.pop(user_id, None)

    async def send_to_user(self, user_id: uuid.UUID, message: dict) -> None:
        conns = list(self._connections.get(user_id, ()))
        for ws in conns:
            try:
                await ws.send_json(message)
            except Exception:
                await self.disconnect(user_id, ws)

    async def send_event(self, user_id: uuid.UUID, event: str, data: dict) -> None:
        """推送业务事件（任务状态变化、节点上下线、调度进度等），无连接时为空操作。"""
        await self.send_to_user(user_id, {"type": event, "data": data})

    @property
    def active_connections(self) -> int:
        return sum(len(conns) for conns in self._connections.values())


manager = ConnectionManager()
