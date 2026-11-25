from fastapi import APIRouter, Depends

from app.api.v1 import (
    account,
    admin,
    auth,
    demand,
    execution,
    gpu_spec,
    marketplace,
    model,
    notifications,
    reserve,
    settlements,
    supplier,
    upload,
)
from app.core.deps import require_setup

api_router = APIRouter(dependencies=[Depends(require_setup)])

api_router.include_router(auth.router)
api_router.include_router(gpu_spec.router)
api_router.include_router(supplier.router)
api_router.include_router(execution.router)
api_router.include_router(demand.router)
api_router.include_router(upload.demand_router)
api_router.include_router(upload.supplier_router)
api_router.include_router(marketplace.router)
api_router.include_router(model.demand_router)
api_router.include_router(model.admin_router)
api_router.include_router(settlements.router)
api_router.include_router(account.router)
api_router.include_router(reserve.router)
api_router.include_router(admin.router)
api_router.include_router(notifications.router)
