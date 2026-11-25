import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models import User
from app.schemas.common import Response
from app.schemas.node import (
    ExecutionCompleteRequest,
    ExecutionFailRequest,
    ExecutionStateResponse,
    PendingExecutionResponse,
)
from app.schemas.upload import InputDownloadResponse, PresignDownloadResponse
from app.services.execution import ExecutionService
from app.services.upload import UploadService

router = APIRouter(prefix="/supplier", tags=["供给方·执行闭环"])


@router.get(
    "/nodes/{node_id}/pending-executions",
    response_model=Response[list[PendingExecutionResponse]],
)
async def list_pending_executions(
    node_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    service = ExecutionService(session)
    items = await service.get_pending_executions(node_id, user.id)
    return Response(data=[PendingExecutionResponse(**item) for item in items])


@router.get(
    "/executions/{execution_id}/model/download",
    response_model=Response[PresignDownloadResponse],
)
async def download_execution_model(
    execution_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    service = UploadService(session)
    result = await service.presign_model_download(user.id, execution_id)
    return Response(data=result)


@router.get(
    "/executions/{execution_id}/input/download",
    response_model=Response[InputDownloadResponse],
)
async def download_execution_input(
    execution_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    service = UploadService(session)
    result = await service.presign_input_download(user.id, execution_id)
    return Response(data=result)


@router.post(
    "/executions/{execution_id}/start",
    response_model=Response[ExecutionStateResponse],
)
async def start_execution(
    execution_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    service = ExecutionService(session)
    execution = await service.start_execution(execution_id, user.id)
    return Response(data=ExecutionStateResponse.model_validate(execution))


@router.post(
    "/executions/{execution_id}/complete",
    response_model=Response[ExecutionStateResponse],
)
async def complete_execution(
    execution_id: uuid.UUID,
    data: ExecutionCompleteRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    service = ExecutionService(session)
    execution = await service.complete_execution(execution_id, user.id, data)
    return Response(data=ExecutionStateResponse.model_validate(execution))


@router.post(
    "/executions/{execution_id}/fail",
    response_model=Response[ExecutionStateResponse],
)
async def fail_execution(
    execution_id: uuid.UUID,
    data: ExecutionFailRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    service = ExecutionService(session)
    execution = await service.fail_execution(execution_id, user.id, data.error_message)
    return Response(data=ExecutionStateResponse.model_validate(execution))
