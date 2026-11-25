import uuid

import pytest
from sqlalchemy import select, text

from app.models import Account, Base, User


@pytest.mark.asyncio
async def test_register_login_and_me(client):
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "username": "testuser123",
            "password": "password123",
            "nickname": "测试供给方",
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()["data"]
    assert body["user"]["roles"] == ["user"]
    assert body["user"]["username"] == "testuser123"
    assert body["access_token"]
    assert body["refresh_token"]

    headers = {"Authorization": f"Bearer {body['access_token']}"}
    response = await client.get("/api/v1/auth/me", headers=headers)
    assert response.status_code == 200
    assert response.json()["data"]["roles"] == ["user"]
    assert response.json()["data"]["account"]["balance_points"] == 0


@pytest.mark.asyncio
async def test_register_rejects_duplicate_username(client):
    payload = {"username": "duplicate_user", "password": "password123"}
    first = await client.post("/api/v1/auth/register", json=payload)
    assert first.status_code == 200, first.text

    second = await client.post("/api/v1/auth/register", json=payload)
    assert second.status_code == 400
    assert second.json()["message"] == "该用户名已被占用"


@pytest.mark.asyncio
async def test_login_with_wrong_password(client, test_user: User):
    response = await client.post(
        "/api/v1/auth/login",
        json={"phone": test_user.phone, "password": "wrong-password"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_protected_endpoint_requires_token(client):
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_admin_endpoint_requires_admin(client, auth_headers):
    response = await client.get("/api/v1/admin/dashboard", headers=auth_headers)
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_admin_can_read_dashboard(client, admin_headers):
    response = await client.get("/api/v1/admin/dashboard", headers=admin_headers)
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["fee_rate"] == 0
    assert data["online_nodes"] == 0


@pytest.mark.asyncio
async def test_dual_role_user_can_act_as_supplier_and_demander(client, db_session):
    """供需一体：普通用户可同时创建节点(供给方)与发布任务(需求方)。"""
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "username": "dual_role_user",
            "password": "password123",
            "nickname": "双角色用户",
        },
    )
    assert response.status_code == 200, response.text
    token = response.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # /me 返回普通用户身份
    me = await client.get("/api/v1/auth/me", headers=headers)
    assert set(me.json()["data"]["roles"]) == {"user"}

    # 供给方能力：创建节点
    node_resp = await client.post(
        "/api/v1/supplier/nodes",
        headers=headers,
        json={
            "name": "双角色节点",
            "gpu_model": "RTX 4090",
            "vram_gb": 24,
            "peak_tflops": 82.6,
            "region_province": "贵州省",
            "region_city": "贵阳市",
        },
    )
    assert node_resp.status_code == 200, node_resp.text

    # 需求方能力：充值余额后发布任务
    user_id = uuid.UUID(response.json()["data"]["user"]["id"])
    account = (
        await db_session.execute(select(Account).where(Account.user_id == user_id))
    ).scalar_one()
    account.balance_points = 5000
    await db_session.commit()

    task_resp = await client.post(
        "/api/v1/demand/tasks",
        headers=headers,
        json={
            "type": "inference",
            "title": "鉴权测试任务",
            "model_source": "platform",
            "params": {"prompt": "hi"},
            "required_vram_gb": 8,
            "budget_points": 2000,
        },
    )
    assert task_resp.status_code == 200, task_resp.text


@pytest.mark.asyncio
async def test_first_run_setup_flow(client, db_session):
    """首次部署：无管理员时全局守卫拦截，仅可完成管理员初始化。"""
    # 清空所有数据，模拟首次部署（无任何管理员）
    for table in reversed(Base.metadata.sorted_tables):
        await db_session.execute(text(f"DELETE FROM {table.name}"))
    await db_session.commit()

    # 初始化前：setup-status 返回 need_setup=True
    response = await client.get("/api/v1/auth/setup-status")
    assert response.status_code == 200
    assert response.json()["data"]["need_setup"] is True

    # 初始化前：业务接口被全局守卫拦截
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 403

    # 创建第一个管理员
    response = await client.post(
        "/api/v1/auth/setup",
        json={"username": "root", "password": "password123", "nickname": "系统管理员"},
    )
    assert response.status_code == 200, response.text
    body = response.json()["data"]
    assert body["user"]["roles"] == ["admin"]
    assert body["access_token"]

    # 初始化后：管理员可访问业务接口
    headers = {"Authorization": f"Bearer {body['access_token']}"}
    response = await client.get("/api/v1/auth/me", headers=headers)
    assert response.status_code == 200
    assert response.json()["data"]["roles"] == ["admin"]

    # 重复初始化被拒绝
    response = await client.post(
        "/api/v1/auth/setup",
        json={"username": "root2", "password": "password123"},
    )
    assert response.status_code == 400
