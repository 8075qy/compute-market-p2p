import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models import NodeStatus, TaskStatus, User
from app.schemas.common import PageResponse, Response
from app.schemas.node import (
    BenchmarkReportRequest,
    NodeCreate,
    NodeDetailResponse,
    NodeEarningsResponse,
    NodeExecutionResponse,
    NodeHeartbeatRequest,
    NodeHeartbeatResponse,
    NodeResponse,
    NodeUpdate,
)
from app.services.node import NodeService

router = APIRouter(prefix="/supplier/nodes", tags=["供给方·节点管理"])


@router.get("", response_model=Response[PageResponse[NodeResponse]])
async def list_nodes(
    page: int = 1,
    page_size: int = 20,
    status: NodeStatus | None = None,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    service = NodeService(session)
    nodes, total = await service.get_nodes(user.id, page, page_size, status)
    return Response(data=PageResponse.create(
        items=[NodeResponse.model_validate(n) for n in nodes],
        total=total, page=page, page_size=page_size
    ))


@router.post("", response_model=Response[NodeResponse])
async def create_node(
    data: NodeCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    service = NodeService(session)
    node = await service.create_node(user.id, data)
    return Response(data=NodeResponse.model_validate(node))


@router.get("/{node_id}", response_model=Response[NodeDetailResponse])
async def get_node(
    node_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    service = NodeService(session)
    detail = await service.get_node_detail(node_id, user.id)
    node_resp = NodeDetailResponse.model_validate(detail["node"])
    node_resp.today_tasks = detail["today_stats"]["tasks"]
    node_resp.today_points = detail["today_stats"]["points"]
    return Response(data=node_resp)


@router.put("/{node_id}", response_model=Response[NodeResponse])
async def update_node(
    node_id: uuid.UUID,
    data: NodeUpdate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    service = NodeService(session)
    node = await service.update_node(node_id, user.id, data)
    return Response(data=NodeResponse.model_validate(node))


@router.post("/{node_id}/benchmark", response_model=Response[NodeResponse])
async def report_benchmark(
    node_id: uuid.UUID,
    data: BenchmarkReportRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    service = NodeService(session)
    node = await service.report_benchmark(node_id, user.id, data)
    return Response(data=NodeResponse.model_validate(node))


@router.post("/{node_id}/online", response_model=Response[NodeResponse])
async def set_node_online(
    node_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    service = NodeService(session)
    node = await service.set_online(node_id, user.id)
    return Response(data=NodeResponse.model_validate(node))


@router.post("/{node_id}/offline", response_model=Response[NodeResponse])
async def set_node_offline(
    node_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    service = NodeService(session)
    node = await service.set_offline(node_id, user.id)
    return Response(data=NodeResponse.model_validate(node))


@router.delete("/{node_id}", response_model=Response[dict])
async def delete_node(
    node_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    service = NodeService(session)
    await service.delete_node(node_id, user.id)
    return Response(data={})


@router.post("/{node_id}/heartbeat", response_model=Response[NodeHeartbeatResponse])
async def node_heartbeat(
    node_id: uuid.UUID,
    data: NodeHeartbeatRequest,
    session: AsyncSession = Depends(get_db)
):
    # 节点客户端调用，使用节点专用 token 认证
    # 这里简化处理，实际应该验证节点 token
    service = NodeService(session)
    result = await service.heartbeat(node_id, data)
    return Response(data=NodeHeartbeatResponse(**result))


@router.get("/{node_id}/executions", response_model=Response[PageResponse[NodeExecutionResponse]])
async def list_node_executions(
    node_id: uuid.UUID,
    page: int = 1,
    page_size: int = 20,
    status: TaskStatus | None = None,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    service = NodeService(session)
    executions, total = await service.get_node_executions(node_id, user.id, page, page_size, status)
    return Response(data=PageResponse.create(
        items=[NodeExecutionResponse.model_validate(e) for e in executions],
        total=total, page=page, page_size=page_size
    ))


@router.get("/{node_id}/earnings", response_model=Response[NodeEarningsResponse])
async def get_node_earnings(
    node_id: uuid.UUID,
    period: str = "month",
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db)
):
    service = NodeService(session)
    earnings = await service.get_node_earnings(node_id, user.id, period)
    return Response(data=NodeEarningsResponse(**earnings))
