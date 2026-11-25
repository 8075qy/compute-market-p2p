"""算力时间银行（储备）相关接口。"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models import User
from app.schemas.common import PageResponse, Response
from app.schemas.reserve import (
    BorrowRecordResponse,
    BorrowRequest,
    BorrowResponse,
    InterestAllocationResponse,
    InterestRecordResponse,
    PoolOverviewResponse,
)
from app.services.reserve import ReserveService

router = APIRouter(prefix="/reserve", tags=["算力时间银行"])


@router.get("/pool", response_model=Response[PoolOverviewResponse])
async def get_pool_overview(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """公共池可视化概览。"""
    service = ReserveService(session)
    overview = await service.get_pool_overview()
    return Response(data=PoolOverviewResponse(**overview))


@router.get("/interest-records", response_model=Response[PageResponse[InterestRecordResponse]])
async def list_interest_records(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """公共池利息分配历史（全局可见）。"""
    service = ReserveService(session)
    items, total = await service.list_interest_records(page, page_size)
    return Response(
        data=PageResponse.create(
            items=[InterestRecordResponse.model_validate(r) for r in items],
            total=total,
            page=page,
            page_size=page_size,
        )
    )


@router.get("/interest", response_model=Response[PageResponse[InterestAllocationResponse]])
async def list_my_interest(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """我的储备利息分配明细。"""
    service = ReserveService(session)
    items, total = await service.list_interest_allocations(user.id, page, page_size)
    return Response(
        data=PageResponse.create(
            items=[InterestAllocationResponse.model_validate(a) for a in items],
            total=total,
            page=page,
            page_size=page_size,
        )
    )


@router.post("/borrow", response_model=Response[BorrowResponse])
async def borrow_reserve(
    payload: BorrowRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """借用（取用）储备分转为自由分。"""
    service = ReserveService(session)
    result = await service.borrow(user.id, payload.amount_points)
    return Response(data=BorrowResponse(**result))


@router.get("/borrows", response_model=Response[PageResponse[BorrowRecordResponse]])
async def list_my_borrows(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """我的储备借用流水。"""
    service = ReserveService(session)
    items, total = await service.list_borrow_records(user.id, page, page_size)
    return Response(
        data=PageResponse.create(
            items=[BorrowRecordResponse.model_validate(b) for b in items],
            total=total,
            page=page,
            page_size=page_size,
        )
    )
