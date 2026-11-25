"""储备利息分配测试。"""
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.core.security import get_password_hash
from app.models import (
    Account,
    ReserveInterestRecord,
    Task,
    TaskExecution,
    TaskStatus,
    TaskType,
    User,
    UserRole,
)
from app.services.reserve import ReserveInterestService


def _task(user: User) -> Task:
    return Task(
        task_no="T202601010099",
        demander_id=user.id,
        type=TaskType.INFERENCE,
        title="储备利息测试任务",
        model_source="platform",
        params_json="{}",
        required_vram_gb=8,
        budget_points=5000,
        min_settlement_unit=1000,
        status=TaskStatus.COMPLETED,
    )


@pytest.mark.asyncio
async def test_reserve_interest_distributes_by_share(
    db_session, test_user, test_supplier, online_node
):
    """公共池本周期产出按储备占比返还，利息计入储备形成复利。"""
    supplier_acct = (
        await db_session.execute(
            select(Account).where(Account.user_id == test_supplier.id)
        )
    ).scalar_one()
    supplier_acct.reserve_points = 300
    supplier_acct.total_earned = 1000

    other = User(
        phone="13500135000",
        password_hash=get_password_hash("password123"),
        nickname="other-supplier",
        roles=[UserRole.USER.value],
        is_active=True,
    )
    db_session.add(other)
    await db_session.flush()
    other_acct = Account(user_id=other.id, reserve_points=100, total_earned=400)
    db_session.add(other_acct)

    task = _task(test_user)
    db_session.add(task)
    await db_session.flush()

    execution = TaskExecution(
        task_id=task.id,
        node_id=online_node.id,
        attempt_no=1,
        status=TaskStatus.COMPLETED,
        platform_fee_rate=0,
        reserve_points=400,  # 本周期公共池新产出
        completed_at=datetime.now(UTC) - timedelta(hours=1),
    )
    db_session.add(execution)
    await db_session.commit()

    service = ReserveInterestService(db_session)
    count = await service.distribute()

    assert count == 2

    await db_session.refresh(supplier_acct)
    await db_session.refresh(other_acct)
    # interest = 400 * 50% = 200；supplier 占比 3/4 → +150，other 占比 1/4 → +50
    assert supplier_acct.reserve_points == 450
    assert other_acct.reserve_points == 150

    records = (await db_session.execute(select(ReserveInterestRecord))).scalars().all()
    assert len(records) == 1
    assert records[0].cycle_output_points == 400
    assert records[0].interest_points == 200

    # 幂等：再次分配无新产出
    assert await service.distribute() == 0


@pytest.mark.asyncio
async def test_reserve_interest_skips_without_output(db_session):
    """无新储备产出时不产生分配记录。"""
    service = ReserveInterestService(db_session)
    assert await service.distribute() == 0
