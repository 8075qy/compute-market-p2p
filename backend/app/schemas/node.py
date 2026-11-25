from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models import NodeStatus


class NodeCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=64, description="节点名称")
    gpu_model: str = Field(..., min_length=1, max_length=64, description="GPU/NPU 型号")
    vram_gb: int = Field(..., ge=1, le=512, description="显存 GB")
    peak_tflops: float = Field(..., gt=0, le=10000, description="峰值算力 TFLOPS")
    gpu_count: int = Field(1, ge=1, le=16, description="GPU 卡数")
    region_province: str | None = Field(
        None, min_length=1, max_length=32, description="省份（可选，后期按 IP 自动获取）"
    )
    region_city: str | None = Field(
        None, min_length=1, max_length=32, description="城市（可选，后期按 IP 自动获取）"
    )
    region_district: str | None = Field(None, max_length=32, description="区县")
    docker_image: str | None = Field(None, max_length=256, description="Docker 镜像")
    config_json: str | None = Field(None, description="扩展配置 JSON")
    gpu_uuid: str | None = Field(
        None, max_length=128, description="GPU 唯一标识（防多开，agent 端实测上报）"
    )


class NodeUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=64)
    gpu_model: str | None = Field(None, min_length=1, max_length=64)
    vram_gb: int | None = Field(None, ge=1, le=512)
    peak_tflops: float | None = Field(None, gt=0, le=10000)
    gpu_count: int | None = Field(None, ge=1, le=16)
    region_province: str | None = Field(None, min_length=1, max_length=32)
    region_city: str | None = Field(None, min_length=1, max_length=32)
    region_district: str | None = Field(None, max_length=32)
    docker_image: str | None = Field(None, max_length=256)
    config_json: str | None = None
    gpu_uuid: str | None = Field(None, max_length=128)
    cached_models: list[str] | None = Field(None, description="节点已缓存的模型标识列表")


class NodeResponse(BaseModel):
    id: UUID
    owner_id: UUID
    name: str
    gpu_model: str
    vram_gb: int
    peak_tflops: float
    gpu_count: int = 1
    region_province: str | None = None
    region_city: str | None = None
    region_district: str | None = None
    gpu_uuid: str | None = None
    benchmark_tflops: float | None = None
    benchmark_status: str = "pending"
    benchmarked_at: datetime | None = None
    status: NodeStatus
    is_online: bool
    last_heartbeat_at: datetime | None = None
    gpu_utilization: float | None = None
    vram_used_gb: int | None = None
    temp_c: int | None = None
    total_tasks_completed: int
    total_points_earned: int
    reputation_score: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class NodeDetailResponse(NodeResponse):
    today_tasks: int = 0
    today_points: int = 0


class MarketplaceNodeResponse(BaseModel):
    """算力市场节点：公开展示在线 GPU 设备信息（不含 owner_id 等敏感字段）。"""

    id: UUID
    name: str
    gpu_model: str
    vram_gb: int
    peak_tflops: float
    gpu_count: int = 1
    region_province: str | None = None
    region_city: str | None = None
    status: NodeStatus
    is_online: bool
    gpu_utilization: float | None = None
    vram_used_gb: int | None = None
    total_tasks_completed: int
    reputation_score: int
    owner_nickname: str | None = None
    last_heartbeat_at: datetime | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class NodeHeartbeatRequest(BaseModel):
    gpu_util: float | None = Field(default=None, ge=0, le=100)
    gpu_utilization: float | None = Field(default=None, ge=0, le=100)
    vram_used_gb: int | None = Field(default=None, ge=0)
    temp_c: int | None = Field(default=None, ge=-50, le=150)
    temperature: int | None = Field(default=None, ge=-50, le=150)
    docker_status: str | None = Field(default=None, max_length=32)
    cached_models: list[str] | None = Field(default=None, description="节点已缓存的模型标识列表")


class BenchmarkReportRequest(BaseModel):
    benchmark_tflops: float = Field(
        ..., gt=0, le=100000, description="算力对标值 TFLOPS（规格库标称或实测）"
    )


class NodeHeartbeatResponse(BaseModel):
    online: bool
    tasks_pending: int


class NodeEarningsResponse(BaseModel):
    total_points: int
    by_period: list[dict]


class NodeExecutionResponse(BaseModel):
    id: UUID
    task_id: UUID
    task_no: str | None = None
    attempt_no: int
    status: str
    started_at: datetime | None = None
    completed_at: datetime | None = None
    compute_duration_seconds: int | None = None
    compute_points: int | None = None
    platform_fee_rate: int
    platform_fee_points: int | None = None
    supplier_earnings_points: int | None = None
    error_message: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PendingExecutionResponse(BaseModel):
    """节点待执行分片：聚合执行记录 + 任务模型信息 + 节点镜像，供 Agent 拉取执行。"""

    execution_id: UUID
    task_id: UUID
    task_no: str | None = None
    slice_index: int
    attempt_no: int
    model_source: str
    model_id: UUID | None = None
    model_file_key: str | None = None
    model_file_size: int | None = None
    params: dict = Field(default_factory=dict)
    command: str | None = None
    env_vars: dict = Field(default_factory=dict)
    challenge_nonce: str | None = Field(
        None, description="本次执行的防重放挑战种子，需绑定到 proof_hash"
    )
    timeout_minutes: int
    docker_image: str | None = None
    # 批处理任务工作项区间（半开区间 [work_unit_start, work_unit_end)），非批处理任务为 None
    work_unit_start: int | None = None
    work_unit_end: int | None = None
    # 批处理任务数据包与清单对象键，供 Agent 按区间取文件；非批处理任务为 None
    input_file_key: str | None = None
    manifest_key: str | None = None
    created_at: datetime


class ExecutionStateResponse(BaseModel):
    id: UUID
    task_id: UUID
    node_id: UUID
    slice_index: int
    attempt_no: int
    status: str
    started_at: datetime | None = None
    completed_at: datetime | None = None
    compute_duration_seconds: int | None = None
    compute_points: int | None = None
    supplier_earnings_points: int | None = None
    error_message: str | None = None
    proof_hash: str | None = None

    model_config = ConfigDict(from_attributes=True)


class ExecutionCompleteRequest(BaseModel):
    result_files: list[dict] = Field(
        default_factory=list, description="结果文件列表 [{key,name,size}]"
    )
    proof_hash: str | None = Field(None, max_length=64, description="结果内容哈希(算力证明)")
    compute_duration_seconds: int | None = Field(None, ge=0, description="实际算力时长(秒)")
    execution_log_key: str | None = Field(None, max_length=256, description="执行日志对象键")
    completed_work_units: int | None = Field(
        None, ge=0, description="批处理批次完成的工作项数（= end - start）"
    )


class ExecutionFailRequest(BaseModel):
    error_message: str = Field(..., min_length=1, max_length=500, description="失败原因")
