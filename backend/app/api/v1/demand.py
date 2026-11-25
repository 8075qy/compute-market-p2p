import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models import TaskStatus, TaskType, User
from app.schemas.common import PageResponse, Response
from app.schemas.task import (
    TaskCreate,
    TaskDetailResponse,
    TaskListQuery,
    TaskLogResponse,
    TaskResponse,
    TaskResultResponse,
)
from app.services.task import TaskService

router = APIRouter(prefix="/demand/tasks", tags=["需求方·任务管理"])


@router.get("", response_model=Response[PageResponse[TaskResponse]])
async def list_tasks(
    page: int = 1,
    page_size: int = 20,
    status: TaskStatus | None = None,
    type: TaskType | None = None,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    service = TaskService(session)
    query = TaskListQuery(page=page, page_size=page_size, status=status, type=type)
    tasks, total = await service.get_tasks(user.id, query)
    return Response(data=PageResponse.create(
        items=[TaskResponse.model_validate(t) for t in tasks],
        total=total, page=page, page_size=page_size
    ))


@router.post("", response_model=Response[TaskResponse])
async def create_task(
    data: TaskCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    service = TaskService(session)
    task = await service.create_task(user.id, data)
    return Response(data=TaskResponse.model_validate(task))


@router.get("/{task_id}", response_model=Response[TaskDetailResponse])
async def get_task(
    task_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    service = TaskService(session)
    task = await service.get_task(task_id, user.id)
    return Response(data=TaskDetailResponse.model_validate(task))


@router.post("/{task_id}/cancel", response_model=Response[TaskResponse])
async def cancel_task(
    task_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    service = TaskService(session)
    task = await service.cancel_task(task_id, user.id)
    return Response(data=TaskResponse.model_validate(task))


@router.post("/{task_id}/retry", response_model=Response[TaskResponse])
async def retry_task(
    task_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    service = TaskService(session)
    task = await service.retry_task(task_id, user.id)
    return Response(data=TaskResponse.model_validate(task))


@router.get("/{task_id}/logs", response_model=Response[TaskLogResponse])
async def get_task_logs(
    task_id: uuid.UUID,
    attempt_no: int | None = None,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    service = TaskService(session)
    result = await service.get_task_logs(task_id, user.id, attempt_no)
    return Response(data=TaskLogResponse(**result))


@router.get("/{task_id}/result", response_model=Response[TaskResultResponse])
async def get_task_result(
    task_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    service = TaskService(session)
    result = await service.get_task_result(task_id, user.id)
    return Response(data=TaskResultResponse(**result))
