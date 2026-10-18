from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from decimal import Decimal

class ProductBase(BaseModel):
    name: str = Field(..., max_length=255, example="Bàn phím cơ AKKO 3087")
    description: Optional[str] = Field(None, example="Switch V3 Cream Yellow, kết nối Type-C")
    price: Decimal = Field(..., gt=0, max_digits=10, decimal_places=2, example=1250000.00)
    quantity: int = Field(..., ge=0, example=25)

class ProductCreate(ProductBase):
    pass

class ProductUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    price: Optional[Decimal] = Field(None, gt=0, max_digits=10, decimal_places=2)
    quantity: Optional[int] = Field(None, ge=0)

class ProductResponse(ProductBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True