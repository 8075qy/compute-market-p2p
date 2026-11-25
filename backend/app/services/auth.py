import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import AuthError, BusinessError
from app.core.redis_client import get_redis
from app.core.redis_keys import RedisKeys
from app.core.security import (
    create_access_token,
    create_refresh_token,
    get_password_hash,
    verify_password,
)
from app.models import Account, User, UserRole
from app.schemas.auth import AdminSetupRequest, LoginRequest, RegisterRequest, SendCodeRequest


class AuthService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.redis = get_redis()

    async def register(self, data: RegisterRequest) -> dict:
        # 检查用户名是否已存在
        existing = await self.session.execute(
            select(User).where(User.username == data.username)
        )
        if existing.scalar_one_or_none():
            raise BusinessError("该用户名已被占用")

        # 创建用户（注册仅限普通用户，管理员只能通过首次部署初始化流程创建）
        user = User(
            username=data.username,
            password_hash=get_password_hash(data.password),
            roles=[UserRole.USER.value],
            nickname=data.nickname,
        )
        self.session.add(user)
        await self.session.flush()

        # 创建积分账户
        account = Account(user_id=user.id)
        self.session.add(account)
        await self.session.flush()

        # 生成 token
        access_token = create_access_token({"sub": str(user.id), "roles": user.roles})
        refresh_token = create_refresh_token({"sub": str(user.id), "roles": user.roles})

        await self.session.commit()

        return {
            "user": user,
            "access_token": access_token,
            "refresh_token": refresh_token,
        }

    async def login(self, data: LoginRequest) -> dict:
        # 查找用户（用户名/手机号/邮箱三选一）
        stmt = (
            select(User)
            .where(
                (User.phone == data.contact)
                | (User.email == data.contact)
                | (User.username == data.contact)
            )
            .options(selectinload(User.account))
        )
        result = await self.session.execute(stmt)
        user = result.scalar_one_or_none()

        if not user or not verify_password(data.password, user.password_hash):
            raise AuthError("用户名/手机号/邮箱或密码错误")

        if not user.is_active:
            raise AuthError("账户已被禁用")

        # 生成 token
        access_token = create_access_token({"sub": str(user.id), "roles": user.roles})
        refresh_token = create_refresh_token({"sub": str(user.id), "roles": user.roles})

        return {
            "user": user,
            "access_token": access_token,
            "refresh_token": refresh_token,
        }

    async def refresh_token(self, refresh_token: str) -> dict:
        from app.core.security import decode_token

        payload = decode_token(refresh_token)
        if not payload or payload.get("type") != "refresh":
            raise AuthError("无效的刷新令牌")

        user_id = uuid.UUID(payload["sub"])
        stmt = select(User).where(User.id == user_id).options(selectinload(User.account))
        result = await self.session.execute(stmt)
        user = result.scalar_one_or_none()

        if not user or not user.is_active:
            raise AuthError("用户不存在或已被禁用")

        access_token = create_access_token({"sub": str(user.id), "roles": user.roles})
        new_refresh_token = create_refresh_token({"sub": str(user.id), "roles": user.roles})

        return {"access_token": access_token, "refresh_token": new_refresh_token}

    async def send_code(self, data: SendCodeRequest) -> None:
        # 这里简化处理，实际应该发送短信/邮件
        # 开发环境使用固定验证码
        code = "123456"
        key = RedisKeys.VERIFICATION_CODE.format(contact=data.contact)
        await self.redis.setex(key, 300, code)  # 5分钟过期

    async def has_admin(self) -> bool:
        """判断系统中是否已存在管理员（用于首次部署引导）。

        采用可移植实现：遍历 users.roles（JSON 数组），兼容 PostgreSQL 与测试环境 SQLite。
        """
        result = await self.session.execute(select(User.roles))
        return any(
            roles and UserRole.ADMIN.value in roles
            for (roles,) in result
        )

    async def setup_admin(self, data: AdminSetupRequest) -> dict:
        """首次部署初始化：创建第一个管理员（仅当系统尚无管理员时可用）。"""
        if await self.has_admin():
            raise BusinessError("管理员已初始化，请直接登录")

        existing = await self.session.execute(
            select(User).where(User.username == data.username)
        )
        if existing.scalar_one_or_none():
            raise BusinessError("该用户名已被占用")

        user = User(
            username=data.username,
            phone=None,
            email=None,
            password_hash=get_password_hash(data.password),
            roles=[UserRole.ADMIN.value],
            nickname=data.nickname,
        )
        self.session.add(user)
        await self.session.flush()

        account = Account(user_id=user.id)
        self.session.add(account)
        await self.session.flush()

        access_token = create_access_token({"sub": str(user.id), "roles": user.roles})
        refresh_token = create_refresh_token({"sub": str(user.id), "roles": user.roles})

        await self.session.commit()

        return {
            "user": user,
            "access_token": access_token,
            "refresh_token": refresh_token,
        }

    async def _verify_code(self, contact: str, code: str, _code_type: str) -> None:
        key = RedisKeys.VERIFICATION_CODE.format(contact=contact)
        stored_code = await self.redis.get(key)
        if not stored_code or stored_code != code:
            raise AuthError("验证码错误或已过期")
        await self.redis.delete(key)

    async def get_current_user(self, user_id: uuid.UUID) -> User:
        stmt = select(User).where(User.id == user_id).options(selectinload(User.account))
        result = await self.session.execute(stmt)
        user = result.scalar_one_or_none()
        if not user:
            raise AuthError("用户不存在")
        return user

    async def update_profile(
        self, user_id: uuid.UUID, nickname: str | None, avatar_url: str | None
    ) -> User:
        stmt = select(User).where(User.id == user_id)
        result = await self.session.execute(stmt)
        user = result.scalar_one_or_none()
        if not user:
            raise AuthError("用户不存在")

        if nickname is not None:
            user.nickname = nickname
        if avatar_url is not None:
            user.avatar_url = avatar_url

        await self.session.commit()
        await self.session.refresh(user)
        return user
