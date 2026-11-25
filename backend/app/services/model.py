from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BusinessError, NotFoundError
from app.models import PlatformModel
from app.schemas.model import ModelCreate, ModelUpdate
from app.services.audit import AuditService


class ModelService:
    """平台模型库：上架模型供需求方发布任务时选择，管理端负责维护目录。"""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.audit = AuditService(session)

    @staticmethod
    def _apply_filters(stmt, keyword: str | None, framework: str | None):
        if keyword:
            stmt = stmt.where(PlatformModel.name.ilike(f"%{keyword}%"))
        if framework:
            stmt = stmt.where(PlatformModel.framework == framework)
        return stmt

    async def list_published(
        self, page: int, page_size: int, keyword: str | None, framework: str | None
    ) -> tuple[list[PlatformModel], int]:
        base = select(PlatformModel).where(PlatformModel.is_published)
        base = self._apply_filters(base, keyword, framework)
        count_stmt = select(func.count()).select_from(base.subquery())
        total = (await self.session.execute(count_stmt)).scalar_one()
        stmt = (
            base.order_by(PlatformModel.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        models = (await self.session.execute(stmt)).scalars().all()
        return list(models), total

    async def get_published(self, model_id: uuid.UUID) -> PlatformModel:
        model = await self.session.get(PlatformModel, model_id)
        if not model or not model.is_published:
            raise NotFoundError("模型不存在或未上架")
        return model

    async def list_all(
        self,
        page: int,
        page_size: int,
        keyword: str | None,
        framework: str | None,
        is_published: bool | None,
    ) -> tuple[list[PlatformModel], int]:
        stmt = select(PlatformModel)
        stmt = self._apply_filters(stmt, keyword, framework)
        if is_published is not None:
            stmt = stmt.where(PlatformModel.is_published == is_published)
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await self.session.execute(count_stmt)).scalar_one()
        result_stmt = (
            stmt.order_by(PlatformModel.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        models = (await self.session.execute(result_stmt)).scalars().all()
        return list(models), total

    async def get(self, model_id: uuid.UUID) -> PlatformModel:
        model = await self.session.get(PlatformModel, model_id)
        if not model:
            raise NotFoundError("模型不存在")
        return model

    async def create(self, data: ModelCreate, admin_id: uuid.UUID) -> PlatformModel:
        exists = (
            await self.session.execute(
                select(PlatformModel.id).where(PlatformModel.name == data.name)
            )
        ).scalar_one_or_none()
        if exists:
            raise BusinessError("模型名称已存在")

        model = PlatformModel(
            name=data.name,
            framework=data.framework,
            size_bytes=data.size_bytes,
            required_vram_gb=data.required_vram_gb,
            source=data.source,
            content_hash=data.content_hash,
            minio_key=data.minio_key,
            description=data.description,
            is_published=data.is_published,
        )
        self.session.add(model)
        await self.session.flush()

        await self.audit.log(
            "model.created",
            "platform_model",
            model.id,
            {"name": model.name, "framework": model.framework, "is_published": model.is_published},
            user_id=admin_id,
        )
        return model

    async def update(
        self, model_id: uuid.UUID, data: ModelUpdate, admin_id: uuid.UUID
    ) -> PlatformModel:
        model = await self.get(model_id)

        if data.name and data.name != model.name:
            exists = (
                await self.session.execute(
                    select(PlatformModel.id).where(
                        PlatformModel.name == data.name, PlatformModel.id != model_id
                    )
                )
            ).scalar_one_or_none()
            if exists:
                raise BusinessError("模型名称已存在")

        for field in (
            "name",
            "framework",
            "size_bytes",
            "required_vram_gb",
            "source",
            "content_hash",
            "minio_key",
            "description",
            "is_published",
        ):
            value = getattr(data, field)
            if value is not None:
                setattr(model, field, value)

        await self.session.flush()
        await self.audit.log(
            "model.updated",
            "platform_model",
            model.id,
            {"name": model.name, "is_published": model.is_published},
            user_id=admin_id,
        )
        return model

    async def delete(self, model_id: uuid.UUID, admin_id: uuid.UUID) -> None:
        model = await self.get(model_id)
        await self.session.delete(model)
        await self.session.flush()
        await self.audit.log(
            "model.deleted",
            "platform_model",
            model_id,
            {"name": model.name},
            user_id=admin_id,
        )
