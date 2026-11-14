from datetime import datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator

Sku = Annotated[str, Field(min_length=1, max_length=64, description="Mã sản phẩm (duy nhất)", examples=["SP001"])]
Name = Annotated[str, Field(min_length=1, max_length=255, description="Tên sản phẩm", examples=["Bút bi Thiên Long"])]
Price = Annotated[Decimal, Field(ge=0, max_digits=14, decimal_places=2, description="Đơn giá (>= 0)", examples=["5000"])]
Stock = Annotated[int, Field(ge=0, le=1_000_000_000, description="Số lượng tồn kho (>= 0)", examples=[100])]


class _Stripped(BaseModel):
    @field_validator("sku", "name", mode="before", check_fields=False)
    @classmethod
    def strip(cls, value):
        return value.strip() if isinstance(value, str) else value


class ProductCreate(_Stripped):
    sku: Sku
    name: Name
    description: str | None = Field(default=None, max_length=5000, description="Mô tả")
    price: Price
    quantity: Stock = 0


class ProductUpdate(_Stripped):
    """PUT: gửi đầy đủ các trường. PATCH: chỉ gửi trường cần đổi."""

    sku: Sku
    name: Name
    description: str | None = Field(default=None, max_length=5000)
    price: Price
    quantity: Stock


class ProductPatch(_Stripped):
    sku: Sku | None = None
    name: Name | None = None
    description: str | None = Field(default=None, max_length=5000)
    price: Price | None = None
    quantity: Stock | None = None


class ProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    sku: str
    name: str
    description: str | None
    price: Decimal
    quantity: int
    created_at: datetime
    updated_at: datetime


class ProductPage(BaseModel):
    items: list[ProductOut]
    total: int = Field(description="Tổng số sản phẩm khớp điều kiện")
    page: int
    size: int


class StockOut(BaseModel):
    product_id: int
    sku: str
    name: str
    quantity: int = Field(description="Số lượng tồn kho hiện tại")


class StockItem(BaseModel):
    product_id: int = Field(ge=1)
    quantity: int = Field(ge=1, le=1_000_000, description="Số lượng cần (>= 1)")


class StockRequest(BaseModel):
    items: list[StockItem] = Field(min_length=1, max_length=200)

    @field_validator("items")
    @classmethod
    def unique_products(cls, items: list[StockItem]) -> list[StockItem]:
        ids = [item.product_id for item in items]
        if len(ids) != len(set(ids)):
            raise ValueError("Mỗi sản phẩm chỉ xuất hiện một lần trong danh sách")
        return items


class StockCheckLine(BaseModel):
    product_id: int
    requested: int
    available: int = Field(description="Tồn kho hiện tại (0 nếu sản phẩm không tồn tại)")
    exists: bool
    enough: bool


class StockCheckOut(BaseModel):
    all_enough: bool
    items: list[StockCheckLine]


class StockChangeOut(BaseModel):
    items: list[StockOut]
