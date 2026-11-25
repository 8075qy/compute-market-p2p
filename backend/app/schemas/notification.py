from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models import NotificationType


class NotificationResponse(BaseModel):
    id: UUID
    type: NotificationType
    title: str
    content: str
    ref_id: UUID | None = None
    is_read: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class NotificationListResponse(BaseModel):
    items: list[NotificationResponse]
    total: int
    page: int
    page_size: int


class UnreadCountResponse(BaseModel):
    unread_count: int
