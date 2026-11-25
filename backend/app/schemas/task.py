from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models import TaskStatus, TaskType


class TaskCreate(BaseModel):
    type: TaskType = Field(..., description="任务类型")
    title: str = Field(..., min_length=1, max_length=128, description="任务标题")
    description: str | None = Field(None, max_length=2000, description="任务描述")
    model_source: str = Field(
        default="platform", pattern=r"^(platform|upload)$", description="模型来源"
    )
    model_id: str | None = Field(None, description="平台模型 ID")
    model_file_key: str | None = Field(None, description="MinIO 对象键")
    model_file_size: int | None = Field(None, ge=1, description="模型文件大小")
    input_file_key: str | None = Field(None, description="输入数据包 MinIO 对象键（batch）")
    input_file_size: int | None = Field(None, ge=1, description="输入数据包大小（batch）")
    batch_size: int = Field(default=0, ge=0, le=10000, description="每批工作项数，0 表示系统自动")
    docker_image: str | None = Field(None, max_length=256, description="执行镜像")
    command: str | None = Field(None, max_length=2000, description="启动命令")
    env_vars: dict[str, str] = Field(default_factory=dict, description="环境变量")
    params: dict[str, Any] = Field(default_factory=dict, description="任务参数")
    concurrency: int = Field(default=1, ge=1, le=10, description="初始并发数")
    min_concurrency: int = Field(default=1, ge=1, le=10, description="弹性并发下限")
    max_concurrency: int | None = Field(
        None, ge=1, le=10, description="弹性并发上限，为空则回退到 concurrency"
    )
    timeout_minutes: int = Field(default=60, ge=5, le=10080, description="超时时间(分钟)")
    required_vram_gb: int = Field(..., ge=1, le=512, description="显存需求 GB")
    required_tflops: float | None = Field(None, gt=0, le=10000, description="算力需求 TFLOPS")
    budget_points: int = Field(..., ge=1, description="积分预算上限(分)")

    @model_validator(mode="before")
    @classmethod
    def _normalize_contract(cls, data):
        if isinstance(data, dict):
            if "budget_points" not in data and "budget" in data:
                data = {**data, "budget_points": data["budget"]}
            if "timeout_minutes" not in data and "max_duration_hours" in data:
                data = {**data, "timeout_minutes": int(float(data["max_duration_hours"]) * 60)}
        return data

    @model_validator(mode="after")
    def _validate_concurrency_bounds(self):
        max_c = self.max_concurrency
        if max_c is not None:
            if max_c < self.concurrency:
                raise ValueError("max_concurrency 不能小于初始并发 concurrency")
            if max_c < self.min_concurrency:
                raise ValueError("max_concurrency 不能小于 min_concurrency")
        if self.min_concurrency > self.concurrency:
            raise ValueError("min_concurrency 不能大于初始并发 concurrency")
        return self


class TaskUpdate(BaseModel):
    params: dict[str, Any] | None = None
    concurrency: int | None = Field(None, ge=1, le=10)
    min_concurrency: int | None = Field(None, ge=1, le=10)
    max_concurrency: int | None = Field(None, ge=1, le=10)
    timeout_minutes: int | None = Field(None, ge=5, le=10080)
    required_vram_gb: int | None = Field(None, ge=1, le=512)


class TaskResponse(BaseModel):
    id: UUID
    task_no: str
    demander_id: UUID
    type: TaskType
    title: str
    description: str | None = None
    model_source: str
    model_id: UUID | None = None
    model_file_key: str | None = None
    model_file_size: int | None = None
    input_file_key: str | None = None
    input_file_size: int | None = None
    batch_size: int = 0
    total_work_units: int | None = None
    completed_work_units: int = 0
    docker_image: str | None = None
    command: str | None = None
    env_vars: dict[str, str] = Field(default_factory=dict)
    params: dict[str, Any] = Field(default_factory=dict)
    concurrency: int
    min_concurrency: int
    max_concurrency: int | None = None
    timeout_minutes: int
    required_vram_gb: int
    required_tflops: float | None = None
    budget_points: int
    min_settlement_unit: int
    status: TaskStatus
    retry_count: int
    max_retries: int
    assigned_node_id: UUID | None = None
    scheduled_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TaskExecutionResponse(BaseModel):
    id: UUID
    task_id: UUID
    node_id: UUID
    slice_index: int = 0
    attempt_no: int
    completed_work_units: int = 0
    work_unit_start: int | None = None
    work_unit_end: int | None = None
    status: TaskStatus
    started_at: datetime | None = None
    completed_at: datetime | None = None
    compute_duration_seconds: int | None = None
    compute_points: int | None = None
    platform_fee_rate: int
    platform_fee_points: int | None = None
    supplier_earnings_points: int | None = None
    error_message: str | None = None
    proof_hash: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TaskDetailResponse(TaskResponse):
    executions: list[TaskExecutionResponse] = Field(default_factory=list)
    settlements: list[SettlementResponse] = Field(default_factory=list)


class TaskListQuery(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
    status: TaskStatus | None = None
    type: TaskType | None = None


class TaskCancelRequest(BaseModel):
    pass


class TaskRetryRequest(BaseModel):
    pass


class TaskLogResponse(BaseModel):
    download_url: str
    expires_at: str


class TaskResultResponse(BaseModel):
    files: list[dict]


from app.schemas.settlement import SettlementResponse  # noqa: E402  (避免循环导入)

TaskDetailResponse.model_rebuild()
