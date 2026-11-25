"""4.4 Agent 按区间执行 + 进度上报测试：完成累计工作项、失败批次回池重试。"""
import math
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select

from app.models import (
    Settlement,
    Task,
    TaskExecution,
    TaskStatus,
    TaskType,
)
from app.schemas.node import ExecutionCompleteRequest
from app.services.execution import ExecutionService
from app.services.settlement import SettlementEngine


async def _create_batch_task(db_session, demander, total=100, batch_size=8, max_retries=None):
    task = Task(
        task_no=f"TP-{demander.id.hex[:8]}-{total}-{batch_size}",
        demander_id=demander.id,
        type=TaskType.BATCH,
        title="批量推理任务",
        model_source="platform",
        params_json="{}",
        required_vram_gb=8,
        budget_points=50000,
        min_settlement_unit=1000,
        status=TaskStatus.ASSIGNED,
        total_work_units=total,
        batch_size=batch_size,
        input_file_key=f"inputs/{demander.id.hex}/abc/data.zip",
        max_retries=max_retries,
    )
    db_session.add(task)
    await db_session.commit()
    await db_session.refresh(task)
    return task


async def _claim_one(service: ExecutionService, node) -> TaskExecution:
    execution = await service._claim_batch_work(node)
    assert execution is not None
    return execution


async def _start(service: ExecutionService, execution, user_id) -> None:
    await service.start_execution(execution.id, user_id)


@pytest.mark.asyncio
async def test_complete_batch_accumulates_work_units(
    db_session, test_user, test_supplier, online_node
):
    """批次完成后按上报值累计到任务进度，execution 记录本批完成数。"""
    task = await _create_batch_task(db_session, test_user, total=100, batch_size=8)
    service = ExecutionService(db_session)
    execution = await _claim_one(service, online_node)
    await _start(service, execution, test_supplier.id)

    data = ExecutionCompleteRequest(
        proof_hash="b" * 64,
        compute_duration_seconds=60,
        completed_work_units=8,
    )
    await service.complete_execution(execution.id, test_supplier.id, data)

    await db_session.refresh(execution)
    assert execution.status == TaskStatus.COMPLETED
    assert execution.completed_work_units == 8  # noqa: PLR2004

    task = await db_session.get(Task, execution.task_id)
    assert task.completed_work_units == 8  # noqa: PLR2004


@pytest.mark.asyncio
async def test_complete_batch_defaults_to_interval_length(
    db_session, test_user, test_supplier, online_node
):
    """未上报 completed_work_units 时默认按区间长度 (end - start) 累计。"""
    await _create_batch_task(db_session, test_user, total=100, batch_size=8)
    service = ExecutionService(db_session)
    execution = await _claim_one(service, online_node)
    await _start(service, execution, test_supplier.id)

    data = ExecutionCompleteRequest(proof_hash="c" * 64, compute_duration_seconds=60)
    await service.complete_execution(execution.id, test_supplier.id, data)

    await db_session.refresh(execution)
    assert execution.completed_work_units == 8  # noqa: PLR2004
    task = await db_session.get(Task, execution.task_id)
    assert task.completed_work_units == 8  # noqa: PLR2004


@pytest.mark.asyncio
async def test_fail_batch_requeues_same_interval(
    db_session, test_user, test_supplier, online_node
):
    """批次失败后按原区间重新入队（attempt_no+1），原执行保持 FAILED。"""
    task = await _create_batch_task(db_session, test_user, total=100, batch_size=8)
    service = ExecutionService(db_session)
    execution = await _claim_one(service, online_node)
    await _start(service, execution, test_supplier.id)

    await service.fail_execution(execution.id, test_supplier.id, "OOM")

    await db_session.refresh(execution)
    assert execution.status == TaskStatus.FAILED

    requeued = (
        await db_session.execute(
            select(TaskExecution).where(
                TaskExecution.task_id == task.id,
                TaskExecution.status == TaskStatus.ASSIGNED,
            )
        )
    ).scalar_one()
    assert requeued.id != execution.id
    assert requeued.attempt_no == execution.attempt_no + 1
    assert requeued.work_unit_start == execution.work_unit_start
    assert requeued.work_unit_end == execution.work_unit_end


@pytest.mark.asyncio
async def test_fail_batch_retry_then_complete_settles_once(
    db_session, test_user, test_supplier, online_node
):
    """失败 → 重新领取 → 完成：工作项不丢失，该区间仅结算一次。"""
    await _create_batch_task(db_session, test_user, total=100, batch_size=8)
    service = ExecutionService(db_session)
    first = await _claim_one(service, online_node)
    await _start(service, first, test_supplier.id)
    await service.fail_execution(first.id, test_supplier.id, "OOM")

    # 失败区间作为 ASSIGNED 执行记录重新入队，可被再次领取
    items = await service.get_pending_executions(online_node.id, test_supplier.id)
    retry_items = [
        it
        for it in items
        if it["work_unit_start"] == first.work_unit_start
        and it["attempt_no"] == first.attempt_no + 1
    ]
    assert len(retry_items) == 1

    retry = await db_session.get(TaskExecution, retry_items[0]["execution_id"])
    assert (retry.work_unit_start, retry.work_unit_end) == (
        first.work_unit_start,
        first.work_unit_end,
    )

    await _start(service, retry, test_supplier.id)
    data = ExecutionCompleteRequest(proof_hash="d" * 64, compute_duration_seconds=60)
    await service.complete_execution(retry.id, test_supplier.id, data)

    await db_session.refresh(retry)
    assert retry.status == TaskStatus.COMPLETED

    # 失败批次无结算，重试批次仅一条结算，工作项被计入
    first_settlement = (
        await db_session.execute(
            select(Settlement).where(Settlement.execution_id == first.id)
        )
    ).scalars().all()
    assert first_settlement == []

    retry_settlement = (
        await db_session.execute(
            select(Settlement).where(Settlement.execution_id == retry.id)
        )
    ).scalars().all()
    assert len(retry_settlement) == 1

    task = await db_session.get(Task, retry.task_id)
    assert task.completed_work_units == retry.work_unit_end - retry.work_unit_start


@pytest.mark.asyncio
async def test_fail_batch_exhausts_retries_stays_failed(
    db_session, test_user, test_supplier, online_node
):
    """超过任务最大重试次数后批次不再回池，保持 FAILED。"""
    await _create_batch_task(
        db_session, test_user, total=100, batch_size=8, max_retries=1
    )
    service = ExecutionService(db_session)
    execution = await _claim_one(service, online_node)
    await _start(service, execution, test_supplier.id)
    await service.fail_execution(execution.id, test_supplier.id, "OOM")

    assigned = (
        await db_session.execute(
            select(TaskExecution).where(
                TaskExecution.task_id == execution.task_id,
                TaskExecution.status == TaskStatus.ASSIGNED,
            )
        )
    ).scalars().all()
    assert assigned == []


@pytest.mark.asyncio
async def test_pending_executions_returns_input_and_manifest_keys(
    db_session, test_user, test_supplier, online_node
):
    """Agent 轮询接口返回数据包与清单对象键，供按区间取文件。"""
    task = await _create_batch_task(db_session, test_user, total=100, batch_size=8)
    service = ExecutionService(db_session)
    items = await service.get_pending_executions(online_node.id, test_supplier.id)

    assert len(items) == 1
    assert items[0]["input_file_key"] == task.input_file_key
    assert items[0]["manifest_key"] == f"{task.input_file_key.rsplit('/', 1)[0]}/manifest.json"


@pytest.mark.asyncio
async def test_input_download_returns_presigned_urls(  # noqa: PLR0913, PLR0917
    db_session,
    test_user,
    online_node,
    client,
    supplier_headers,
    monkeypatch,
):
    """Agent 可按 execution 下载批处理数据包与 manifest 的预签名地址。"""
    task = await _create_batch_task(db_session, test_user, total=100, batch_size=8)
    service = ExecutionService(db_session)
    execution = await _claim_one(service, online_node)

    monkeypatch.setattr(
        "app.services.upload.get_presigned_url",
        AsyncMock(side_effect=lambda key, _: f"https://minio/dl/{key}"),
    )

    resp = await client.get(
        f"/api/v1/supplier/executions/{execution.id}/input/download",
        headers=supplier_headers,
    )
    assert resp.status_code == 200, resp.text  # noqa: PLR2004
    body = resp.json()["data"]
    assert body["input_object_key"] == task.input_file_key
    assert body["manifest_object_key"] == (
        f"{task.input_file_key.rsplit('/', 1)[0]}/manifest.json"
    )
    assert body["input_download_url"] == f"https://minio/dl/{task.input_file_key}"
    assert body["manifest_download_url"] == f"https://minio/dl/{body['manifest_object_key']}"


@pytest.mark.asyncio
async def test_batch_settlement_uses_duration_formula(
    db_session, test_user, test_supplier, online_node
):
    """批处理批次结算额 = 计费分钟 × peak_tflops / 60（向上取整），纯对等交换不抽成。"""
    await _create_batch_task(db_session, test_user, total=100, batch_size=8)
    service = ExecutionService(db_session)
    execution = await _claim_one(service, online_node)
    await _start(service, execution, test_supplier.id)

    # 直接结算，绕过 complete_execution 的墙钟时间截断，验证计价公式本身
    execution.compute_duration_seconds = 3600
    execution.proof_hash = "e" * 64
    await db_session.flush()

    engine = SettlementEngine(db_session)
    settlement = await engine.settle_execution(execution)

    expected_points = math.ceil(60 * float(online_node.peak_tflops) / 60)
    assert settlement.compute_points == expected_points
    assert settlement.platform_fee_points == 0
    assert settlement.net_points == settlement.compute_points


@pytest.mark.asyncio
async def test_batch_task_finalizes_after_retry_completes(
    db_session, test_user, test_supplier, online_node
):
    """全部工作项完成（含失败回池留 FAILED 记录）后任务正确收尾。"""
    task = await _create_batch_task(db_session, test_user, total=8, batch_size=8)
    service = ExecutionService(db_session)

    first = await _claim_one(service, online_node)
    await _start(service, first, test_supplier.id)
    await service.fail_execution(first.id, test_supplier.id, "OOM")

    items = await service.get_pending_executions(online_node.id, test_supplier.id)
    retry_items = [it for it in items if it["attempt_no"] == first.attempt_no + 1]
    assert len(retry_items) == 1
    retry = await db_session.get(TaskExecution, retry_items[0]["execution_id"])
    await _start(service, retry, test_supplier.id)
    data = ExecutionCompleteRequest(proof_hash="f" * 64, compute_duration_seconds=60)
    await service.complete_execution(retry.id, test_supplier.id, data)

    await db_session.refresh(task)
    assert task.completed_work_units == 8  # noqa: PLR2004
    assert task.status == TaskStatus.COMPLETED
