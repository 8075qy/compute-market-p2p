import uuid
from datetime import timedelta

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models import SettlementRole, SettlementStatus, User
from app.schemas.common import PageResponse, Response
from app.schemas.settlement import (
    SettlementDetailResponse,
    SettlementExportResponse,
    SettlementResponse,
)
from app.services.settlement import SettlementEngine

router = APIRouter(prefix="/settlements", tags=["结算明细"])


@router.get("", response_model=Response[PageResponse[SettlementResponse]])
async def list_settlements(
    page: int = 1,
    page_size: int = 20,
    status: str | None = None,
    role: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    service = SettlementEngine(session)
    from datetime import datetime
    settlements, total = await service.get_user_settlements(
        user.id, page, page_size,
        SettlementStatus(status) if status else None,
        SettlementRole(role) if role else None,
        datetime.fromisoformat(start_date) if start_date else None,
        datetime.fromisoformat(end_date) if end_date else None,
    )
    return Response(data=PageResponse.create(
        items=[SettlementResponse.model_validate(s) for s in settlements],
        total=total, page=page, page_size=page_size
    ))


@router.get("/export", response_model=Response[SettlementExportResponse])
async def export_settlements(
    status: str | None = None,
    role: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    service = SettlementEngine(session)
    from datetime import datetime
    object_key = await service.export_settlements(
        user.id,
        SettlementStatus(status) if status else None,
        SettlementRole(role) if role else None,
        datetime.fromisoformat(start_date) if start_date else None,
        datetime.fromisoformat(end_date) if end_date else None,
    )
    from app.core.minio_client import get_presigned_url
    download_url = await get_presigned_url(object_key)
    return Response(data=SettlementExportResponse(
        download_url=download_url,
        expires_at=(datetime.now() + timedelta(hours=1)).isoformat()
    ))


@router.get("/{settlement_id}", response_model=Response[SettlementDetailResponse])
async def get_settlement(
    settlement_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    service = SettlementEngine(session)
    settlement = await service.get_settlement(settlement_id, user.id)
    return Response(data=SettlementDetailResponse.model_validate(settlement))
