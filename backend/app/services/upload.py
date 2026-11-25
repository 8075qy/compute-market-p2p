"""文件上传服务：生成模型/结果预签名上传地址，并校验上传完成。"""
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BusinessError, NotFoundError
from app.core.minio_client import (
    get_object_size,
    get_presigned_upload_url,
    get_presigned_url,
)
from app.models import Node, PlatformModel, Task, TaskExecution, TaskStatus
from app.schemas.upload import (
    InputDownloadResponse,
    PresignDownloadResponse,
    PresignUploadRequest,
    PresignUploadResponse,
    UploadConfirmRequest,
    UploadConfirmResponse,
)

MODEL_UPLOAD_EXPIRES = 3600  # 模型文件较大，预签名地址有效期 1 小时
RESULT_UPLOAD_EXPIRES = 3600
MODEL_DOWNLOAD_EXPIRES = 3600


def _safe_name(filename: str) -> str:
    """去除目录与路径穿越，仅保留文件名。"""
    name = filename.replace("\\", "/").rsplit("/", 1)[-1].strip()
    return name or "file"


class UploadService:
    """预签名上传业务层，对象键由后端生成，客户端不可指定。"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def presign_model_upload(
        self, user_id: uuid.UUID, data: PresignUploadRequest
    ) -> PresignUploadResponse:
        """需求方申请模型上传预签名地址，生成 `models/{user}/{uuid}/{文件名}` 对象键。"""
        object_key = f"models/{user_id.hex}/{uuid.uuid4().hex}/{_safe_name(data.filename)}"
        upload_url = await get_presigned_upload_url(object_key, MODEL_UPLOAD_EXPIRES)
        return PresignUploadResponse(
            object_key=object_key, upload_url=upload_url, expires_in=MODEL_UPLOAD_EXPIRES
        )

    async def confirm_model_upload(
        self, user_id: uuid.UUID, data: UploadConfirmRequest
    ) -> UploadConfirmResponse:
        """需求方确认模型文件已上传：校验对象归属并核对 MinIO 实际落库大小。"""
        prefix = f"models/{user_id.hex}/"
        if not data.object_key.startswith(prefix):
            raise BusinessError("无权确认该上传对象")

        size = await get_object_size(data.object_key)
        if size is None:
            raise NotFoundError("文件未上传完成或不存在")
        return UploadConfirmResponse(object_key=data.object_key, exists=True, size=size)

    async def presign_result_upload(
        self, user_id: uuid.UUID, execution_id: uuid.UUID, data: PresignUploadRequest
    ) -> PresignUploadResponse:
        """供给方节点申请结果上传预签名地址，对象键挂载到执行记录所属任务。"""
        execution = await self._get_owned_execution(execution_id, user_id)
        if execution.status not in (TaskStatus.ASSIGNED, TaskStatus.RUNNING):
            raise BusinessError(f"当前状态({execution.status.value})无法上传结果")

        object_key = (
            f"results/{execution.task_id.hex}/{execution.id.hex}/"
            f"{uuid.uuid4().hex}/{_safe_name(data.filename)}"
        )
        upload_url = await get_presigned_upload_url(object_key, RESULT_UPLOAD_EXPIRES)
        return PresignUploadResponse(
            object_key=object_key, upload_url=upload_url, expires_in=RESULT_UPLOAD_EXPIRES
        )

    async def presign_model_download(
        self, user_id: uuid.UUID, execution_id: uuid.UUID
    ) -> PresignDownloadResponse:
        """供给方节点下载分配给自己的任务模型，返回预签名下载地址。

        兼容两种模型来源：upload（task.model_file_key 指向 MinIO 对象键）、
        platform（通过 model_id 关联平台模型库的 minio_key）。
        """
        execution = await self._get_owned_execution(execution_id, user_id)
        task = await self.session.get(Task, execution.task_id)
        if not task:
            raise NotFoundError("任务不存在")

        object_key: str | None = task.model_file_key
        if not object_key and task.model_source == "platform" and task.model_id:
            platform = await self.session.get(PlatformModel, task.model_id)
            if platform:
                object_key = platform.minio_key

        if not object_key:
            raise BusinessError("该任务未关联可下载的模型文件")

        download_url = await get_presigned_url(object_key, MODEL_DOWNLOAD_EXPIRES)
        return PresignDownloadResponse(
            object_key=object_key,
            download_url=download_url,
            expires_in=MODEL_DOWNLOAD_EXPIRES,
        )

    async def presign_input_download(
        self, user_id: uuid.UUID, execution_id: uuid.UUID
    ) -> InputDownloadResponse:
        """供给方节点下载批处理任务的数据包与 manifest，返回两组预签名下载地址。"""
        execution = await self._get_owned_execution(execution_id, user_id)
        task = await self.session.get(Task, execution.task_id)
        if not task:
            raise NotFoundError("任务不存在")

        if not task.input_file_key:
            raise BusinessError("该任务未关联可下载的数据包")

        from app.services.batch_input import manifest_key_for  # noqa: PLC0415

        input_key = task.input_file_key
        manifest_key = manifest_key_for(input_key)
        input_url = await get_presigned_url(input_key, MODEL_DOWNLOAD_EXPIRES)
        manifest_url = await get_presigned_url(manifest_key, MODEL_DOWNLOAD_EXPIRES)
        return InputDownloadResponse(
            input_object_key=input_key,
            input_download_url=input_url,
            manifest_object_key=manifest_key,
            manifest_download_url=manifest_url,
            expires_in=MODEL_DOWNLOAD_EXPIRES,
        )

    async def _get_owned_execution(
        self, execution_id: uuid.UUID, user_id: uuid.UUID
    ) -> TaskExecution:
        """校验执行记录归属：执行记录的节点必须属于当前用户。"""
        stmt = (
            select(TaskExecution)
            .join(Node, Node.id == TaskExecution.node_id)
            .where(TaskExecution.id == execution_id, Node.owner_id == user_id)
        )
        execution = (await self.session.execute(stmt)).scalar_one_or_none()
        if not execution:
            raise NotFoundError("执行记录不存在或无权访问")
        return execution
