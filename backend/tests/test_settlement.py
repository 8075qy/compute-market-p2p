from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from app.models import (
    Account,
    PlatformConfig,
    Settlement,
    SettlementRole,
    SettlementStatus,
    Task,
    TaskStatus,
)
from app.services.settlement import SettlementEngine


async def _account(db_session, user_id):
    return (
        await db_session.execute(select(Account).where(Account.user_id == user_id))
    ).scalar_one()


@pytest.mark.asyncio
async def test_settlement_zero_fee_full_points_to_supplier(
    db_session, test_user, test_supplier, completed_execution
):
    engine = SettlementEngine(db_session)
    settlement = await engine.settle_execution(completed_execution)

    assert settlement.role == SettlementRole.SUPPLIER
    assert settlement.compute_points == 83  # noqa: PLR2004  82.6 TFLOPS × 1 小时 → 向上取整
    assert settlement.platform_fee_rate == 0
    assert settlement.platform_fee_points == 0
    assert settlement.net_points == 83  # noqa: PLR2004
    assert settlement.status == SettlementStatus.SETTLED

    supplier_account = await _account(db_session, test_supplier.id)
    demander_account = await _account(db_session, test_user.id)
    await db_session.refresh(supplier_account)
    await db_session.refresh(demander_account)

    assert supplier_account.balance_points == 59  # 83 - 24 储备沉淀
    assert supplier_account.reserve_points == 24
    assert supplier_account.total_earned == 83  # noqa: PLR2004
    assert demander_account.balance_points == 19917  # 15000 + (5000 - 83) 退款
    assert demander_account.frozen_points == 0
    assert demander_account.total_spent == 83  # noqa: PLR2004

    await db_session.refresh(completed_execution)
    assert completed_execution.status == TaskStatus.COMPLETED
    task = (
        await db_session.execute(
            select(Task).where(Task.id == completed_execution.task_id)
        )
    ).scalar_one()
    assert task.status == TaskStatus.COMPLETED


@pytest.mark.asyncio
async def test_settlement_is_idempotent(db_session, completed_execution):
    engine = SettlementEngine(db_session)
    first = await engine.settle_execution(completed_execution)
    second = await engine.settle_execution(completed_execution)

    assert first.id == second.id

    settlements = (await db_session.execute(select(Settlement))).scalars().all()
    supplier_rows = [s for s in settlements if s.role == SettlementRole.SUPPLIER]
    # 供给方结算单只有一条；重复调用不会重复入账
    assert len(supplier_rows) == 1


@pytest.mark.asyncio
async def test_settlement_refunds_unused_budget(
    db_session, test_user, test_supplier, completed_execution
):
    completed_execution.compute_points = 2000
    await db_session.commit()

    engine = SettlementEngine(db_session)
    settlement = await engine.settle_execution(completed_execution)

    assert settlement.compute_points == 2000
    assert settlement.platform_fee_points == 0
    assert settlement.net_points == 2000

    demander_account = await _account(db_session, test_user.id)
    await db_session.refresh(demander_account)
    assert demander_account.balance_points == 18000  # 15000 + 3000 退款
    assert demander_account.frozen_points == 0

    settlements = (await db_session.execute(select(Settlement))).scalars().all()
    refunds = [s for s in settlements if s.status == SettlementStatus.REFUNDED]
    assert len(refunds) == 1
    assert refunds[0].net_points == 3000


@pytest.mark.asyncio
async def test_settlement_ignores_platform_fee_rate(
    db_session, completed_execution
):
    completed_execution.platform_fee_rate = 500
    db_session.add(
        PlatformConfig(
            id=1,
            platform_fee_rate=2000,
            min_settlement_unit=1000,
        )
    )
    await db_session.commit()

    engine = SettlementEngine(db_session)
    settlement = await engine.settle_execution(completed_execution)

    assert settlement.platform_fee_rate == 0
    assert settlement.platform_fee_points == 0
    assert settlement.net_points == settlement.compute_points


@pytest.mark.asyncio
async def test_usage_never_exceeds_frozen_budget(
    db_session, test_user, completed_execution
):
    completed_execution.compute_points = 999999
    await db_session.commit()

    engine = SettlementEngine(db_session)
    settlement = await engine.settle_execution(completed_execution)

    assert settlement.compute_points == 5000

    demander_account = await _account(db_session, test_user.id)
    await db_session.refresh(demander_account)
    assert demander_account.balance_points == 15000
    assert demander_account.frozen_points == 0


@pytest.mark.asyncio
async def test_multiple_settlements_accumulate(
    db_session, test_user, test_supplier, online_node
):
    from datetime import datetime

    from app.models import Task, TaskExecution, TaskType

    account = await _account(db_session, test_user.id)
    account.balance_points = 20000
    account.frozen_points = 0
    await db_session.commit()

    engine = SettlementEngine(db_session)
    for index in range(3):
        account.balance_points -= 5000
        account.frozen_points += 5000
        task = Task(
            task_no=f"T20260102{index:04d}",
            demander_id=test_user.id,
            type=TaskType.INFERENCE,
            title="结算测试任务",
            model_source="platform",
            params_json="{}",
            required_vram_gb=4,
            budget_points=5000,
            preauthorized_points=5000,
            min_settlement_unit=1000,
            status=TaskStatus.RUNNING,
        )
        db_session.add(task)
        await db_session.flush()
        execution = TaskExecution(
            task_id=task.id,
            node_id=online_node.id,
            attempt_no=1,
            status=TaskStatus.RUNNING,
            started_at=datetime.now(UTC),
            compute_duration_seconds=3600,
            platform_fee_rate=0,
        )
        db_session.add(execution)
        await db_session.commit()
        await engine.settle_execution(execution)

    supplier_account = await _account(db_session, test_supplier.id)
    await db_session.refresh(supplier_account)
    # 单卡 82.6 TFLOPS，1 小时 = 82.6 分 → 向上取整 83 分；30% 储备沉淀
    assert supplier_account.balance_points == 177  # (83 - 24) × 3
    assert supplier_account.reserve_points == 72  # 24 × 3


@pytest.mark.asyncio
async def test_points_are_rounded_up_by_minute(
    db_session, completed_execution
):
    """计费粒度到分钟且向上取整：61 秒按 2 分钟计，2 × 82.6/60 = 2.75 → 3 分。"""
    completed_execution.compute_points = None
    completed_execution.compute_duration_seconds = 61
    await db_session.commit()

    engine = SettlementEngine(db_session)
    settlement = await engine.settle_execution(completed_execution)

    assert settlement.compute_points == 3  # noqa: PLR2004


@pytest.mark.asyncio
async def test_sub_second_execution_falls_back_to_wall_clock(
    db_session, completed_execution
):
    """上报时长被截断为 0 秒时，回退起止时间差，仍按 1 分钟起计，不再兜底到最小结算单位。"""
    completed_execution.compute_points = None
    completed_execution.compute_duration_seconds = 0
    completed_execution.started_at = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)
    completed_execution.completed_at = datetime(2026, 1, 1, 0, 0, 0, 58000, tzinfo=UTC)
    await db_session.commit()

    engine = SettlementEngine(db_session)
    settlement = await engine.settle_execution(completed_execution)

    assert settlement.compute_points == 2  # noqa: PLR2004  1 分钟 × 82.6/60 = 1.377 → 2
    assert settlement.compute_points < 1000  # 不再套用最小结算单位兜底


@pytest.mark.asyncio
async def test_points_scale_with_gpu_count(
    db_session, completed_execution, online_node
):
    """实际算力按整机累计：4 卡节点 1 小时 = 82.6 × 4 = 330.4 → 331 分。"""
    online_node.gpu_count = 4
    completed_execution.compute_points = None
    await db_session.commit()

    engine = SettlementEngine(db_session)
    settlement = await engine.settle_execution(completed_execution)

    assert settlement.compute_points == 331  # noqa: PLR2004


@pytest.mark.asyncio
async def test_points_scale_with_gpu_utilization(
    db_session, completed_execution, online_node
):
    """实际算力按实测利用率折算：50% 负载 1 小时 = 82.6 × 0.5 = 41.3 → 42 分。"""
    online_node.gpu_utilization = 50
    completed_execution.compute_points = None
    await db_session.commit()

    engine = SettlementEngine(db_session)
    settlement = await engine.settle_execution(completed_execution)

    assert settlement.compute_points == 42  # noqa: PLR2004


@pytest.mark.asyncio
async def test_points_use_full_capacity_without_utilization_sample(
    db_session, completed_execution, online_node
):
    """无利用率样本（心跳未上报）时按满载计费，不因缺样本而少算。"""
    online_node.gpu_utilization = None
    completed_execution.compute_points = None
    await db_session.commit()

    engine = SettlementEngine(db_session)
    settlement = await engine.settle_execution(completed_execution)

    assert settlement.compute_points == 83  # noqa: PLR2004
