from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from product_service.config import get_settings
from product_service.db import engine
from product_service.errors import register_error_handlers
from product_service.routers import products

app = FastAPI(
    title="Product Service - Quản lý sản phẩm",
    description="Dịch vụ độc lập (cổng 8091, CSDL `product_db`): CRUD sản phẩm và quản lý tồn kho. "
    "Order-service gọi các API `/products/stock/*` để kiểm tra, trừ và hoàn tồn kho.",
    version="0.1.0",
    openapi_tags=[
        {"name": "Sản phẩm", "description": "Tạo, xem, cập nhật, xóa sản phẩm"},
        {"name": "Tồn kho (cho order-service)", "description": "Kiểm tra / trừ / hoàn số lượng tồn kho"},
        {"name": "Hệ thống", "description": "Kiểm tra trạng thái"},
    ],
)
_origins = [o.strip() for o in get_settings().cors_origins.split(",") if o.strip()]
app.add_middleware(CORSMiddleware, allow_origins=_origins, allow_methods=["*"], allow_headers=["*"])
register_error_handlers(app)
app.include_router(products.router)
app.include_router(products.stock_router)


@app.get("/health", tags=["Hệ thống"], summary="Service và database còn chạy không")
def health() -> Any:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError:
        return JSONResponse(status_code=503, content={"status": "DOWN", "db": "DOWN"})
    return {"status": "UP", "db": "UP"}
