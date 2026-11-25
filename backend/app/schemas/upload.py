from __future__ import annotations

from pydantic import BaseModel, Field


class PresignUploadRequest(BaseModel):
    filename: str = Field(..., min_length=1, max_length=255, description="原始文件名")
    size: int = Field(..., ge=1, description="文件大小（字节）")
    content_type: str | None = Field(
        None, max_length=128, description="MIME 类型，默认 application/octet-stream"
    )


class PresignUploadResponse(BaseModel):
    object_key: str = Field(..., description="MinIO 对象键，任务/执行记录据此引用")
    upload_url: str = Field(..., description="预签名 PUT 上传地址，可直接上传文件")
    expires_in: int = Field(..., description="预签名地址有效时长（秒）")


class UploadConfirmRequest(BaseModel):
    object_key: str = Field(..., min_length=1, max_length=512, description="待确认的 MinIO 对象键")


class UploadConfirmResponse(BaseModel):
    object_key: str = Field(..., description="已确认的 MinIO 对象键")
    exists: bool = Field(..., description="文件是否已落库")
    size: int = Field(..., description="实际文件大小（字节）")


class PresignDownloadResponse(BaseModel):
    object_key: str = Field(..., description="MinIO 对象键")
    download_url: str = Field(..., description="预签名 GET 下载地址")
    expires_in: int = Field(..., description="预签名地址有效时长（秒）")


class InputConfirmResponse(BaseModel):
    object_key: str = Field(..., description="输入数据包 MinIO 对象键")
    manifest_key: str = Field(..., description="manifest.json 对象键（文件相对路径有序列表）")
    file_count: int = Field(..., description="数据包内文件总数（即工作项数）")
    file_size: int = Field(..., description="数据包压缩后大小（字节）")


class InputDownloadResponse(BaseModel):
    """批处理任务数据包 + manifest 预签名下载地址，供 Agent 按区间取文件。"""

    input_object_key: str = Field(..., description="数据包 MinIO 对象键")
    input_download_url: str = Field(..., description="数据包预签名 GET 下载地址")
    manifest_object_key: str = Field(..., description="manifest.json 对象键")
    manifest_download_url: str = Field(..., description="manifest 预签名 GET 下载地址")
    expires_in: int = Field(..., description="预签名地址有效时长（秒）")
