import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models import User
from app.schemas.common import Response
from app.schemas.notification import (
    NotificationListResponse,
    NotificationResponse,
    UnreadCountResponse,
)
from app.services.notification import NotificationService

router = APIRouter(prefix="/notifications", tags=["通知"])


@router.get("", response_model=Response[NotificationListResponse])
async def list_notifications(
    page: int = 1,
    page_size: int = 20,
    unread_only: bool = False,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    service = NotificationService(session)
    items, total = await service.list_notifications(user.id, page, page_size, unread_only)
    return Response(
        data=NotificationListResponse(
            items=[NotificationResponse.model_validate(n) for n in items],
            total=total,
            page=page,
            page_size=page_size,
        )
    )


@router.get("/unread-count", response_model=Response[UnreadCountResponse])
async def unread_count(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    service = NotificationService(session)
    count = await service.unread_count(user.id)
    return Response(data=UnreadCountResponse(unread_count=count))


@router.post("/{notification_id}/read", response_model=Response[dict])
async def mark_read(
    notification_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    service = NotificationService(session)
    updated = await service.mark_read(user.id, notification_id)
    await session.commit()
    return Response(data={"ok": updated})


@router.post("/read-all", response_model=Response[dict])
async def mark_all_read(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    service = NotificationService(session)
    updated = await service.mark_all_read(user.id)
    await session.commit()
    return Response(data={"updated": updated})
