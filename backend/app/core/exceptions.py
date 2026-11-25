from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse


class ErrorCode:
    SYSTEM_ERROR = 1000
    PARAM_ERROR = 2000
    AUTH_ERROR = 3000
    BUSINESS_ERROR = 4000
    NOT_FOUND = 5000


class APIException(HTTPException):
    def __init__(
        self,
        code: int,
        message: str,
        status_code: int = 400,
        data: Any = None,
    ):
        self.code = code
        self.message = message
        self.data = data
        super().__init__(
            status_code=status_code, detail={"code": code, "message": message, "data": data}
        )


class SystemError(APIException):
    def __init__(self, message: str = "系统错误", data: Any = None):
        super().__init__(ErrorCode.SYSTEM_ERROR, message, 500, data)


class ParamError(APIException):
    def __init__(self, message: str = "参数错误", data: Any = None):
        super().__init__(ErrorCode.PARAM_ERROR, message, 400, data)


class AuthError(APIException):
    def __init__(self, message: str = "认证失败", data: Any = None):
        super().__init__(ErrorCode.AUTH_ERROR, message, 401, data)


class BusinessError(APIException):
    def __init__(self, message: str = "业务逻辑错误", data: Any = None):
        super().__init__(ErrorCode.BUSINESS_ERROR, message, 400, data)


class NotFoundError(APIException):
    def __init__(self, message: str = "资源不存在", data: Any = None):
        super().__init__(ErrorCode.NOT_FOUND, message, 404, data)


async def api_exception_handler(_request: Request, exc: APIException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "code": exc.code,
            "message": exc.message,
            "data": exc.data,
            "timestamp": datetime.now(UTC).isoformat(),
        },
    )
