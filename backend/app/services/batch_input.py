"""批处理数据包服务：数据包预签名上传、解压计数、manifest 生成。

工作项语义：数据包（zip）按包内文件切分，`work_unit i` 对应 manifest 中的第 i 个文件。
MVP 仅支持 zip，计数只解析 zip 中央目录（infolist），不实际解压文件内容，速度快且可防 zip bomb。
"""
import io
import json
import uuid
import zipfile

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import BusinessError, NotFoundError
from app.core.minio_client import (
    get_object_bytes,
    get_object_size,
    get_presigned_upload_url,
    upload_bytes,
)
from app.schemas.upload import InputConfirmResponse, PresignUploadResponse
from app.services.upload import _safe_name

INPUT_UPLOAD_EXPIRES = 3600


def manifest_key_for(input_file_key: str) -> str:
    """由数据包对象键推导 manifest 对象键（同目录下的 manifest.json）。"""
    base = input_file_key.rsplit("/", 1)[0]
    return f"{base}/manifest.json"


async def load_manifest_count(input_file_key: str) -> int:
    """读取数据包 manifest 的文件数，供任务创建时回填 total_work_units。"""
    manifest_key = manifest_key_for(input_file_key)
    data = await get_object_bytes(manifest_key)
    if data is None:
        raise BusinessError("数据包尚未处理完成，请先确认数据包上传")
    try:
        manifest = json.loads(data.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise BusinessError("数据包清单格式错误") from exc
    count = manifest.get("count", 0)
    if not isinstance(count, int) or count <= 0:
        raise BusinessError("数据包清单中无有效文件")
    return count


class BatchInputService:
    """数据包上传与工作项计数。"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def presign_input_upload(
        self, user_id: uuid.UUID, filename: str
    ) -> PresignUploadResponse:
        """数据包上传预签名地址；MVP 仅支持 zip。"""
        safe_name = _safe_name(filename)
        if not safe_name.lower().endswith(".zip"):
            raise BusinessError("仅支持zip格式的数据包，请重新上传")

        object_key = f"inputs/{user_id.hex}/{uuid.uuid4().hex}/{safe_name}"
        upload_url = await get_presigned_upload_url(object_key, INPUT_UPLOAD_EXPIRES)
        return PresignUploadResponse(
            object_key=object_key, upload_url=upload_url, expires_in=INPUT_UPLOAD_EXPIRES
        )

    async def confirm_input_upload(
        self, user_id: uuid.UUID, object_key: str
    ) -> InputConfirmResponse:
        """确认数据包已上传：校验归属、大小与 zip 格式，生成 manifest 并回传 MinIO。"""
        prefix = f"inputs/{user_id.hex}/"
        if not object_key.startswith(prefix):
            raise BusinessError("无权确认该上传对象")

        settings = get_settings()
        size = await get_object_size(object_key)
        if size is None:
            raise NotFoundError("数据包未上传完成或不存在")
        if size == 0:
            raise BusinessError("数据包为空，请重新上传")
        if size > settings.MAX_INPUT_ARCHIVE_BYTES:
            raise BusinessError("数据包超过大小上限，请拆分后重新上传")

        data = await get_object_bytes(object_key)
        if data is None:
            raise NotFoundError("数据包未上传完成或不存在")

        files = _scan_zip(data, settings)
        manifest_key = manifest_key_for(object_key)
        manifest = {"version": 1, "count": len(files), "files": files}
        await upload_bytes(
            manifest_key,
            json.dumps(manifest, ensure_ascii=False, sort_keys=True).encode("utf-8"),
            content_type="application/json",
        )
        return InputConfirmResponse(
            object_key=object_key,
            manifest_key=manifest_key,
            file_count=len(files),
            file_size=size,
        )


def _scan_zip(data: bytes, settings) -> list[str]:
    """解析 zip 中央目录，返回文件相对路径有序列表（不含目录项）。"""
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            infos = zf.infolist()
    except zipfile.BadZipFile as exc:
        raise BusinessError("仅支持zip格式的数据包，请重新上传") from exc

    file_infos = [i for i in infos if not i.is_dir()]
    if not file_infos:
        raise BusinessError("数据包为空，不包含任何文件")

    if len(file_infos) > settings.MAX_INPUT_FILES:
        raise BusinessError(f"数据包文件数超过上限:{settings.MAX_INPUT_FILES}")

    total_uncompressed = sum(i.file_size for i in file_infos)
    if total_uncompressed > settings.MAX_INPUT_UNCOMPRESSED_BYTES:
        raise BusinessError("数据包解压后体积过大，请拆分后重新上传")

    return sorted(i.filename for i in file_infos)
