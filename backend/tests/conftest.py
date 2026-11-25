import asyncio
import uuid
from collections.abc import AsyncGenerator
from pathlib import Path

import fakeredis.aioredis
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.database import get_db
from app.core.redis_client import close_redis, init_redis
from app.core.security import get_password_hash
from app.main import app
from app.models import (
    Account,
    Base,
    Node,
    NodeStatus,
    Task,
    TaskExecution,
    TaskStatus,
    TaskType,
    User,
    UserRole,
)

TEST_DB_PATH = Path(__file__).parent.parent / f"test_{uuid.uuid4().hex}.db"
TEST_DATABASE_URL = f"sqlite+aiosqlite:///{TEST_DB_PATH.resolve()}"


@pytest.fixture(scope="session", autouse=True)
def setup_database():
    async def create():
        engine = create_async_engine(
            TEST_DATABASE_URL,
            poolclass=NullPool,
            connect_args={"check_same_thread": False},
        )
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        await engine.dispose()

    asyncio.run(create())
    yield
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    engine = create_async_engine(
        TEST_DATABASE_URL, poolclass=NullPool, connect_args={"check_same_thread": False}
    )
    async with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            await conn.execute(text(f"DELETE FROM {table.name}"))
        await conn.commit()

    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        # 默认种子一个管理员，保证既有测试在「系统已初始化」前提下运行
        admin = User(
            username="admin",
            phone=None,
            email=None,
            password_hash=get_password_hash("password123"),
            nickname="测试管理员",
            roles=[UserRole.ADMIN.value],
            is_active=True,
        )
        session.add(admin)
        await session.flush()
        session.add(Account(user_id=admin.id))
        await session.commit()
        yield session
        await session.rollback()
    await engine.dispose()


@pytest_asyncio.fixture(autouse=True)
async def init_test_redis():
    fake_redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    await init_redis(fake_redis)
    yield
    await close_redis()


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


async def create_user(
    session: AsyncSession,
    phone: str,
    role: UserRole = UserRole.USER,
    balance: int = 0,
    frozen: int = 0,
    roles: list[str] | None = None,
) -> User:
    user = User(
        phone=phone,
        password_hash=get_password_hash("password123"),
        nickname=phone,
        roles=roles or [role.value],
        is_active=True,
    )
    session.add(user)
    await session.flush()
    session.add(
        Account(
            user_id=user.id,
            balance_points=balance,
            frozen_points=frozen,
        )
    )
    await session.commit()
    await session.refresh(user)
    return user


@pytest_asyncio.fixture
async def test_user(db_session: AsyncSession) -> User:
    return await create_user(db_session, "13800138000", UserRole.USER, balance=20000)


@pytest_asyncio.fixture
async def test_supplier(db_session: AsyncSession) -> User:
    return await create_user(db_session, "13900139000", UserRole.USER)


@pytest_asyncio.fixture
async def test_admin(db_session: AsyncSession) -> User:
    return await create_user(db_session, "13700137000", UserRole.ADMIN)


async def _login(client: AsyncClient, phone: str) -> dict:
    response = await client.post(
        "/api/v1/auth/login", json={"phone": phone, "password": "password123"}
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['data']['access_token']}"}


@pytest_asyncio.fixture
async def auth_headers(client: AsyncClient, test_user: User) -> dict:
    return await _login(client, test_user.phone)


@pytest_asyncio.fixture
async def supplier_headers(client: AsyncClient, test_supplier: User) -> dict:
    return await _login(client, test_supplier.phone)


@pytest_asyncio.fixture
async def admin_headers(client: AsyncClient, test_admin: User) -> dict:
    return await _login(client, test_admin.phone)


@pytest_asyncio.fixture
async def online_node(db_session: AsyncSession, test_supplier: User) -> Node:
    node = Node(
        owner_id=test_supplier.id,
        name="RTX 4090 Node",
        gpu_model="RTX 4090",
        vram_gb=24,
        peak_tflops=82.6,
        region_province="贵州省",
        region_city="贵阳市",
        status=NodeStatus.ONLINE,
        is_online=True,
        reputation_score=100,
    )
    db_session.add(node)
    await db_session.commit()
    await db_session.refresh(node)
    return node


@pytest_asyncio.fixture
async def completed_execution(
    db_session: AsyncSession, test_user: User, test_supplier: User, online_node: Node
) -> TaskExecution:
    task = Task(
        task_no="T202601010001",
        demander_id=test_user.id,
        type=TaskType.INFERENCE,
        title="测试任务",
        model_source="platform",
        params_json="{}",
        required_vram_gb=8,
        budget_points=5000,
        preauthorized_points=5000,
        min_settlement_unit=1000,
        status=TaskStatus.RUNNING,
    )
    account = (
        await db_session.execute(
            select(Account).where(Account.user_id == test_user.id)
        )
    ).scalar_one()
    account.balance_points -= 5000
    account.frozen_points += 5000
    db_session.add(task)
    await db_session.flush()
    execution = TaskExecution(
        task_id=task.id,
        node_id=online_node.id,
        attempt_no=1,
        status=TaskStatus.RUNNING,
        compute_duration_seconds=3600,
        platform_fee_rate=0,
    )
    db_session.add(execution)
    await db_session.commit()
    await db_session.refresh(execution)
    return execution
