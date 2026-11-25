"""认证依赖：从 Authorization 请求头解析当前用户。"""
from uuid import UUID

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import APIException, ErrorCode
from app.core.security import decode_token
from app.models import User, UserRole
from app.services.auth import AuthService

# 首次部署引导：系统尚未初始化管理员时，仅放行以下端点
_SETUP_EXEMPT_SUFFIXES = (
    "/auth/setup-status",
    "/auth/setup",
)


async def require_setup(
    request: Request, session: AsyncSession = Depends(get_db)
) -> None:
    """首次部署守卫：未初始化管理员时拦截所有接口，强制进入初始化流程。"""
    path = request.url.path
    if any(path.endswith(suffix) for suffix in _SETUP_EXEMPT_SUFFIXES):
        return
    if not await AuthService(session).has_admin():
        raise APIException(
            code=ErrorCode.BUSINESS_ERROR,
            message="系统尚未初始化管理员，请先完成初始化",
            status_code=403,
            data={"need_setup": True},
        )


def _extract_token(authorization: str | None) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": 3000, "message": "无效的认证头", "data": None},
        )
    return authorization[7:].strip()


async def get_current_user_id(
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> UUID:
    token = _extract_token(authorization)
    payload = decode_token(token)
    if not payload or payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": 3000, "message": "令牌无效或已过期", "data": None},
        )
    try:
        return UUID(payload["sub"])
    except (KeyError, ValueError, TypeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": 3000, "message": "令牌内容无效", "data": None},
        ) from exc


async def get_current_user(
    user_id: UUID = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
) -> User:
    user = await session.get(User, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": 5000, "message": "用户不存在", "data": None},
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": 3000, "message": "账户已被禁用", "data": None},
        )
    return user


async def get_current_admin(user: User = Depends(get_current_user)) -> User:
    if not user.has_role(UserRole.ADMIN):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": 3000, "message": "需要管理员权限", "data": None},
        )
    return user
