import pytest
from sqlalchemy import select

from app.models import Account, Task, TaskStatus, User


async def _account(db_session, user_id):
    return (
        await db_session.execute(select(Account).where(Account.user_id == user_id))
    ).scalar_one()


@pytest.mark.asyncio
async def test_budget_below_min_unit_is_rejected_without_side_effects(
    client, db_session, auth_headers, test_user: User
):
    account = await _account(db_session, test_user.id)
    original_balance = account.balance_points
    original_frozen = account.frozen_points

    response = await client.post(
        "/api/v1/demand/tasks",
        headers=auth_headers,
        json={
            "type": "inference",
            "title": "预算不足任务",
            "model_source": "platform",
            "required_vram_gb": 8,
            "budget_points": 500,
        },
    )

    assert response.status_code == 400
    assert "最小结算单位" in response.json()["message"]

    await db_session.refresh(account)
    assert account.balance_points == original_balance
    assert account.frozen_points == original_frozen

    tasks = (await db_session.execute(select(Task))).scalars().all()
    assert tasks == []


@pytest.mark.asyncio
async def test_create_task_preauthorizes_first_segment_and_is_listed(
    client, db_session, auth_headers, test_user: User
):
    account = await _account(db_session, test_user.id)

    response = await client.post(
        "/api/v1/demand/tasks",
        headers=auth_headers,
        json={
            "type": "inference",
            "title": "推理测试任务",
            "model_source": "platform",
            "params": {"prompt": "hello"},
            "required_vram_gb": 8,
            "required_tflops": 13.5,
            "budget_points": 2000,
        },
    )
    assert response.status_code == 200, response.text
    task = response.json()["data"]
    assert task["status"] == "scheduling"
    assert task["params"] == {"prompt": "hello"}
    assert task["budget_points"] == 2000

    await db_session.refresh(account)
    # 预授权仅冻结首段预估费用 ⌈13.5⌉ = 14 分，不再全额冻结预算
    assert account.balance_points == 19986
    assert account.frozen_points == 14

    response = await client.get("/api/v1/demand/tasks", headers=auth_headers)
    assert response.status_code == 200
    page = response.json()["data"]
    assert page["total"] == 1
    assert page["total_pages"] == 1
    assert page["items"][0]["task_no"].startswith("T")

    response = await client.get(
        f"/api/v1/demand/tasks/{task['id']}", headers=auth_headers
    )
    assert response.status_code == 200
    assert response.json()["data"]["executions"] == []


@pytest.mark.asyncio
async def test_cancel_task_refunds_frozen_budget(
    client, db_session, auth_headers, test_user: User
):
    response = await client.post(
        "/api/v1/demand/tasks",
        headers=auth_headers,
        json={
            "type": "training",
            "title": "训练测试任务",
            "model_source": "platform",
            "required_vram_gb": 16,
            "required_tflops": 13.5,
            "budget_points": 3000,
        },
    )
    task = response.json()["data"]

    account = await _account(db_session, test_user.id)
    await db_session.refresh(account)
    # 预授权仅冻结首段预估费用 ⌈13.5⌉ = 14 分
    assert account.balance_points == 19986
    assert account.frozen_points == 14

    response = await client.post(
        f"/api/v1/demand/tasks/{task['id']}/cancel", headers=auth_headers
    )
    assert response.status_code == 200
    assert response.json()["data"]["status"] == TaskStatus.CANCELLED.value

    await db_session.refresh(account)
    assert account.balance_points == 20000
    assert account.frozen_points == 0


@pytest.mark.asyncio
async def test_task_list_is_scoped_to_current_user(
    client, auth_headers, supplier_headers
):
    response = await client.post(
        "/api/v1/demand/tasks",
        headers=auth_headers,
        json={
            "type": "inference",
            "title": "归属隔离任务",
            "model_source": "platform",
            "required_vram_gb": 4,
            "budget_points": 1000,
        },
    )
    assert response.status_code == 200

    response = await client.get("/api/v1/demand/tasks", headers=supplier_headers)
    assert response.status_code == 200
    assert response.json()["data"]["total"] == 0


@pytest.mark.asyncio
async def test_insufficient_balance_is_rejected(client, db_session, auth_headers, test_user: User):
    account = await _account(db_session, test_user.id)
    account.balance_points = 5
    await db_session.commit()

    response = await client.post(
        "/api/v1/demand/tasks",
        headers=auth_headers,
        json={
            "type": "inference",
            "title": "余额不足任务",
            "model_source": "platform",
            "required_vram_gb": 4,
            "required_tflops": 13.5,
            "budget_points": 1000,
        },
    )
    assert response.status_code == 400
    assert "余额不足" in response.json()["message"]
