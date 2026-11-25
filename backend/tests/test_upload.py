"""文件上传接口测试：模型预签名上传、上传确认、结果预签名上传。"""
import json
from unittest.mock import AsyncMock

import pytest

from app.models import (
    Task,
    TaskExecution,
    TaskStatus,
    TaskType,
)


async def _create_execution(
    db_session, test_user, online_node, status=TaskStatus.ASSIGNED
) -> TaskExecution:
    """创建任务与执行记录，节点归属供给方。"""
    task = Task(
        task_no="T202602020002",
        demander_id=test_user.id,
        type=TaskType.INFERENCE,
        title="上传测试任务",
        model_source="upload",
        params_json=json.dumps({"prompt": "hi"}),
        required_vram_gb=8,
        budget_points=5000,
        min_settlement_unit=1000,
        status=TaskStatus.RUNNING,
    )
    db_session.add(task)
    await db_session.flush()

    execution = TaskExecution(
        task_id=task.id,
        node_id=online_node.id,
        slice_index=0,
        attempt_no=1,
        status=status,
        platform_fee_rate=1000,
    )
    db_session.add(execution)
    await db_session.commit()
    await db_session.refresh(execution)
    return execution


@pytest.mark.asyncio
async def test_presign_model_upload_returns_url(test_user, client, auth_headers, monkeypatch):
    monkeypatch.setattr(
        "app.services.upload.get_presigned_upload_url",
        AsyncMock(return_value="https://minio/bucket/upload"),
    )

    resp = await client.post(
        "/api/v1/demand/uploads/model/presign",
        headers=auth_headers,
        json={"filename": "model.gguf", "size": 1024},
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()["data"]
    assert body["object_key"].startswith(f"models/{test_user.id.hex}/")
    assert body["object_key"].endswith("model.gguf")
    assert body["upload_url"] == "https://minio/bucket/upload"
    assert body["expires_in"] == 3600


@pytest.mark.asyncio
async def test_presign_model_upload_sanitizes_path(client, auth_headers, monkeypatch):
    monkeypatch.setattr(
        "app.services.upload.get_presigned_upload_url",
        AsyncMock(return_value="https://minio/bucket/upload"),
    )

    resp = await client.post(
        "/api/v1/demand/uploads/model/presign",
        headers=auth_headers,
        json={"filename": "../../etc/passwd", "size": 1024},
    )

    assert resp.status_code == 200, resp.text
    object_key = resp.json()["data"]["object_key"]
    assert object_key.endswith("passwd")
    assert "../" not in object_key


@pytest.mark.asyncio
async def test_confirm_model_upload_ok(test_user, client, auth_headers, monkeypatch):
    monkeypatch.setattr(
        "app.services.upload.get_object_size",
        AsyncMock(return_value=2048),
    )

    object_key = f"models/{test_user.id.hex}/abc/model.gguf"
    resp = await client.post(
        "/api/v1/demand/uploads/model/confirm",
        headers=auth_headers,
        json={"object_key": object_key},
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()["data"]
    assert body["exists"] is True
    assert body["size"] == 2048
    assert body["object_key"] == object_key


@pytest.mark.asyncio
async def test_confirm_model_upload_rejects_foreign_key(client, auth_headers):
    resp = await client.post(
        "/api/v1/demand/uploads/model/confirm",
        headers=auth_headers,
        json={"object_key": "models/anotheruser/abc/model.gguf"},
    )

    assert resp.status_code == 400
    assert resp.json()["code"] == 4000


@pytest.mark.asyncio
async def test_confirm_model_upload_missing_file(test_user, client, auth_headers, monkeypatch):
    monkeypatch.setattr(
        "app.services.upload.get_object_size",
        AsyncMock(return_value=None),
    )

    resp = await client.post(
        "/api/v1/demand/uploads/model/confirm",
        headers=auth_headers,
        json={"object_key": f"models/{test_user.id.hex}/abc/missing.gguf"},
    )

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_presign_result_upload_ok(
    db_session, test_user, online_node, client, supplier_headers, monkeypatch
):
    execution = await _create_execution(db_session, test_user, online_node)
    monkeypatch.setattr(
        "app.services.upload.get_presigned_upload_url",
        AsyncMock(return_value="https://minio/bucket/result"),
    )

    resp = await client.post(
        f"/api/v1/supplier/uploads/result/presign?execution_id={execution.id}",
        headers=supplier_headers,
        json={"filename": "result.json", "size": 100},
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()["data"]
    assert f"results/{execution.task_id.hex}/{execution.id.hex}/" in body["object_key"]
    assert body["object_key"].endswith("result.json")


@pytest.mark.asyncio
async def test_presign_result_upload_ownership_guard(
    db_session, test_user, online_node, client, auth_headers
):
    """非节点所有者无法为执行记录申请结果上传。"""
    execution = await _create_execution(db_session, test_user, online_node)

    resp = await client.post(
        f"/api/v1/supplier/uploads/result/presign?execution_id={execution.id}",
        headers=auth_headers,
        json={"filename": "result.json", "size": 100},
    )

    assert resp.status_code == 404
