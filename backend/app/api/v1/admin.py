import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_admin
from app.models import NodeStatus, TaskStatus, User, VerificationStatus
from app.schemas.admin import (
    AdminAuditLogResponse,
    AdminDashboardResponse,
    AdminNodeForceOfflineRequest,
    AdminNodeResponse,
    AdminTaskResponse,
    AdminUserResponse,
    AdminUserSetActiveRequest,
    AdminVerificationRecordResponse,
    PlatformConfigResponse,
    PlatformConfigUpdate,
)
from app.schemas.common import PageResponse, Response
from app.services.admin import AdminService

router = APIRouter(prefix="/admin", tags=["平台管理"])


@router.get("/dashboard", response_model=Response[AdminDashboardResponse])
async def get_dashboard(
    admin: User = Depends(get_current_admin), session: AsyncSession = Depends(get_db)
):
    service = AdminService(session)
    data = await service.get_dashboard()
    return Response(data=AdminDashboardResponse(**data))


@router.get("/config", response_model=Response[PlatformConfigResponse])
async def get_config(
    admin: User = Depends(get_current_admin), session: AsyncSession = Depends(get_db)
):
    service = AdminService(session)
    config = await service.get_config()
    return Response(data=PlatformConfigResponse.model_validate(config))


@router.put("/config", response_model=Response[PlatformConfigResponse])
async def update_config(
    data: PlatformConfigUpdate,
    admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_db),
):
    service = AdminService(session)
    config = await service.update_config(data, admin.id)
    return Response(data=PlatformConfigResponse.model_validate(config))


@router.get("/nodes", response_model=Response[PageResponse[AdminNodeResponse]])
async def list_all_nodes(
    page: int = 1,
    page_size: int = 20,
    status: str | None = None,
    admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_db),
):
    service = AdminService(session)
    nodes, total = await service.get_all_nodes(
        page, page_size, NodeStatus(status) if status else None
    )
    return Response(
        data=PageResponse.create(
            items=[AdminNodeResponse.model_validate(n) for n in nodes],
            total=total,
            page=page,
            page_size=page_size,
        )
    )


@router.post("/nodes/{node_id}/force-offline", response_model=Response[AdminNodeResponse])
async def force_node_offline(
    node_id: uuid.UUID,
    data: AdminNodeForceOfflineRequest,
    admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_db),
):
    service = AdminService(session)
    node = await service.force_node_offline(node_id, data, admin.id)
    return Response(data=AdminNodeResponse.model_validate(node))


@router.get("/tasks", response_model=Response[PageResponse[AdminTaskResponse]])
async def list_all_tasks(
    page: int = 1,
    page_size: int = 20,
    status: str | None = None,
    admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_db),
):
    service = AdminService(session)
    tasks, total = await service.get_all_tasks(
        page, page_size, TaskStatus(status) if status else None
    )
    return Response(
        data=PageResponse.create(
            items=[AdminTaskResponse.model_validate(t) for t in tasks],
            total=total,
            page=page,
            page_size=page_size,
        )
    )


@router.post("/tasks/{task_id}/cancel-scheduling", response_model=Response[AdminTaskResponse])
async def cancel_task_scheduling(
    task_id: uuid.UUID,
    admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_db),
):
    service = AdminService(session)
    task = await service.cancel_task_scheduling(task_id, admin.id)
    return Response(data=AdminTaskResponse.model_validate(task))


@router.get("/audit-logs", response_model=Response[PageResponse[AdminAuditLogResponse]])
async def list_audit_logs(
    page: int = 1,
    page_size: int = 20,
    event_type: str | None = None,
    entity_type: str | None = None,
    user_id: str | None = None,
    admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_db),
):
    service = AdminService(session)
    logs, total = await service.get_audit_logs(
        page, page_size, event_type, entity_type, uuid.UUID(user_id) if user_id else None
    )
    return Response(
        data=PageResponse.create(
            items=[AdminAuditLogResponse.model_validate(log) for log in logs],
            total=total,
            page=page,
            page_size=page_size,
        )
    )


@router.get("/audit-logs/verify", response_model=Response[dict])
async def verify_audit_chain(
    start_from: str | None = None,
    admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_db),
):
    service = AdminService(session)
    from datetime import datetime

    valid, errors = await service.verify_audit_chain(
        datetime.fromisoformat(start_from) if start_from else None
    )
    return Response(data={"valid": valid, "errors": errors})


@router.get(
    "/verification-records", response_model=Response[PageResponse[AdminVerificationRecordResponse]]
)
async def list_verification_records(
    page: int = 1,
    page_size: int = 20,
    status: str | None = None,
    admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_db),
):
    service = AdminService(session)
    records, total = await service.list_verification_records(
        page, page_size, VerificationStatus(status) if status else None
    )
    return Response(
        data=PageResponse.create(
            items=[AdminVerificationRecordResponse.model_validate(r) for r in records],
            total=total,
            page=page,
            page_size=page_size,
        )
    )


@router.post(
    "/verification-records/{record_id}/run",
    response_model=Response[AdminVerificationRecordResponse],
)
async def run_verification(
    record_id: uuid.UUID,
    admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_db),
):
    service = AdminService(session)
    record = await service.run_verification(record_id, admin.id)
    return Response(data=AdminVerificationRecordResponse.model_validate(record))


@router.get("/users", response_model=Response[PageResponse[AdminUserResponse]])
async def list_users(
    page: int = 1,
    page_size: int = 20,
    keyword: str | None = None,
    role: str | None = None,
    is_active: bool | None = None,
    admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_db),
):
    service = AdminService(session)
    users, total = await service.get_users(page, page_size, keyword, role, is_active)
    return Response(
        data=PageResponse.create(
            items=[AdminUserResponse(**item) for item in users],
            total=total,
            page=page,
            page_size=page_size,
        )
    )


@router.get("/users/{user_id}", response_model=Response[AdminUserResponse])
async def get_user_detail(
    user_id: uuid.UUID,
    admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_db),
):
    service = AdminService(session)
    data = await service.get_user_detail(user_id)
    return Response(data=AdminUserResponse(**data))


@router.post("/users/{user_id}/set-active", response_model=Response[AdminUserResponse])
async def set_user_active(
    user_id: uuid.UUID,
    data: AdminUserSetActiveRequest,
    admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_db),
):
    service = AdminService(session)
    user = await service.set_user_active(user_id, data, admin.id)
    return Response(data=AdminUserResponse(**user))
