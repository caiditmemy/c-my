"""Lỗi trả về cùng một dạng JSON: {"status", "error", "message", "path"}."""

import logging
from http import HTTPStatus

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

log = logging.getLogger(__name__)


class ApiError(Exception):
    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.message = message


def error_response(status: int, message: str, path: str) -> JSONResponse:
    body = {"status": status, "error": HTTPStatus(status).phrase, "message": message, "path": path}
    return JSONResponse(status_code=status, content=body)


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def handle_api_error(request: Request, exc: ApiError) -> JSONResponse:
        return error_response(exc.status, exc.message, request.url.path)

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        message = "Không tìm thấy đường dẫn" if exc.status_code == 404 and exc.detail == "Not Found" else str(exc.detail)
        return error_response(exc.status_code, message, request.url.path)

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        message = "Dữ liệu không hợp lệ"
        errors = exc.errors()
        if errors:
            field = ".".join(str(part) for part in errors[0].get("loc", ()) if part not in ("body", "query", "path"))
            text = str(errors[0].get("msg", message))
            message = f"Dữ liệu không hợp lệ - {field}: {text}" if field else f"Dữ liệu không hợp lệ - {text}"
        return error_response(400, message, request.url.path)

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        log.exception("Lỗi không mong muốn tại %s %s", request.method, request.url.path)
        return error_response(500, "Lỗi hệ thống", request.url.path)
