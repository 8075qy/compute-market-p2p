from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models import SettlementRole, SettlementStatus


class SettlementResponse(BaseModel):
    id: UUID
    settlement_no: str
    task_id: UUID
    task_no: str | None = None
    execution_id: UUID
    role: SettlementRole
    compute_points: int
    platform_fee_rate: int
    platform_fee_points: int
    net_points: int
    destination_account: str
    status: SettlementStatus
    settled_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SettlementDetailResponse(SettlementResponse):
    pass


class SettlementListQuery(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
    status: SettlementStatus | None = None
    role: SettlementRole | None = None
    start_date: str | None = None
    end_date: str | None = None


class SettlementExportResponse(BaseModel):
    download_url: str
    expires_at: str
