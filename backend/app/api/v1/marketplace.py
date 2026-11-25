from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models import User
from app.schemas.common import PageResponse, Response
from app.schemas.node import MarketplaceNodeResponse
from app.services.node import NodeService

router = APIRouter(prefix="/marketplace", tags=["算力市场"])


@router.get("/nodes", response_model=Response[PageResponse[MarketplaceNodeResponse]])
async def list_marketplace_nodes(
    page: int = 1,
    page_size: int = 20,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """公开的算力市场：所有登录用户均可查看在线共享的 GPU 设备。"""
    service = NodeService(session)
    nodes, total = await service.get_marketplace_nodes(page, page_size)
    return Response(data=PageResponse.create(
        items=[MarketplaceNodeResponse.model_validate(n) for n in nodes],
        total=total, page=page, page_size=page_size
    ))
