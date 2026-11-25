from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models import User
from app.schemas.account import AccountResponse
from app.schemas.common import Response
from app.services.account import AccountService

router = APIRouter(prefix="/account", tags=["账户与算力分"])


@router.get("", response_model=Response[AccountResponse])
async def get_account(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    service = AccountService(session)
    overview = await service.get_account_overview(user.id)
    return Response(data=AccountResponse(**overview))
