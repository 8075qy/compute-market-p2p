import enum
import json
import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class UserRole(str, enum.Enum):
    """用户身份：普通用户（供需一体）或平台管理员。"""

    USER = "user"
    ADMIN = "admin"


class SettlementRole(str, enum.Enum):
    """结算方向：仅用于结算记录标记，与用户身份无关。"""

    SUPPLIER = "supplier"
    DEMANDER = "demander"


class NodeStatus(str, enum.Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    MAINTENANCE = "maintenance"


class BenchmarkStatus(str, enum.Enum):
    """节点算力对标状态：pending 未对标 / verified 通过 / failed 谎报异常。"""

    PENDING = "pending"
    VERIFIED = "verified"
    FAILED = "failed"


class TaskStatus(str, enum.Enum):
    PENDING = "pending"
    SCHEDULING = "scheduling"
    ASSIGNED = "assigned"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskType(str, enum.Enum):
    INFERENCE = "inference"
    TRAINING = "training"
    BATCH = "batch"


class SettlementStatus(str, enum.Enum):
    PENDING = "pending"
    SETTLED = "settled"
    REFUNDING = "refunding"
    REFUNDED = "refunded"
    REVERSED = "reversed"


class VerificationStatus(str, enum.Enum):
    PENDING = "pending"
    VERIFIED = "verified"
    FAILED = "failed"


class NotificationType(str, enum.Enum):
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"
    TASK_ASSIGNED = "task_assigned"
    TASK_STARTED = "task_started"
    TASK_CANCELLED = "task_cancelled"
    SETTLEMENT_PAID = "settlement_paid"
    NODE_ONLINE = "node_online"
    NODE_OFFLINE = "node_offline"
    SYSTEM = "system"


# 用户表
class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    phone: Mapped[str | None] = mapped_column(String(20), unique=True, index=True, nullable=True)
    username: Mapped[str | None] = mapped_column(String(64), unique=True, index=True, nullable=True)
    email: Mapped[str | None] = mapped_column(String(128), unique=True, index=True, nullable=True)
    password_hash: Mapped[str] = mapped_column(String(256), nullable=False)
    roles: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    nickname: Mapped[str | None] = mapped_column(String(64), nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    nodes: Mapped[list["Node"]] = relationship(back_populates="owner")
    tasks: Mapped[list["Task"]] = relationship(back_populates="demander")
    account: Mapped["Account"] = relationship(back_populates="user", uselist=False)
    settlements: Mapped[list["Settlement"]] = relationship(back_populates="user")
    notifications: Mapped[list["Notification"]] = relationship(back_populates="user")

    def has_role(self, role: UserRole) -> bool:
        """判断用户是否具备指定身份（普通用户/管理员）。"""
        return role.value in (self.roles or [])


# 积分账户表
class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    balance_points: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    reserve_points: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    frozen_points: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    total_earned: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    total_spent: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    user: Mapped["User"] = relationship(back_populates="account")


# 节点表
class Node(Base):
    __tablename__ = "nodes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    gpu_model: Mapped[str] = mapped_column(String(64), nullable=False)
    vram_gb: Mapped[int] = mapped_column(Integer, nullable=False)
    peak_tflops: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    gpu_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    region_province: Mapped[str | None] = mapped_column(String(32), nullable=True)
    region_city: Mapped[str | None] = mapped_column(String(32), nullable=True)
    region_district: Mapped[str | None] = mapped_column(String(32), nullable=True)
    status: Mapped[NodeStatus] = mapped_column(
        Enum(NodeStatus), default=NodeStatus.OFFLINE, nullable=False, index=True
    )
    is_online: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_heartbeat_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    gpu_utilization: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    vram_used_gb: Mapped[int | None] = mapped_column(Integer, nullable=True)
    temp_c: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_tasks_completed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_points_earned: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    reputation_score: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    docker_image: Mapped[str | None] = mapped_column(String(256), nullable=True)
    config_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    gpu_uuid: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    benchmark_tflops: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    benchmark_status: Mapped[BenchmarkStatus] = mapped_column(
        Enum(BenchmarkStatus, name="benchmark_status"),
        default=BenchmarkStatus.PENDING,
        nullable=False,
    )
    benchmarked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cached_models_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    owner: Mapped["User"] = relationship(back_populates="nodes")
    executions: Mapped[list["TaskExecution"]] = relationship(back_populates="node")

    @property
    def owner_phone(self) -> str | None:
        return self.owner.phone if self.owner else None

    @property
    def owner_nickname(self) -> str | None:
        return self.owner.nickname if self.owner else None

    @property
    def cached_models(self) -> list[str]:
        """节点已缓存的模型标识列表（模型 ID 或 MinIO 对象键），用于调度命中评分。"""
        try:
            return json.loads(self.cached_models_json) if self.cached_models_json else []
        except (TypeError, ValueError):
            return []

    __table_args__ = (
        Index("ix_nodes_owner_status", "owner_id", "status"),
        Index("ix_nodes_schedulable", "is_online", "status", "vram_gb", "peak_tflops"),
    )


# 任务表
class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_no: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)
    demander_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    type: Mapped[TaskType] = mapped_column(Enum(TaskType), nullable=False)
    title: Mapped[str] = mapped_column(String(128), nullable=False, server_default="")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    model_source: Mapped[str] = mapped_column(String(32), nullable=False)
    model_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    model_file_key: Mapped[str | None] = mapped_column(String(256), nullable=True)
    model_file_size: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    docker_image: Mapped[str | None] = mapped_column(String(256), nullable=True)
    command: Mapped[str | None] = mapped_column(Text, nullable=True)
    env_vars_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    params_json: Mapped[str] = mapped_column(Text, nullable=False)
    concurrency: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    # 弹性伸缩：并发上下限；max_concurrency 为 NULL 时回退到 concurrency
    min_concurrency: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    max_concurrency: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # 弹性进度：total_work_units 为 NULL 表示「分片数即总量」，否则按进度追加分片
    total_work_units: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    completed_work_units: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    # 批处理：输入数据包（zip）与每批工作项数；batch_size=0 表示系统自动决定
    input_file_key: Mapped[str | None] = mapped_column(String(256), nullable=True)
    input_file_size: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    batch_size: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    timeout_minutes: Mapped[int] = mapped_column(Integer, default=60, nullable=False)
    required_vram_gb: Mapped[int] = mapped_column(Integer, nullable=False)
    required_tflops: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    budget_points: Mapped[int] = mapped_column(BigInteger, nullable=False)
    preauthorized_points: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    min_settlement_unit: Mapped[int] = mapped_column(Integer, default=1000, nullable=False)
    status: Mapped[TaskStatus] = mapped_column(
        Enum(TaskStatus), default=TaskStatus.PENDING, nullable=False, index=True
    )
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_retries: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    assigned_node_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("nodes.id", ondelete="SET NULL"), nullable=True
    )
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    result_files_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    demander: Mapped["User"] = relationship(back_populates="tasks")
    executions: Mapped[list["TaskExecution"]] = relationship(back_populates="task")
    settlements: Mapped[list["Settlement"]] = relationship(back_populates="task")

    @property
    def params(self) -> dict:
        try:
            return json.loads(self.params_json) if self.params_json else {}
        except (TypeError, ValueError):
            return {}

    @property
    def env_vars(self) -> dict:
        try:
            return json.loads(self.env_vars_json) if self.env_vars_json else {}
        except (TypeError, ValueError):
            return {}

    @property
    def demander_phone(self) -> str | None:
        return self.demander.phone if self.demander else None

    __table_args__ = (
        Index("ix_tasks_demander_status", "demander_id", "status"),
        Index("ix_tasks_scheduling", "status", "created_at"),
    )


# 任务执行记录表
class TaskExecution(Base):
    __tablename__ = "task_executions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    node_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("nodes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    slice_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    attempt_no: Mapped[int] = mapped_column(Integer, nullable=False)
    # 该分片已完成的工作单元数（随进度上报递增）
    completed_work_units: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    # 批处理：该执行负责的工作项半开区间 [work_unit_start, work_unit_end)
    work_unit_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    work_unit_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[TaskStatus] = mapped_column(
        Enum(TaskStatus), default=TaskStatus.ASSIGNED, nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    compute_duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    compute_points: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    platform_fee_rate: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    platform_fee_points: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    supplier_earnings_points: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    reserve_points: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    execution_log_key: Mapped[str | None] = mapped_column(String(256), nullable=True)
    proof_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # 防重放：每次执行唯一的随机挑战种子，绑定到 proof_hash，使结果无法跨次缓存复用
    challenge_nonce: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    task: Mapped["Task"] = relationship(back_populates="executions")
    node: Mapped["Node"] = relationship(back_populates="executions")
    settlements: Mapped[list["Settlement"]] = relationship(back_populates="execution")
    verification_records: Mapped[list["VerificationRecord"]] = relationship(
        back_populates="execution", cascade="all, delete-orphan"
    )

    @property
    def task_no(self) -> str | None:
        return self.task.task_no if self.task else None

    __table_args__ = (
        UniqueConstraint("task_id", "slice_index", "attempt_no", name="uq_task_attempt"),
        Index("ix_executions_node_status", "node_id", "status"),
    )


# 结算记录表
class Settlement(Base):
    __tablename__ = "settlements"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    settlement_no: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    execution_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("task_executions.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[SettlementRole] = mapped_column(Enum(SettlementRole), nullable=False)
    compute_points: Mapped[int] = mapped_column(BigInteger, nullable=False)
    platform_fee_rate: Mapped[int] = mapped_column(Integer, nullable=False)
    platform_fee_points: Mapped[int] = mapped_column(BigInteger, nullable=False)
    net_points: Mapped[int] = mapped_column(BigInteger, nullable=False)
    destination_account: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[SettlementStatus] = mapped_column(
        Enum(SettlementStatus), default=SettlementStatus.PENDING, nullable=False, index=True
    )
    settled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    user: Mapped["User"] = relationship(back_populates="settlements")
    task: Mapped["Task"] = relationship(back_populates="settlements")
    execution: Mapped["TaskExecution"] = relationship(back_populates="settlements")

    @property
    def task_no(self) -> str | None:
        return self.task.task_no if self.task else None

    __table_args__ = (
        Index("ix_settlements_user_status", "user_id", "status"),
        Index("ix_settlements_task", "task_id"),
        Index("ix_settlements_execution", "execution_id"),
    )


# 采样复核记录表（D1 第二阶段：结果抽样重算验证）
class VerificationRecord(Base):
    __tablename__ = "verification_records"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    execution_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("task_executions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[VerificationStatus] = mapped_column(
        Enum(VerificationStatus, name="verification_status"),
        default=VerificationStatus.PENDING,
        nullable=False,
    )
    expected_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    actual_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    result_files_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    execution: Mapped["TaskExecution"] = relationship(back_populates="verification_records")
    task: Mapped["Task"] = relationship()

    @property
    def task_no(self) -> str | None:
        return self.task.task_no if self.task else None

    __table_args__ = (Index("ix_verification_records_status", "status", "created_at"),)


# 平台配置表
class PlatformConfig(Base):
    __tablename__ = "platform_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    platform_fee_rate: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    min_settlement_unit: Mapped[int] = mapped_column(Integer, default=1000, nullable=False)
    max_task_retries: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    node_offline_threshold_minutes: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    task_scheduling_timeout_minutes: Mapped[int] = mapped_column(
        Integer, default=10, nullable=False
    )
    settlement_timeout_hours: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    verification_sample_rate: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    reserve_ratio: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    max_borrow_ratio: Mapped[int] = mapped_column(Integer, default=20, nullable=False)
    reserve_interest_ratio: Mapped[int] = mapped_column(Integer, default=50, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    updated_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)


# 审计日志表
class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    prev_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(32), nullable=False)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    __table_args__ = (
        Index("ix_audit_logs_chain", "prev_hash"),
        Index("ix_audit_logs_entity", "entity_type", "entity_id"),
    )


# 平台模型库表
class PlatformModel(Base):
    __tablename__ = "platform_models"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    framework: Mapped[str] = mapped_column(String(32), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    required_vram_gb: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    source: Mapped[str] = mapped_column(String(32), default="huggingface", nullable=False)
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    minio_key: Mapped[str | None] = mapped_column(String(256), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_published: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    __table_args__ = (Index("ix_platform_models_published", "is_published", "created_at"),)


# GPU 规格库表（显存/峰值算力参考数据，减少节点登记手填）
class GpuSpec(Base):
    __tablename__ = "gpu_specs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    gpu_model: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    vendor: Mapped[str] = mapped_column(String(16), nullable=False)
    vram_gb: Mapped[int] = mapped_column(Integer, nullable=False)
    peak_tflops: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    aliases_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    @property
    def aliases(self) -> list[str]:
        try:
            return json.loads(self.aliases_json) if self.aliases_json else []
        except (TypeError, ValueError):
            return []


# 通知表
class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    type: Mapped[NotificationType] = mapped_column(
        Enum(NotificationType, name="notification_type"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(128), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    ref_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped["User"] = relationship(back_populates="notifications")

    __table_args__ = (Index("ix_notifications_user_read", "user_id", "is_read"),)


# 储备利息分配记录表（算力时间银行：公共池产出按储备占比返还的周期快照）
class ReserveInterestRecord(Base):
    __tablename__ = "reserve_interest_records"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    cycle_output_points: Mapped[int] = mapped_column(BigInteger, nullable=False)
    interest_points: Mapped[int] = mapped_column(BigInteger, nullable=False)
    total_reserve_points: Mapped[int] = mapped_column(BigInteger, nullable=False)
    distributed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    __table_args__ = (Index("ix_reserve_interest_records_created", "distributed_at"),)


# 储备利息分配明细表（算力时间银行：每轮分配给单账户的利息明细，用于利息明细查询）
class ReserveInterestAllocation(Base):
    __tablename__ = "reserve_interest_allocations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    record_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("reserve_interest_records.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    reserve_points_before: Mapped[int] = mapped_column(BigInteger, nullable=False)
    interest_points: Mapped[int] = mapped_column(BigInteger, nullable=False)
    distributed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    __table_args__ = (Index("ix_reserve_interest_allocations_user", "user_id", "distributed_at"),)


# 储备借用流水表（算力时间银行：用户取用储备分转为自由分的记录）
class ReserveBorrowRecord(Base):
    __tablename__ = "reserve_borrow_records"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    amount_points: Mapped[int] = mapped_column(BigInteger, nullable=False)
    balance_before: Mapped[int] = mapped_column(BigInteger, nullable=False)
    reserve_before: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    __table_args__ = (Index("ix_reserve_borrow_records_user", "user_id", "created_at"),)
