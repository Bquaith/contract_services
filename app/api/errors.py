from typing import Any, cast

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette import status
from starlette.exceptions import HTTPException as StarletteHTTPException


class ApiError(Exception):
    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: dict[str, Any] | None = None,
    ):
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details or {}


def error_payload(code: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "error": {
            "code": code,
            "message": message,
            "details": details or {},
        }
    }


async def api_error_handler(_: Request, exc: ApiError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=error_payload(exc.code, exc.message, exc.details),
    )


async def request_validation_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=error_payload(
            code="request_validation_error",
            message="Request validation failed",
            details={"errors": exc.errors()},
        ),
    )


async def http_exception_handler(_: Request, exc: StarletteHTTPException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=error_payload(
            code="http_error",
            message=str(exc.detail),
            details={},
        ),
    )


async def unexpected_handler(_: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=error_payload(
            code="internal_error",
            message="Internal server error",
            details={"exception": exc.__class__.__name__},
        ),
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(ApiError, cast(Any, api_error_handler))
    app.add_exception_handler(RequestValidationError, cast(Any, request_validation_handler))
    app.add_exception_handler(StarletteHTTPException, cast(Any, http_exception_handler))
    app.add_exception_handler(Exception, cast(Any, unexpected_handler))
