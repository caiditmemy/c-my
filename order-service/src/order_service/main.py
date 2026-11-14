from pathlib import Path
from typing import Any

from fastapi import FastAPI, Response
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from order_service.config import get_settings
from order_service.db import engine
from order_service.errors import register_error_handlers
from order_service.product_client import get_product_client
from order_service.routers import orders

STATIC = Path(__file__).parent / "static"

app = FastAPI(
    title="Order Service - Quản lý đơn hàng",
    description="Dịch vụ độc lập (cổng 8092, CSDL `order_db`): tạo đơn, xem, cập nhật trạng thái, hủy, xóa. "
    "Kiểm tra và trừ tồn kho bằng cách gọi HTTP sang product-service (cổng 8091). "
    "Giao diện web đơn giản ở trang chủ `/`.",
    version="0.1.0",
    openapi_tags=[
        {"name": "Đơn hàng", "description": "Tạo đơn, cập nhật trạng thái, kiểm tra tồn kho, xóa"},
        {"name": "Hệ thống", "description": "Kiểm tra trạng thái"},
    ],
)
register_error_handlers(app)
app.include_router(orders.router)
app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(STATIC / "index.html")


@app.get("/config.js", include_in_schema=False)
def config_js() -> Response:
    """Cho giao diện biết địa chỉ product-service mà trình duyệt gọi được."""
    url = get_settings().public_product_service_url.rstrip("/")
    return Response(f'window.PRODUCT_API = "{url}";\n', media_type="application/javascript")


@app.get("/health", tags=["Hệ thống"], summary="Service và database còn chạy không (kèm trạng thái product-service)")
def health() -> Any:
    # product-service chỉ được báo cáo: nó tắt thì order-service vẫn xem được đơn cũ
    product = "UP" if get_product_client().ping() else "DOWN"
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError:
        return JSONResponse(status_code=503, content={"status": "DOWN", "db": "DOWN", "product_service": product})
    return {"status": "UP", "db": "UP", "product_service": product}
