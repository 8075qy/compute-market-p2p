import pytest

from app.core.security import get_password_hash
from app.models import Account, User, UserRole


@pytest.mark.asyncio
async def test_list_users_requires_admin(client, auth_headers):
    response = await client.get("/api/v1/admin/users", headers=auth_headers)
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_admin_list_users(client, admin_headers, test_user: User):
    response = await client.get("/api/v1/admin/users", headers=admin_headers)
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["total"] >= 1
    ids = {item["id"] for item in data["items"]}
    assert str(test_user.id) in ids
    for item in data["items"]:
        assert "balance_points" in item
        assert "roles" in item
        assert "is_active" in item


@pytest.mark.asyncio
async def test_admin_list_users_keyword_filter(client, admin_headers, test_user: User):
    response = await client.get(
        "/api/v1/admin/users", params={"keyword": test_user.phone}, headers=admin_headers
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["total"] == 1
    assert data["items"][0]["id"] == str(test_user.id)


@pytest.mark.asyncio
async def test_admin_list_users_role_filter(client, admin_headers):
    response = await client.get(
        "/api/v1/admin/users", params={"role": "admin"}, headers=admin_headers
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["total"] >= 1
    assert all("admin" in item["roles"] for item in data["items"])


@pytest.mark.asyncio
async def test_admin_disable_and_enable_user(client, admin_headers, test_user: User):
    # 封禁
    response = await client.post(
        f"/api/v1/admin/users/{test_user.id}/set-active",
        json={"is_active": False, "reason": "违规操作"},
        headers=admin_headers,
    )
    assert response.status_code == 200, response.text
    assert response.json()["data"]["is_active"] is False

    # 被封禁用户无法登录
    login = await client.post(
        "/api/v1/auth/login", json={"phone": test_user.phone, "password": "password123"}
    )
    assert login.status_code == 401

    # 解封
    response = await client.post(
        f"/api/v1/admin/users/{test_user.id}/set-active",
        json={"is_active": True, "reason": "恢复正常"},
        headers=admin_headers,
    )
    assert response.status_code == 200, response.text
    assert response.json()["data"]["is_active"] is True

    # 解封后可以登录
    login = await client.post(
        "/api/v1/auth/login", json={"phone": test_user.phone, "password": "password123"}
    )
    assert login.status_code == 200


@pytest.mark.asyncio
async def test_admin_cannot_disable_another_admin(client, admin_headers, db_session):
    other_admin = User(
        phone="13600136000",
        password_hash=get_password_hash("password123"),
        nickname="13600136000",
        roles=[UserRole.ADMIN.value],
        is_active=True,
    )
    db_session.add(other_admin)
    await db_session.flush()
    db_session.add(Account(user_id=other_admin.id))
    await db_session.commit()
    await db_session.refresh(other_admin)

    response = await client.post(
        f"/api/v1/admin/users/{other_admin.id}/set-active",
        json={"is_active": False, "reason": "test"},
        headers=admin_headers,
    )
    assert response.status_code == 400
    assert "管理员" in response.json()["message"]


@pytest.mark.asyncio
async def test_admin_cannot_disable_self(client, admin_headers, test_admin: User):
    response = await client.post(
        f"/api/v1/admin/users/{test_admin.id}/set-active",
        json={"is_active": False, "reason": "test"},
        headers=admin_headers,
    )
    assert response.status_code == 400
    assert "自己" in response.json()["message"]
