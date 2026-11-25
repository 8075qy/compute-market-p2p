from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # App
    APP_NAME: str = "ComputeMarketP2P"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False
    API_V1_PREFIX: str = "/api/v1"

    # Database
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://dev:dev@localhost:5432/compute_market_p2p",
        description="PostgreSQL async connection string",
    )
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20

    # Redis
    REDIS_URL: str = Field(default="redis://localhost:6379/0")
    REDIS_MAX_CONNECTIONS: int = 50

    # MinIO
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_BUCKET: str = "compute-market-p2p"
    MINIO_SECURE: bool = False

    # JWT
    JWT_SECRET: str = Field(default="dev-secret-change-in-production-32chars", min_length=32)
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Security
    ARGON2_TIME_COST: int = 3
    ARGON2_MEMORY_COST: int = 65536
    ARGON2_PARALLELISM: int = 4

    # Scheduler
    SCHEDULER_INTERVAL_SECONDS: int = 30
    ELASTIC_SCALING_INTERVAL_SECONDS: int = 30  # 弹性扩容评估间隔（秒）
    SCALE_IN_LAG_SECONDS: int = 600  # 弹性缩容：分片滞后阈值（秒），超时未完成则提前终止并部分结算
    HEARTBEAT_CHECK_INTERVAL_SECONDS: int = 60
    RETRY_CHECK_INTERVAL_SECONDS: int = 60
    RESERVE_INTEREST_INTERVAL_SECONDS: int = 86400  # 储备利息分配间隔（秒），默认每天

    # Node
    NODE_OFFLINE_THRESHOLD_MINUTES: int = 5
    NODE_HEARTBEAT_INTERVAL_SECONDS: int = 30
    MAX_NODES_PER_GPU: int = 1  # 同一 GPU 唯一标识（gpu_uuid）允许注册的最大节点数，防多开
    MAX_NODES_PER_USER: int = 10  # 单账号节点数上限，防女巫批量注册供给节点
    GPU_SPEC_TFLOPS_TOLERANCE_PCT: int = 30  # 登记算力相对规格库标称值的容差（%），超出视为谎报

    # Task
    TASK_SCHEDULING_TIMEOUT_MINUTES: int = 10
    MAX_TASK_RETRIES: int = 3
    MIN_SETTLEMENT_UNIT: int = 1000  # 分，默认 10 积分
    PREAUTH_MINUTES: int = 60  # 预授权窗口（分钟），只冻结该时长的预估算力费用
    RESUME_CHECK_INTERVAL_SECONDS: int = 60  # 暂停任务恢复扫描间隔（秒）

    # Batch input（批处理数据包）
    # 数据包 zip 压缩包大小上限（1GB）
    MAX_INPUT_ARCHIVE_BYTES: int = 1024 * 1024 * 1024
    # 解压后总大小上限（10GB，zip bomb 防护）
    MAX_INPUT_UNCOMPRESSED_BYTES: int = 10 * 1024 * 1024 * 1024
    MAX_INPUT_FILES: int = 100000  # 单数据包最大文件数
    # 批处理动态领取默认档位（batch_size 未设置时按节点算力取默认批次大小）
    BATCH_SIZE_SINGLE_GPU: int = 8  # 单卡节点每批工作项数
    BATCH_SIZE_MULTI_GPU: int = 64  # 整机(多卡)节点每批工作项数

    # Settlement
    SETTLEMENT_TIMEOUT_HOURS: int = 1
    DEFAULT_PLATFORM_FEE_RATE: int = 0  # 万分比，纯对等交换不抽成

    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:8080"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
