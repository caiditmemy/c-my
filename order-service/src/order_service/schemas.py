from datetime import datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator

from order_service.models import OrderStatus

CustomerName = Annotated[str, Field(min_length=1, max_length=255, description="Tên khách hàng", examples=["Nguyễn Văn A"])]
Phone = Annotated[str, Field(min_length=6, max_length=32, description="Số điện thoại", examples=["0901234567"])]


class _Stripped(BaseModel):
    @field_validator("customer_name", "customer_phone", "address", "note", mode="before", check_fields=False)
    @classmethod
    def strip(cls, value):
        if isinstance(value, str):
            return value.strip()
        return value


class OrderItemIn(BaseModel):
    product_id: int = Field(ge=1, description="Id sản phẩm bên product-service")
    quantity: int = Field(ge=1, le=1_000_000, description="Số lượng (>= 1)")


class OrderCreate(_Stripped):
    customer_name: CustomerName
    customer_phone: Phone
    address: str | None = Field(default=None, max_length=500, description="Địa chỉ giao hàng")
    note: str | None = Field(default=None, max_length=2000, description="Ghi chú")
    items: list[OrderItemIn] = Field(min_length=1, max_length=100, description="Các sản phẩm (cùng sản phẩm sẽ được gộp số lượng)")


class OrderUpdate(_Stripped):
    """Chỉ cập nhật thông tin khách; sản phẩm không đổi được."""

    customer_name: CustomerName
    customer_phone: Phone
    address: str | None = Field(default=None, max_length=500)
    note: str | None = Field(default=None, max_length=2000)


class StatusChange(BaseModel):
    status: OrderStatus = Field(description="Trạng thái mới", examples=["CONFIRMED"])


class OrderItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    product_id: int
    product_name: str
    unit_price: Decimal
    quantity: int
    line_total: Decimal


class OrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    customer_name: str
    customer_phone: str
    address: str | None
    note: str | None
    status: OrderStatus
    total_amount: Decimal
    created_at: datetime
    updated_at: datetime
    items: list[OrderItemOut]


class OrderPage(BaseModel):
    items: list[OrderOut]
    total: int
    page: int
    size: int


class StockCheckItemIn(BaseModel):
    items: list[OrderItemIn] = Field(min_length=1, max_length=100)


class StockLine(BaseModel):
    product_id: int
    product_name: str | None
    requested: int
    available: int
    exists: bool
    enough: bool


class StockPreview(BaseModel):
    all_enough: bool
    items: list[StockLine]
