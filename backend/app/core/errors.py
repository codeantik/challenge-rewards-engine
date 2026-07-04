"""The error side of the response envelope (see CLAUDE.md).

Every non-2xx JSON body is:

    {"error": {"code": "...", "message": "...", "details": ..., "request_id": "..."}}

`AppError` is what domain/business logic should raise for expected failure
cases (not found, conflict, business-rule violation, ...). Validation errors,
generic HTTP errors, and truly unexpected exceptions are normalized to the
same shape by the handlers registered below — this is the single place
exceptions become responses, so no route needs its own try/except-to-JSON.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from fastapi import FastAPI, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.requests import Request

_CODE_BY_STATUS: dict[int, str] = {
    400: "BAD_REQUEST",
    401: "UNAUTHORIZED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    409: "CONFLICT",
    422: "VALIDATION_ERROR",
}


class AppError(Exception):
    """Raise this for expected domain failures; it maps to a stable error code."""

    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        details: Any = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details


def _request_id(request: Request) -> str:
    return str(getattr(request.state, "request_id", "unknown"))


def _sanitize_validation_errors(errors: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    """Pydantic v2 puts the raised exception itself under `ctx.error` for
    `model_validator` failures (e.g. `validate_challenge_config`'s
    `ValueError`) — that's not JSON-serializable, so `json.dumps` blows up
    turning a 422 into an unhandled 500. Swap it for its string form; that's
    the only non-serializable field pydantic ever puts in `.errors()`.
    """
    sanitized = []
    for err in errors:
        ctx = err.get("ctx")
        if isinstance(ctx, dict) and isinstance(ctx.get("error"), BaseException):
            err = {**err, "ctx": {**ctx, "error": str(ctx["error"])}}
        sanitized.append(err)
    return sanitized


def _error_body(code: str, message: str, request_id: str, details: Any = None) -> dict[str, Any]:
    return {
        "error": {
            "code": code,
            "message": message,
            "details": details,
            "request_id": request_id,
        }
    }


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        request_id = _request_id(request)
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_body(exc.code, exc.message, request_id, exc.details),
            headers={"X-Request-Id": request_id},
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        request_id = _request_id(request)
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content=_error_body(
                "VALIDATION_ERROR",
                "request validation failed",
                request_id,
                _sanitize_validation_errors(exc.errors()),
            ),
            headers={"X-Request-Id": request_id},
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_exception(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        request_id = _request_id(request)
        code = _CODE_BY_STATUS.get(exc.status_code, "HTTP_ERROR")
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_body(code, str(exc.detail), request_id),
            headers={"X-Request-Id": request_id},
        )

    @app.exception_handler(Exception)
    async def handle_unhandled_exception(request: Request, exc: Exception) -> JSONResponse:
        request_id = _request_id(request)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=_error_body("INTERNAL_ERROR", "an unexpected error occurred", request_id),
            headers={"X-Request-Id": request_id},
        )
