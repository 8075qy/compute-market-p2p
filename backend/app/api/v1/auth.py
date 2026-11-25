from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models import User
from app.schemas.account import AccountResponse
from app.schemas.auth import (
    AdminSetupRequest,
    AuthResponse,
    LoginRequest,
    RefreshTokenRequest,
    RegisterRequest,
    SendCodeRequest,
    UserResponse,
)
from app.schemas.common import Response
from app.services.account import AccountService
from app.services.auth import AuthService

router = APIRouter(prefix="/auth", tags=["认证授权"])


@router.post("/register", response_model=Response[AuthResponse])
async def register(data: RegisterRequest, session: AsyncSession = Depends(get_db)):
    service = AuthService(session)
    result = await service.register(data)
    return Response(data=AuthResponse(
        user=UserResponse.model_validate(result["user"]),
        access_token=result["access_token"],
        refresh_token=result["refresh_token"],
    ))


@router.post("/login", response_model=Response[AuthResponse])
async def login(data: LoginRequest, session: AsyncSession = Depends(get_db)):
    service = AuthService(session)
    result = await service.login(data)
    return Response(data=AuthResponse(
        user=UserResponse.model_validate(result["user"]),
        access_token=result["access_token"],
        refresh_token=result["refresh_token"],
    ))


@router.post("/refresh", response_model=Response[dict])
async def refresh(data: RefreshTokenRequest, session: AsyncSession = Depends(get_db)):
    service = AuthService(session)
    result = await service.refresh_token(data.refresh_token)
    return Response(data=result)


@router.post("/logout", response_model=Response[dict])
async def logout():
    return Response(data={})


@router.post("/send-code", response_model=Response[dict])
async def send_code(data: SendCodeRequest, session: AsyncSession = Depends(get_db)):
    service = AuthService(session)
    await service.send_code(data)
    return Response(data={})


@router.get("/setup-status", response_model=Response[dict])
async def setup_status(session: AsyncSession = Depends(get_db)):
    service = AuthService(session)
    need_setup = not await service.has_admin()
    return Response(data={"need_setup": need_setup})


@router.post("/setup", response_model=Response[AuthResponse])
async def setup_admin(data: AdminSetupRequest, session: AsyncSession = Depends(get_db)):
    service = AuthService(session)
    result = await service.setup_admin(data)
    return Response(data=AuthResponse(
        user=UserResponse.model_validate(result["user"]),
        access_token=result["access_token"],
        refresh_token=result["refresh_token"],
    ))


@router.get("/me", response_model=Response[dict])
async def get_me(user: User = Depends(get_current_user), session: AsyncSession = Depends(get_db)):
    service = AuthService(session)
    user_with_account = await service.get_current_user(user.id)
    overview = await AccountService(session).get_account_overview(user.id)
    return Response(data={
        "user": UserResponse.model_validate(user_with_account),
        "account": AccountResponse(**overview),
        "roles": user_with_account.roles,
    })


@router.put("/me", response_model=Response[UserResponse])
async def update_me(
    nickname: str | None = None,
    avatar_url: str | None = None,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    service = AuthService(session)
    updated = await service.update_profile(user.id, nickname, avatar_url)
    return Response(data=UserResponse.model_validate(updated))
