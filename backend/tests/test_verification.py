"""采样复核验证测试（D1 第二阶段）。"""
import hashlib
import json

import pytest
from sqlalchemy import select

from app.models import (
    Account,
    Node,
    PlatformConfig,
    Settlement,
    SettlementRole,
    SettlementStatus,
    Task,
    TaskExecution,
    TaskStatus,
    TaskType,
    VerificationRecord,
    VerificationStatus,
)

NAME = "result.bin"
CONTENT = b"hello world"
NONCE = "testnonce"


def _content_hash(name: str, content: bytes) -> str:
    digest = hashlib.sha256()
    digest.update(name.encode("utf-8"))
    digest.update(content)
    return digest.hexdigest()


def _proof_hash(nonce: str, name: str, content: bytes) -> str:
    """与后端防重放协议一致：proof_hash = sha256(nonce + ':' + content_hash)。"""
    digest = hashlib.sha256()
    digest.update(nonce.encode("utf-8"))
    digest.update(b":")
    digest.update(_content_hash(name, content).encode("utf-8"))
    return digest.hexdigest()


EXPECTED_HASH = _proof_hash(NONCE, NAME, CONTENT)


async def _enable_sampling(db_session, rate: int = 10000) -> PlatformConfig:
    config = await db_session.get(PlatformConfig, 1)
    if not config:
        config = PlatformConfig()
        db_session.add(config)
        await db_session.flush()
    config.verification_sample_rate = rate
    await db_session.commit()
    return config


async def _create_running_execution(
    db_session, test_user, online_node, task_no: str = "T202603010001"
) -> TaskExecution:
    task = Task(
        task_no=task_no,
        demander_id=test_user.id,
        type=TaskType.INFERENCE,
        title="复核测试任务",
        model_source="upload",
        model_file_key="models/m.bin",
        params_json=json.dumps({"x": 1}),
        required_vram_gb=8,
        budget_points=5000,
        preauthorized_points=5000,
        min_settlement_unit=1000,
        status=TaskStatus.ASSIGNED,
    )
    db_session.add(task)
    await db_session.flush()

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
        status=TaskStatus.RUNNING,
        platform_fee_rate=1000,
        challenge_nonce=NONCE,
    )
    db_session.add(execution)
    await db_session.commit()
    await db_session.refresh(execution)
    return execution


async def _complete(
    client, supplier_headers, execution, proof_hash: str, content: bytes = CONTENT
):
    return await client.post(
        f"/api/v1/supplier/executions/{execution.id}/complete",
        headers=supplier_headers,
        json={
            "compute_duration_seconds": 3600,
            "proof_hash": proof_hash,
            "result_files": [{"key": "results/result.bin", "name": NAME, "size": len(content)}],
        },
    )


@pytest.mark.asyncio
async def test_sample_disabled_by_default(
    db_session, test_user, online_node, client, supplier_headers
):
    execution = await _create_running_execution(db_session, test_user, online_node)

    resp = await _complete(client, supplier_headers, execution, EXPECTED_HASH)
    assert resp.status_code == 200, resp.text

    records = (await db_session.execute(select(VerificationRecord))).scalars().all()
    assert records == []


@pytest.mark.asyncio
async def test_sample_creates_pending_record(
    db_session, test_user, online_node, client, supplier_headers
):
    await _enable_sampling(db_session, 10000)
    execution = await _create_running_execution(db_session, test_user, online_node)

    resp = await _complete(client, supplier_headers, execution, EXPECTED_HASH)
    assert resp.status_code == 200, resp.text

    records = (await db_session.execute(select(VerificationRecord))).scalars().all()
    assert len(records) == 1
    record = records[0]
    assert record.status == VerificationStatus.PENDING
    assert record.expected_hash == EXPECTED_HASH
    files = json.loads(record.result_files_json)
    assert files[0]["name"] == NAME


@pytest.mark.asyncio
async def test_run_verification_passes(
    db_session, test_user, online_node, client, supplier_headers, admin_headers, monkeypatch
):
    await _enable_sampling(db_session, 10000)
    execution = await _create_running_execution(db_session, test_user, online_node)
    await _complete(client, supplier_headers, execution, EXPECTED_HASH)

    async def fake_get_object_bytes(key: str) -> bytes:
        return CONTENT

    monkeypatch.setattr("app.services.verification.get_object_bytes", fake_get_object_bytes)

    record = (await db_session.execute(select(VerificationRecord))).scalar_one()
    resp = await client.post(
        f"/api/v1/admin/verification-records/{record.id}/run",
        headers=admin_headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()["data"]
    assert body["status"] == "verified"
    assert body["actual_hash"] == EXPECTED_HASH

    await db_session.refresh(record)
    assert record.status == VerificationStatus.VERIFIED


@pytest.mark.asyncio
async def test_run_verification_fails_and_reverses(
    db_session, test_user, test_supplier, online_node,
    client, supplier_headers, admin_headers, monkeypatch
):
    await _enable_sampling(db_session, 10000)
    execution = await _create_running_execution(db_session, test_user, online_node)
    await _complete(client, supplier_headers, execution, EXPECTED_HASH)

    async def fake_get_object_bytes(key: str) -> bytes:
        return b"tampered content"

    monkeypatch.setattr("app.services.verification.get_object_bytes", fake_get_object_bytes)

    record = (await db_session.execute(select(VerificationRecord))).scalar_one()

    supplier_account = (
        await db_session.execute(
            select(Account).where(Account.user_id == test_supplier.id)
        )
    ).scalar_one()
    earned = supplier_account.balance_points + supplier_account.reserve_points
    assert earned > 0

    resp = await client.post(
        f"/api/v1/admin/verification-records/{record.id}/run",
        headers=admin_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["status"] == "failed"

    # 供给方收益被追回
    await db_session.refresh(supplier_account)
    assert supplier_account.balance_points == 0
    assert supplier_account.reserve_points == 0
    assert supplier_account.total_earned == 0

    # 节点统计与信誉回退
    node = await db_session.get(Node, online_node.id)
    await db_session.refresh(node)
    assert node.total_tasks_completed == 0
    assert node.total_points_earned == 0
    assert node.reputation_score == 80

    # 结算单被回滚，并生成回滚单
    settlements = (
        await db_session.execute(
            select(Settlement).where(
                Settlement.execution_id == execution.id,
                Settlement.role == SettlementRole.SUPPLIER,
            )
        )
    ).scalars().all()
    assert any(s.status == SettlementStatus.REVERSED for s in settlements)
    assert any(s.net_points == -earned for s in settlements)


@pytest.mark.asyncio
async def test_admin_list_verification_records(
    db_session, test_user, online_node, client, supplier_headers, admin_headers
):
    await _enable_sampling(db_session, 10000)
    execution = await _create_running_execution(db_session, test_user, online_node)
    await _complete(client, supplier_headers, execution, EXPECTED_HASH)

    resp = await client.get(
        "/api/v1/admin/verification-records",
        headers=admin_headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["total"] == 1
    item = data["items"][0]
    assert item["status"] == "pending"
    assert item["expected_hash"] == EXPECTED_HASH


@pytest.mark.asyncio
async def test_run_verification_rejects_unbound_proof_hash(
    db_session, test_user, online_node,
    client, supplier_headers, admin_headers, monkeypatch
):
    """P0 反作弊：proof_hash 未绑定 challenge_nonce 时复核失败，拦截结果缓存重放。"""
    await _enable_sampling(db_session, 10000)
    execution = await _create_running_execution(db_session, test_user, online_node)

    # 上报纯内容哈希（未绑定 nonce），模拟复用历史执行结果
    unbound = _content_hash(NAME, CONTENT)
    await _complete(client, supplier_headers, execution, unbound)

    async def fake_get_object_bytes(key: str) -> bytes:
        return CONTENT

    monkeypatch.setattr("app.services.verification.get_object_bytes", fake_get_object_bytes)

    record = (await db_session.execute(select(VerificationRecord))).scalar_one()
    resp = await client.post(
        f"/api/v1/admin/verification-records/{record.id}/run",
        headers=admin_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["status"] == "failed"
