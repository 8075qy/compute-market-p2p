"""算力时间银行（储备）相关的请求与响应模型。"""
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PoolOverviewResponse(BaseModel):
    """公共池可视化概览。"""
    pool_total_points: int
    pool_contributors: int
    total_output_points: int = 0
    total_interest_points: int = 0
    last_distributed_at: datetime | None = None


class InterestRecordResponse(BaseModel):
    """储备利息分配周期快照。"""
    id: UUID
    cycle_output_points: int
    interest_points: int
    total_reserve_points: int
    distributed_at: datetime

    model_config = ConfigDict(from_attributes=True)


class InterestAllocationResponse(BaseModel):
    """单账户利息分配明细。"""
    id: UUID
    interest_points: int
    reserve_points_before: int
    distributed_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BorrowRequest(BaseModel):
    amount_points: int = Field(..., gt=0, description="借用（取用）的储备分数量")


class BorrowResponse(BaseModel):
    amount_points: int
    balance_points: int
    reserve_points: int


class BorrowRecordResponse(BaseModel):
    id: UUID
    amount_points: int
    balance_before: int
    reserve_before: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
