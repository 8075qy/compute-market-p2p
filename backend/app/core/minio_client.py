from datetime import timedelta

from minio import Minio
from minio.error import S3Error

from app.core.config import get_settings

settings = get_settings()

minio_client: Minio | None = None


def init_minio() -> None:
    global minio_client
    minio_client = Minio(
        settings.MINIO_ENDPOINT,
        access_key=settings.MINIO_ACCESS_KEY,
        secret_key=settings.MINIO_SECRET_KEY,
        secure=settings.MINIO_SECURE,
    )
    # 确保 bucket 存在
    if not minio_client.bucket_exists(settings.MINIO_BUCKET):
        minio_client.make_bucket(settings.MINIO_BUCKET)


def get_minio() -> Minio:
    if minio_client is None:
        raise RuntimeError("MinIO not initialized. Call init_minio() first.")
    return minio_client


async def get_presigned_url(object_key: str, expires: int = 3600) -> str:
    """获取对象的预签名下载 URL"""
    client = get_minio()
    return client.presigned_get_object(
        settings.MINIO_BUCKET, object_key, expires=timedelta(seconds=expires)
    )


async def get_presigned_upload_url(object_key: str, expires: int = 3600) -> str:
    """获取对象的预签名上传 URL（PUT 直传 MinIO）"""
    client = get_minio()
    return client.presigned_put_object(
        settings.MINIO_BUCKET, object_key, expires=timedelta(seconds=expires)
    )


async def upload_file(
    object_key: str, file_path: str, content_type: str = "application/octet-stream"
) -> str:
    """上传文件到 MinIO"""
    client = get_minio()
    client.fput_object(settings.MINIO_BUCKET, object_key, file_path, content_type=content_type)
    return object_key


async def upload_bytes(
    object_key: str, data: bytes, content_type: str = "application/octet-stream"
) -> str:
    """上传字节数据到 MinIO"""
    import io

    client = get_minio()
    client.put_object(
        settings.MINIO_BUCKET,
        object_key,
        io.BytesIO(data),
        length=len(data),
        content_type=content_type,
    )
    return object_key


async def delete_file(object_key: str) -> None:
    """删除 MinIO 中的文件"""
    client = get_minio()
    client.remove_object(settings.MINIO_BUCKET, object_key)


async def file_exists(object_key: str) -> bool:
    """检查文件是否存在"""
    client = get_minio()
    try:
        client.stat_object(settings.MINIO_BUCKET, object_key)
    except S3Error:
        return False
    return True


async def get_object_size(object_key: str) -> int | None:
    """获取对象大小（字节），不存在返回 None"""
    client = get_minio()
    try:
        stat = client.stat_object(settings.MINIO_BUCKET, object_key)
    except S3Error:
        return None
    return stat.size


async def get_object_bytes(object_key: str) -> bytes | None:
    """读取对象全部内容，不存在返回 None"""
    client = get_minio()
    try:
        response = client.get_object(settings.MINIO_BUCKET, object_key)
    except S3Error:
        return None
    try:
        return response.read()
    finally:
        response.close()
        response.release_conn()
