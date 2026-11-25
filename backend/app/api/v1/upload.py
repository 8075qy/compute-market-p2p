import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models import User
from app.schemas.common import Response
from app.schemas.upload import (
    InputConfirmResponse,
    PresignUploadRequest,
    PresignUploadResponse,
    UploadConfirmRequest,
    UploadConfirmResponse,
)
from app.services.batch_input import BatchInputService
from app.services.upload import UploadService

demand_router = APIRouter(prefix="/demand/uploads", tags=["需求方·文件上传"])
supplier_router = APIRouter(prefix="/supplier/uploads", tags=["供给方·文件上传"])


@demand_router.post("/model/presign", response_model=Response[PresignUploadResponse])
async def presign_model_upload(
    data: PresignUploadRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    service = UploadService(session)
    result = await service.presign_model_upload(user.id, data)
    return Response(data=result)


@demand_router.post("/model/confirm", response_model=Response[UploadConfirmResponse])
async def confirm_model_upload(
    data: UploadConfirmRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    service = UploadService(session)
    result = await service.confirm_model_upload(user.id, data)
    return Response(data=result)


@demand_router.post("/input/presign", response_model=Response[PresignUploadResponse])
async def presign_input_upload(
    data: PresignUploadRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    service = BatchInputService(session)
    result = await service.presign_input_upload(user.id, data.filename)
    return Response(data=result)


@demand_router.post("/input/confirm", response_model=Response[InputConfirmResponse])
async def confirm_input_upload(
    data: UploadConfirmRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    service = BatchInputService(session)
    result = await service.confirm_input_upload(user.id, data.object_key)
    return Response(data=result)


@supplier_router.post("/result/presign", response_model=Response[PresignUploadResponse])
async def presign_result_upload(
    execution_id: uuid.UUID,
    data: PresignUploadRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    service = UploadService(session)
    result = await service.presign_result_upload(user.id, execution_id, data)
    return Response(data=result)
