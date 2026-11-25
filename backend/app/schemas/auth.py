from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models import UserRole


class _ContactMixin(BaseModel):
    """兼容 phone/email 与统一的 contact 字段。"""

    @model_validator(mode="before")
    @classmethod
    def _normalize_contact(cls, data):
        if isinstance(data, dict) and not data.get("contact"):
            contact = data.get("phone") or data.get("email")
            if contact:
                data = {**data, "contact": contact}
        return data


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=64, description="用户名")
    password: str = Field(..., min_length=8, max_length=64, description="密码")
    nickname: str | None = Field(None, max_length=64, description="昵称")


class LoginRequest(_ContactMixin):
    contact: str = Field(..., description="用户名/手机号/邮箱")
    password: str = Field(..., description="密码")


class AdminSetupRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=64, description="管理员用户名")
    password: str = Field(..., min_length=8, max_length=64, description="密码")
    nickname: str | None = Field(None, max_length=64, description="昵称")


class RefreshTokenRequest(BaseModel):
    refresh_token: str = Field(..., description="刷新令牌")


class SendCodeRequest(_ContactMixin):
    contact: str = Field(..., description="手机号或邮箱")
    type: str = Field(
        default="register", pattern=r"^(register|login|reset)$", description="验证码类型"
    )


class UserResponse(BaseModel):
    id: UUID
    phone: str | None = None
    username: str | None = None
    email: str | None = None
    roles: list[UserRole]
    nickname: str | None = None
    avatar_url: str | None = None
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AuthResponse(BaseModel):
    user: UserResponse
    access_token: str
    refresh_token: str
