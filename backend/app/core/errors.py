from __future__ import annotations

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class AppError(Exception):
    def __init__(self, status_code: int, code: str, message: str) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        super().__init__(message)


def error_payload(code: str, message: str) -> dict[str, dict[str, str]]:
    return {"error": {"code": code, "message": message}}


async def app_error_handler(_request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=error_payload(exc.code, exc.message),
        headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
    )


async def validation_error_handler(_request: Request, _exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=400,
        content=error_payload("INVALID_REQUEST", "请求参数不正确。"),
        headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
    )


def invalid_uid_error() -> AppError:
    return AppError(400, "INVALID_UID", "UID 格式错误。")


def session_expired_error() -> AppError:
    return AppError(401, "SESSION_EXPIRED", "邮箱连接已过期，请重新连接。")
