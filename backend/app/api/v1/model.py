import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_admin, get_current_user
from app.models import User
from app.schemas.common import PageResponse, Response
from app.schemas.model import ModelCreate, ModelResponse, ModelUpdate
from app.services.model import ModelService

demand_router = APIRouter(prefix="/demand/models", tags=["需求方·平台模型"])
admin_router = APIRouter(prefix="/admin/models", tags=["平台管理·模型库"])


@demand_router.get("", response_model=Response[PageResponse[ModelResponse]])
async def list_published_models(
    page: int = 1,
    page_size: int = 20,
    keyword: str | None = None,
    framework: str | None = None,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """上架中的平台模型列表，供需求方发布任务时选择。"""
    service = ModelService(session)
    models, total = await service.list_published(page, page_size, keyword, framework)
    return Response(data=PageResponse.create(
        items=[ModelResponse.model_validate(m) for m in models],
        total=total, page=page, page_size=page_size,
    ))


@demand_router.get("/{model_id}", response_model=Response[ModelResponse])
async def get_published_model(
    model_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    service = ModelService(session)
    model = await service.get_published(model_id)
    return Response(data=ModelResponse.model_validate(model))


@admin_router.get("", response_model=Response[PageResponse[ModelResponse]])
async def list_all_models(
    page: int = 1,
    page_size: int = 20,
    keyword: str | None = None,
    framework: str | None = None,
    is_published: bool | None = None,
    admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_db),
):
    service = ModelService(session)
    models, total = await service.list_all(page, page_size, keyword, framework, is_published)
    return Response(data=PageResponse.create(
        items=[ModelResponse.model_validate(m) for m in models],
        total=total, page=page, page_size=page_size,
    ))


@admin_router.post("", response_model=Response[ModelResponse])
async def create_model(
    data: ModelCreate,
    admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_db),
):
    service = ModelService(session)
    model = await service.create(data, admin.id)
    return Response(data=ModelResponse.model_validate(model))


@admin_router.put("/{model_id}", response_model=Response[ModelResponse])
async def update_model(
    model_id: uuid.UUID,
    data: ModelUpdate,
    admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_db),
):
    service = ModelService(session)
    model = await service.update(model_id, data, admin.id)
    return Response(data=ModelResponse.model_validate(model))


@admin_router.delete("/{model_id}", response_model=Response[dict])
async def delete_model(
    model_id: uuid.UUID,
    admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_db),
):
    service = ModelService(session)
    await service.delete(model_id, admin.id)
    return Response(message="ok")
