"""算力时间银行：借用/取用、利息明细、公共池可视化、储备贡献率可见 测试。"""
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.core.exceptions import BusinessError
from app.core.security import get_password_hash
from app.models import (
    Account,
    AuditLog,
    ReserveBorrowRecord,
    ReserveInterestAllocation,
    ReserveInterestRecord,
    Task,
    TaskExecution,
    TaskStatus,
    TaskType,
    User,
    UserRole,
)
from app.services.account import AccountService
from app.services.reserve import ReserveInterestService, ReserveService


async def _set_reserve(db_session, user: User, points: int) -> Account:
    account = (
        await db_session.execute(
            select(Account).where(Account.user_id == user.id)
        )
    ).scalar_one()
    account.reserve_points = points
    await db_session.commit()
    return account


def _task(user: User) -> Task:
    return Task(
        task_no="T202601010099",
        demander_id=user.id,
        type=TaskType.INFERENCE,
        title="时间银行测试任务",
        model_source="platform",
        params_json="{}",
        required_vram_gb=8,
        budget_points=5000,
        min_settlement_unit=1000,
        status=TaskStatus.COMPLETED,
    )


@pytest.mark.asyncio
async def test_borrow_moves_reserve_to_balance(db_session, test_user):
    """借用把储备分转为自由分，并写入流水与审计链。"""
    account = await _set_reserve(db_session, test_user, 500)
    balance_before = account.balance_points

    service = ReserveService(db_session)
    result = await service.borrow(test_user.id, 100)

    assert result["amount_points"] == 100
    assert result["balance_points"] == balance_before + 100
    assert result["reserve_points"] == 400

    records = (await db_session.execute(select(ReserveBorrowRecord))).scalars().all()
    assert len(records) == 1
    assert records[0].amount_points == 100
    assert records[0].reserve_before == 500
    assert records[0].balance_before == balance_before

    audit = (
        await db_session.execute(
            select(AuditLog).where(AuditLog.event_type == "reserve.borrowed")
        )
    ).scalars().all()
    assert len(audit) == 1
    assert audit[0].user_id == test_user.id


@pytest.mark.asyncio
async def test_borrow_exceeds_own_reserve(db_session, test_user):
    """借用金额超过自身储备时报错。"""
    await _set_reserve(db_session, test_user, 100)
    service = ReserveService(db_session)
    with pytest.raises(BusinessError):
        await service.borrow(test_user.id, 200)


@pytest.mark.asyncio
async def test_borrow_exceeds_pool_cap(db_session, test_user):
    """借用金额超过公共池单人上限（max_borrow_ratio）时报错。"""
    # 公共池 1000 分，max_borrow_ratio=20% → 单次上限 200 分
    await _set_reserve(db_session, test_user, 1000)
    service = ReserveService(db_session)
    with pytest.raises(BusinessError):
        await service.borrow(test_user.id, 300)


@pytest.mark.asyncio
async def test_interest_allocation_writes_per_account_detail(
    db_session, test_user, test_supplier, online_node
):
    """利息分配同时写入单账户明细，支撑利息明细查询。"""
    supplier_acct = (
        await db_session.execute(
            select(Account).where(Account.user_id == test_supplier.id)
        )
    ).scalar_one()
    supplier_acct.reserve_points = 300

    other = User(
        phone="13500135000",
        password_hash=get_password_hash("password123"),
        nickname="other-supplier",
        roles=[UserRole.USER.value],
        is_active=True,
    )
    db_session.add(other)
    await db_session.flush()
    db_session.add(Account(user_id=other.id, reserve_points=100))

    task = _task(test_user)
    db_session.add(task)
    await db_session.flush()

    db_session.add(
        TaskExecution(
            task_id=task.id,
            node_id=online_node.id,
            attempt_no=1,
            status=TaskStatus.COMPLETED,
            platform_fee_rate=0,
            reserve_points=400,
            completed_at=datetime.now(UTC) - timedelta(hours=1),
        )
    )
    await db_session.commit()

    service = ReserveInterestService(db_session)
    count = await service.distribute()
    assert count == 2

    allocs = (
        await db_session.execute(select(ReserveInterestAllocation))
    ).scalars().all()
    assert len(allocs) == 2
    by_user = {a.user_id: a for a in allocs}
    assert by_user[test_supplier.id].interest_points == 150
    assert by_user[other.id].interest_points == 50
    assert by_user[test_supplier.id].reserve_points_before == 300

    records = (await db_session.execute(select(ReserveInterestRecord))).scalars().all()
    assert by_user[test_supplier.id].record_id == records[0].id

    audit = (
        await db_session.execute(
            select(AuditLog).where(AuditLog.event_type == "reserve.interest_distributed")
        )
    ).scalars().all()
    assert len(audit) == 1
    assert audit[0].entity_id == records[0].id


@pytest.mark.asyncio
async def test_account_overview_exposes_contribution(db_session, test_user, test_supplier):
    """账户概览返回储备贡献率与公共池信息。"""
    await _set_reserve(db_session, test_user, 300)
    await _set_reserve(db_session, test_supplier, 100)

    service = AccountService(db_session)
    overview = await service.get_account_overview(test_user.id)

    assert overview["reserve_contribution"] == 7500
    assert overview["pool_total_points"] == 400
    assert overview["pool_contributors"] == 2


@pytest.mark.asyncio
async def test_pool_overview_stats(db_session, test_user, test_supplier):
    """公共池可视化返回池总量、贡献人数、累计产出与利息。"""
    await _set_reserve(db_session, test_user, 300)
    await _set_reserve(db_session, test_supplier, 100)

    service = ReserveService(db_session)
    overview = await service.get_pool_overview()

    assert overview["pool_total_points"] == 400
    assert overview["pool_contributors"] == 2
    assert overview["total_output_points"] == 0
    assert overview["total_interest_points"] == 0
    assert overview["last_distributed_at"] is None


@pytest.mark.asyncio
async def test_reserve_api_borrow_and_lists(client, auth_headers, db_session, test_user):
    """时间银行接口：借用、公共池概览、借用流水。"""
    await _set_reserve(db_session, test_user, 500)

    resp = await client.post(
        "/api/v1/reserve/borrow",
        json={"amount_points": 100},
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["amount_points"] == 100
    assert data["reserve_points"] == 400

    resp = await client.get("/api/v1/reserve/pool", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["pool_total_points"] == 400
    assert resp.json()["data"]["pool_contributors"] == 1

    resp = await client.get("/api/v1/reserve/borrows", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["total"] == 1

    resp = await client.get("/api/v1/reserve/interest", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["total"] == 0
