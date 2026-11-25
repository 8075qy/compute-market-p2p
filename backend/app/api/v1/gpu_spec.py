from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.common import Response
from app.schemas.gpu_spec import GpuSpecResponse
from app.services.gpu_spec import GpuSpecService

router = APIRouter(prefix="/gpu-specs", tags=["GPU 规格库"])


@router.get("", response_model=Response[list[GpuSpecResponse]])
async def list_gpu_specs(session: AsyncSession = Depends(get_db)):
    service = GpuSpecService(session)
    specs = await service.list_specs()
    return Response(data=[GpuSpecResponse.model_validate(s) for s in specs])


@router.get("/match", response_model=Response[GpuSpecResponse | None])
async def match_gpu_spec(
    model: str = Query(..., min_length=1, max_length=64, description="GPU 型号"),
    session: AsyncSession = Depends(get_db),
):
    service = GpuSpecService(session)
    spec = await service.match(model)
    return Response(data=GpuSpecResponse.model_validate(spec) if spec else None)
