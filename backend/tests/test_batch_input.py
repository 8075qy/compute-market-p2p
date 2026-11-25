"""批处理数据包上传测试：预签名、解压计数、manifest 生成、任务回填。"""
import io
import json
import zipfile
from unittest.mock import AsyncMock

import pytest

from app.services.batch_input import manifest_key_for


def _make_zip(files: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, content in files.items():
            zf.writestr(name, content)
    return buf.getvalue()


@pytest.mark.asyncio
async def test_presign_input_upload_rejects_non_zip(client, auth_headers):
    resp = await client.post(
        "/api/v1/demand/uploads/input/presign",
        headers=auth_headers,
        json={"filename": "data.tar.gz", "size": 1024},
    )
    assert resp.status_code == 400
    assert resp.json()["message"] == "仅支持zip格式的数据包，请重新上传"


@pytest.mark.asyncio
async def test_presign_input_upload_returns_url(test_user, client, auth_headers, monkeypatch):
    monkeypatch.setattr(
        "app.services.batch_input.get_presigned_upload_url",
        AsyncMock(return_value="https://minio/bucket/upload"),
    )

    resp = await client.post(
        "/api/v1/demand/uploads/input/presign",
        headers=auth_headers,
        json={"filename": "data.zip", "size": 1024},
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()["data"]
    assert body["object_key"].startswith(f"inputs/{test_user.id.hex}/")
    assert body["object_key"].endswith("data.zip")
    assert body["upload_url"] == "https://minio/bucket/upload"
    assert body["expires_in"] == 3600


@pytest.mark.asyncio
async def test_confirm_input_upload_counts_files_and_writes_manifest(
    test_user, client, auth_headers, monkeypatch
):
    files = {f"file_{i}.txt": b"x" * i for i in range(100)}
    zip_bytes = _make_zip(files)

    monkeypatch.setattr(
        "app.services.batch_input.get_object_size",
        AsyncMock(return_value=len(zip_bytes)),
    )
    monkeypatch.setattr(
        "app.services.batch_input.get_object_bytes",
        AsyncMock(return_value=zip_bytes),
    )

    uploaded: dict[str, bytes] = {}

    async def fake_upload_bytes(key, data, content_type="application/octet-stream"):
        uploaded[key] = data

    monkeypatch.setattr(
        "app.services.batch_input.upload_bytes",
        AsyncMock(side_effect=fake_upload_bytes),
    )

    object_key = f"inputs/{test_user.id.hex}/abc/data.zip"
    resp = await client.post(
        "/api/v1/demand/uploads/input/confirm",
        headers=auth_headers,
        json={"object_key": object_key},
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()["data"]
    assert body["file_count"] == 100
    assert body["object_key"] == object_key
    assert body["file_size"] == len(zip_bytes)

    manifest_key = f"inputs/{test_user.id.hex}/abc/manifest.json"
    assert body["manifest_key"] == manifest_key
    manifest = json.loads(uploaded[manifest_key].decode("utf-8"))
    assert manifest["count"] == 100
    assert len(manifest["files"]) == 100
    assert manifest["files"][0] == "file_0.txt"


@pytest.mark.asyncio
async def test_confirm_input_upload_rejects_empty_zip(test_user, client, auth_headers, monkeypatch):
    zip_bytes = _make_zip({})

    monkeypatch.setattr(
        "app.services.batch_input.get_object_size",
        AsyncMock(return_value=len(zip_bytes)),
    )
    monkeypatch.setattr(
        "app.services.batch_input.get_object_bytes",
        AsyncMock(return_value=zip_bytes),
    )

    resp = await client.post(
        "/api/v1/demand/uploads/input/confirm",
        headers=auth_headers,
        json={"object_key": f"inputs/{test_user.id.hex}/abc/empty.zip"},
    )

    assert resp.status_code == 400
    assert resp.json()["message"] == "数据包为空，不包含任何文件"


@pytest.mark.asyncio
async def test_confirm_input_upload_rejects_non_zip_bytes(
    test_user, client, auth_headers, monkeypatch
):
    monkeypatch.setattr(
        "app.services.batch_input.get_object_size",
        AsyncMock(return_value=10),
    )
    monkeypatch.setattr(
        "app.services.batch_input.get_object_bytes",
        AsyncMock(return_value=b"not a zip file"),
    )

    resp = await client.post(
        "/api/v1/demand/uploads/input/confirm",
        headers=auth_headers,
        json={"object_key": f"inputs/{test_user.id.hex}/abc/fake.zip"},
    )

    assert resp.status_code == 400
    assert resp.json()["message"] == "仅支持zip格式的数据包，请重新上传"


@pytest.mark.asyncio
async def test_confirm_input_upload_rejects_foreign_object(test_user, client, auth_headers):
    resp = await client.post(
        "/api/v1/demand/uploads/input/confirm",
        headers=auth_headers,
        json={"object_key": "inputs/otheruser/abc/data.zip"},
    )
    assert resp.status_code == 400
    assert resp.json()["message"] == "无权确认该上传对象"


def test_manifest_key_for():
    assert manifest_key_for("inputs/uuid/abc/data.zip") == "inputs/uuid/abc/manifest.json"


@pytest.mark.asyncio
async def test_create_batch_task_backfills_total_work_units(
    test_user, client, auth_headers, monkeypatch
):
    monkeypatch.setattr(
        "app.services.task.load_manifest_count",
        AsyncMock(return_value=1000),
    )

    resp = await client.post(
        "/api/v1/demand/tasks",
        headers=auth_headers,
        json={
            "type": "batch",
            "title": "批量推理任务",
            "required_vram_gb": 8,
            "budget_points": 10000,
            "input_file_key": f"inputs/{test_user.id.hex}/abc/data.zip",
            "input_file_size": 1024,
            "batch_size": 100,
        },
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()["data"]
    assert body["total_work_units"] == 1000
    assert body["type"] == "batch"
    assert body["input_file_key"] == f"inputs/{test_user.id.hex}/abc/data.zip"


@pytest.mark.asyncio
async def test_create_batch_task_requires_input_file_key(test_user, client, auth_headers):
    resp = await client.post(
        "/api/v1/demand/tasks",
        headers=auth_headers,
        json={
            "type": "batch",
            "title": "批量推理任务",
            "required_vram_gb": 8,
            "budget_points": 50000,
        },
    )
    assert resp.status_code == 400
    assert resp.json()["message"] == "批处理任务需要先上传输入数据包"
