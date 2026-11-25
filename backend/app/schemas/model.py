from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ModelCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128, description="模型名称")
    framework: str = Field(
        ..., min_length=1, max_length=32, description="框架（pytorch/onnx/gguf 等）"
    )
    size_bytes: int = Field(0, ge=0, description="模型大小（字节）")
    required_vram_gb: int = Field(0, ge=0, le=512, description="推荐显存需求 GB")
    source: str = Field(
        default="huggingface", max_length=32, description="来源（huggingface/modelscope/minio）"
    )
    content_hash: str | None = Field(None, max_length=64, description="内容哈希（SHA-256）")
    minio_key: str | None = Field(None, max_length=256, description="MinIO 对象键")
    description: str | None = Field(None, max_length=2000, description="模型描述")
    is_published: bool = Field(default=False, description="是否上架")


class ModelUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=128)
    framework: str | None = Field(None, min_length=1, max_length=32)
    size_bytes: int | None = Field(None, ge=0)
    required_vram_gb: int | None = Field(None, ge=0, le=512)
    source: str | None = Field(None, max_length=32)
    content_hash: str | None = Field(None, max_length=64)
    minio_key: str | None = Field(None, max_length=256)
    description: str | None = Field(None, max_length=2000)
    is_published: bool | None = None


class ModelResponse(BaseModel):
    id: UUID
    name: str
    framework: str
    size_bytes: int
    required_vram_gb: int
    source: str
    content_hash: str | None = None
    minio_key: str | None = None
    description: str | None = None
    is_published: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ModelListQuery(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
    keyword: str | None = Field(None, max_length=128, description="按名称模糊搜索")
    framework: str | None = Field(None, max_length=32)
