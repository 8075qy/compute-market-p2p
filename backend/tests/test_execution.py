"""执行闭环接口测试：领取 → 开始 → 完成/失败 → 结算/重试。"""

import json
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.models import (
    Account,
    Settlement,
    SettlementRole,
    Task,
    TaskExecution,
    TaskStatus,
    TaskType,
)


async def _create_assigned_execution(
    db_session, test_user, online_node, task_no="T202602020001", **kwargs
) -> TaskExecution:
    """创建一个已分配（ASSIGNED）的单分片执行记录及其任务、冻结预算。"""
    task = Task(
        task_no=task_no,
        demander_id=test_user.id,
        type=TaskType.INFERENCE,
        title="执行测试任务",
        model_source="upload",
        model_file_key="models/test-model.bin",
        params_json=json.dumps({"prompt": "hello"}),
        required_vram_gb=8,
        budget_points=5000,
        preauthorized_points=5000,
        min_settlement_unit=1000,
        status=TaskStatus.ASSIGNED,
        **kwargs,
    )
    db_session.add(task)
    await db_session.flush()

    # 冻结需求方预算，模拟发布任务时的冻结
    account = (
        await db_session.execute(select(Account).where(Account.user_id == test_user.id))
    ).scalar_one()
    account.balance_points -= task.budget_points
    account.frozen_points += task.budget_points

    execution = TaskExecution(
        task_id=task.id,
        node_id=online_node.id,
        slice_index=0,
        attempt_no=1,
        status=TaskStatus.ASSIGNED,
        platform_fee_rate=1000,
        challenge_nonce="testnonce",
    )
    db_session.add(execution)
    await db_session.commit()
    await db_session.refresh(execution)
    return execution


@pytest.mark.asyncio
async def test_pending_executions_returns_assigned_slice(
    db_session, test_user, online_node, client, supplier_headers
):
    execution = await _create_assigned_execution(db_session, test_user, online_node)

    resp = await client.get(
        f"/api/v1/supplier/nodes/{online_node.id}/pending-executions",
        headers=supplier_headers,
    )

    assert resp.status_code == 200, resp.text
    items = resp.json()["data"]
    assert len(items) == 1
    assert items[0]["execution_id"] == str(execution.id)
    assert items[0]["task_no"] == "T202602020001"
    assert items[0]["model_file_key"] == "models/test-model.bin"
    assert items[0]["params"] == {"prompt": "hello"}


@pytest.mark.asyncio
async def test_start_execution_transitions_to_running(
    db_session, test_user, online_node, client, supplier_headers
):
    execution = await _create_assigned_execution(db_session, test_user, online_node)

    resp = await client.post(
        f"/api/v1/supplier/executions/{execution.id}/start",
        headers=supplier_headers,
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()["data"]
    assert body["status"] == "running"
    assert body["started_at"] is not None

    await db_session.refresh(execution)
    assert execution.status == TaskStatus.RUNNING
    assert execution.started_at is not None


@pytest.mark.asyncio
async def test_complete_execution_settles_and_finalizes_task(
    db_session, test_user, test_supplier, online_node, client, supplier_headers
):
    execution = await _create_assigned_execution(db_session, test_user, online_node)
    # 先进入运行态
    await client.post(
        f"/api/v1/supplier/executions/{execution.id}/start",
        headers=supplier_headers,
    )

    resp = await client.post(
        f"/api/v1/supplier/executions/{execution.id}/complete",
        headers=supplier_headers,
        json={
            "compute_duration_seconds": 3600,
            "proof_hash": "a" * 64,
            "result_files": [{"key": "results/r1.bin", "name": "r1.bin", "size": 128}],
        },
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()["data"]
    assert body["status"] == "completed"
    assert body["compute_points"] is not None and body["compute_points"] > 0

    await db_session.refresh(execution)
    assert execution.status == TaskStatus.COMPLETED
    assert execution.proof_hash == "a" * 64

    task = await db_session.get(Task, execution.task_id)
    await db_session.refresh(task)
    assert task.status == TaskStatus.COMPLETED
    result_files = json.loads(task.result_files_json)
    assert result_files == [{"key": "results/r1.bin", "name": "r1.bin", "size": 128}]

    # 供给方入账
    supplier_account = (
        await db_session.execute(select(Account).where(Account.user_id == test_supplier.id))
    ).scalar_one()
    assert (
        supplier_account.balance_points + supplier_account.reserve_points
        == execution.supplier_earnings_points
    )

    # 生成供给方结算单
    settlement = (
        await db_session.execute(
            select(Settlement).where(
                Settlement.execution_id == execution.id,
                Settlement.role == SettlementRole.SUPPLIER,
            )
        )
    ).scalar_one()
    assert settlement.net_points == execution.supplier_earnings_points


@pytest.mark.asyncio
async def test_fail_execution_triggers_retry(
    db_session, test_user, online_node, client, supplier_headers
):
    execution = await _create_assigned_execution(db_session, test_user, online_node)
    await client.post(
        f"/api/v1/supplier/executions/{execution.id}/start",
        headers=supplier_headers,
    )

    resp = await client.post(
        f"/api/v1/supplier/executions/{execution.id}/fail",
        headers=supplier_headers,
        json={"error_message": "OOM"},
    )

    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["status"] == "failed"

    await db_session.refresh(execution)
    assert execution.status == TaskStatus.FAILED
    assert execution.error_message == "OOM"

    # 单分片任务触发重新调度
    task = await db_session.get(Task, execution.task_id)
    await db_session.refresh(task)
    assert task.status == TaskStatus.SCHEDULING
    assert task.retry_count == 1


@pytest.mark.asyncio
async def test_complete_idempotent_rejects_duplicate(
    db_session, test_user, online_node, client, supplier_headers
):
    execution = await _create_assigned_execution(db_session, test_user, online_node)
    await client.post(
        f"/api/v1/supplier/executions/{execution.id}/start",
        headers=supplier_headers,
    )
    await client.post(
        f"/api/v1/supplier/executions/{execution.id}/complete",
        headers=supplier_headers,
        json={"compute_duration_seconds": 100},
    )

    resp = await client.post(
        f"/api/v1/supplier/executions/{execution.id}/complete",
        headers=supplier_headers,
        json={"compute_duration_seconds": 100},
    )

    assert resp.status_code == 400
    assert resp.json()["code"] == 4000


@pytest.mark.asyncio
async def test_execution_ownership_guard(db_session, test_user, online_node, client, auth_headers):
    """非节点所有者无法操作执行记录。"""
    execution = await _create_assigned_execution(db_session, test_user, online_node)

    # 需求方（非节点所有者）尝试操作
    resp = await client.post(
        f"/api/v1/supplier/executions/{execution.id}/start",
        headers=auth_headers,
    )

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_complete_requires_proof_hash_with_result_files(
    db_session, test_user, online_node, client, supplier_headers
):
    """D1：上报结果文件时必须携带算力证明 proof_hash。"""
    execution = await _create_assigned_execution(db_session, test_user, online_node)
    await client.post(
        f"/api/v1/supplier/executions/{execution.id}/start",
        headers=supplier_headers,
    )

    resp = await client.post(
        f"/api/v1/supplier/executions/{execution.id}/complete",
        headers=supplier_headers,
        json={
            "compute_duration_seconds": 100,
            "result_files": [{"key": "results/r1.bin", "name": "r1.bin", "size": 128}],
        },
    )

    assert resp.status_code == 400
    assert resp.json()["code"] == 4000

    await db_session.refresh(execution)
    assert execution.status == TaskStatus.RUNNING


@pytest.mark.asyncio
async def test_complete_dedupes_result_files_by_key(
    db_session, test_user, online_node, client, supplier_headers
):
    """C1：同一结果对象键重复上报时去重，仅保留一份。"""
    execution = await _create_assigned_execution(db_session, test_user, online_node)
    await client.post(
        f"/api/v1/supplier/executions/{execution.id}/start",
        headers=supplier_headers,
    )

    file_entry = {"key": "results/r1.bin", "name": "r1.bin", "size": 128}
    resp = await client.post(
        f"/api/v1/supplier/executions/{execution.id}/complete",
        headers=supplier_headers,
        json={
            "compute_duration_seconds": 100,
            "proof_hash": "b" * 64,
            "result_files": [file_entry, file_entry],
        },
    )

    assert resp.status_code == 200, resp.text

    task = await db_session.get(Task, execution.task_id)
    await db_session.refresh(task)
    result_files = json.loads(task.result_files_json)
    assert result_files == [file_entry]


@pytest.mark.asyncio
async def test_pending_execution_includes_command_and_env_vars(
    db_session, test_user, online_node, client, supplier_headers
):
    """A1：待执行分片应透传执行命令与环境变量，供 Agent 沙箱执行。"""
    execution = await _create_assigned_execution(
        db_session,
        test_user,
        online_node,
        task_no="T202602020003",
        command="python run.py",
        env_vars_json=json.dumps({"CUDA_VISIBLE_DEVICES": "0"}),
    )

    resp = await client.get(
        f"/api/v1/supplier/nodes/{online_node.id}/pending-executions",
        headers=supplier_headers,
    )

    assert resp.status_code == 200, resp.text
    item = resp.json()["data"][0]
    assert item["execution_id"] == str(execution.id)
    assert item["command"] == "python run.py"
    assert item["env_vars"] == {"CUDA_VISIBLE_DEVICES": "0", "PROOF_NONCE": "testnonce"}
    assert item["challenge_nonce"] == "testnonce"


@pytest.mark.asyncio
async def test_complete_execution_clamps_duration(
    db_session, test_user, online_node, client, supplier_headers
):
    """P0 反作弊：上报算力时长不得超过墙钟时间，超出部分被截断，防止虚报时长多结算。"""
    execution = await _create_assigned_execution(db_session, test_user, online_node)
    await client.post(
        f"/api/v1/supplier/executions/{execution.id}/start",
        headers=supplier_headers,
    )

    # 将开始时间回溯到 10 分钟前，模拟真实执行了约 10 分钟
    await db_session.refresh(execution)
    execution.started_at = datetime.now(UTC) - timedelta(seconds=600)
    await db_session.commit()

    # 上报 3600 秒（1 小时），远超墙钟时间，应被截断到约 600 秒以内
    resp = await client.post(
        f"/api/v1/supplier/executions/{execution.id}/complete",
        headers=supplier_headers,
        json={
            "compute_duration_seconds": 3600,
            "proof_hash": "b" * 64,
            "result_files": [{"key": "results/r2.bin", "name": "r2.bin", "size": 128}],
        },
    )

    assert resp.status_code == 200, resp.text
    await db_session.refresh(execution)
    assert 0 < execution.compute_duration_seconds <= 610


@pytest.mark.asyncio
async def test_download_execution_model_presign(
    db_session, test_user, online_node, client, supplier_headers, monkeypatch
):
    """A1：供给方节点可获取分配给自己的任务模型的预签名下载地址。"""
    from unittest.mock import AsyncMock

    execution = await _create_assigned_execution(db_session, test_user, online_node)
    monkeypatch.setattr(
        "app.services.upload.get_presigned_url",
        AsyncMock(return_value="https://minio/bucket/models/test-model.bin"),
    )

    resp = await client.get(
        f"/api/v1/supplier/executions/{execution.id}/model/download",
        headers=supplier_headers,
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()["data"]
    assert body["object_key"] == "models/test-model.bin"
    assert body["download_url"] == "https://minio/bucket/models/test-model.bin"
    assert body["expires_in"] == 3600


@pytest.mark.asyncio
async def test_download_execution_model_ownership_guard(
    db_session, test_user, online_node, client, auth_headers
):
    """A1：非节点所有者无法下载任务模型。"""
    execution = await _create_assigned_execution(db_session, test_user, online_node)

    resp = await client.get(
        f"/api/v1/supplier/executions/{execution.id}/model/download",
        headers=auth_headers,
    )

    assert resp.status_code == 404
