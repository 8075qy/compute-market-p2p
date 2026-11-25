from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models import NodeStatus, TaskStatus, VerificationStatus


class PlatformConfigResponse(BaseModel):
    id: int
    platform_fee_rate: int
    min_settlement_unit: int
    max_task_retries: int
    node_offline_threshold_minutes: int
    task_scheduling_timeout_minutes: int
    settlement_timeout_hours: int
    verification_sample_rate: int
    reserve_ratio: int
    max_borrow_ratio: int
    reserve_interest_ratio: int
    updated_at: datetime
    updated_by: UUID | None = None

    model_config = ConfigDict(from_attributes=True)


class PlatformConfigUpdate(BaseModel):
    platform_fee_rate: int | None = Field(None, ge=0, le=10000)
    min_settlement_unit: int | None = Field(None, ge=1)
    max_task_retries: int | None = Field(None, ge=0, le=10)
    node_offline_threshold_minutes: int | None = Field(None, ge=1, le=60)
    task_scheduling_timeout_minutes: int | None = Field(None, ge=1, le=120)
    settlement_timeout_hours: int | None = Field(None, ge=1, le=72)
    verification_sample_rate: int | None = Field(None, ge=0, le=10000)
    reserve_ratio: int | None = Field(None, ge=0, le=100)
    max_borrow_ratio: int | None = Field(None, ge=0, le=100)
    reserve_interest_ratio: int | None = Field(None, ge=0, le=100)


class AdminDashboardResponse(BaseModel):
    online_nodes: int
    pending_tasks: int
    today_fee_points: int
    fee_rate: int


class AdminNodeResponse(BaseModel):
    id: UUID
    name: str
    owner_id: UUID
    owner_phone: str | None = None
    gpu_model: str
    vram_gb: int
    peak_tflops: float
    gpu_uuid: str | None = None
    benchmark_tflops: float | None = None
    benchmark_status: str = "pending"
    benchmarked_at: datetime | None = None
    status: NodeStatus
    is_online: bool
    last_heartbeat_at: datetime | None = None
    total_tasks_completed: int
    total_points_earned: int
    reputation_score: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AdminTaskResponse(BaseModel):
    id: UUID
    task_no: str
    demander_id: UUID
    demander_phone: str | None = None
    type: str
    status: TaskStatus
    assigned_node_id: UUID | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AdminNodeForceOfflineRequest(BaseModel):
    reason: str = Field(..., min_length=1, max_length=256)


class AdminAuditLogQuery(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
    event_type: str | None = None
    entity_type: str | None = None
    user_id: UUID | None = None


class AdminAuditLogResponse(BaseModel):
    id: UUID
    prev_hash: str | None = None
    event_type: str
    entity_type: str
    entity_id: UUID | None = None
    user_id: UUID | None = None
    payload_json: str
    hash: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AdminVerificationRecordResponse(BaseModel):
    id: UUID
    execution_id: UUID
    task_id: UUID
    task_no: str | None = None
    status: VerificationStatus
    expected_hash: str | None = None
    actual_hash: str | None = None
    checked_at: datetime | None = None
    error_message: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AdminUserResponse(BaseModel):
    id: UUID
    username: str | None = None
    phone: str | None = None
    email: str | None = None
    nickname: str | None = None
    roles: list[str]
    is_active: bool
    balance_points: int = 0
    frozen_points: int = 0
    reserve_points: int = 0
    total_earned: int = 0
    total_spent: int = 0
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AdminUserSetActiveRequest(BaseModel):
    is_active: bool
    reason: str = Field(..., min_length=1, max_length=256)
