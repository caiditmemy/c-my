from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from product_service.db import get_db
from product_service.errors import ApiError
from product_service.models import Product
from product_service.schemas import (
    ProductCreate,
    ProductOut,
    ProductPage,
    ProductPatch,
    ProductUpdate,
    StockChangeOut,
    StockCheckLine,
    StockCheckOut,
    StockOut,
    StockRequest,
)

router = APIRouter(prefix="/products", tags=["Sản phẩm"])
stock_router = APIRouter(prefix="/products", tags=["Tồn kho (cho order-service)"])

Db = Annotated[Session, Depends(get_db)]


def _get_or_404(db: Session, product_id: int) -> Product:
    product = db.get(Product, product_id)
    if product is None:
        raise ApiError(404, f"Không tìm thấy sản phẩm có id {product_id}")
    return product


def _commit_unique_sku(db: Session, sku: str) -> None:
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ApiError(409, f"Mã sản phẩm '{sku}' đã tồn tại") from None


@router.post("", response_model=ProductOut, status_code=201, summary="Tạo sản phẩm")
def create_product(body: ProductCreate, db: Db) -> Product:
    product = Product(**body.model_dump())
    db.add(product)
    _commit_unique_sku(db, body.sku)
    db.refresh(product)
    return product


@router.get("", response_model=ProductPage, summary="Danh sách sản phẩm (tìm kiếm, phân trang)")
def list_products(
    db: Db,
    q: Annotated[str | None, Query(description="Tìm theo tên hoặc mã sản phẩm")] = None,
    page: Annotated[int, Query(ge=1, description="Trang (từ 1)")] = 1,
    size: Annotated[int, Query(ge=1, le=200, description="Số dòng mỗi trang")] = 20,
) -> ProductPage:
    query = select(Product)
    if q and q.strip():
        like = f"%{q.strip().replace('%', r'\%').replace('_', r'\_')}%"
        query = query.where(or_(Product.name.ilike(like, escape="\\"), Product.sku.ilike(like, escape="\\")))
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    items = db.scalars(query.order_by(Product.id).offset((page - 1) * size).limit(size)).all()
    return ProductPage(items=items, total=total, page=page, size=size)


# --- Tồn kho: đặt trước {product_id} để "stock" không bị hiểu là id ---


@stock_router.post("/stock/check", response_model=StockCheckOut, summary="Kiểm tra đủ hàng (không trừ kho)")
def check_stock(body: StockRequest, db: Db) -> StockCheckOut:
    ids = [item.product_id for item in body.items]
    products = {p.id: p for p in db.scalars(select(Product).where(Product.id.in_(ids)))}
    lines = []
    for item in body.items:
        product = products.get(item.product_id)
        available = product.quantity if product else 0
        lines.append(
            StockCheckLine(
                product_id=item.product_id,
                requested=item.quantity,
                available=available,
                exists=product is not None,
                enough=product is not None and available >= item.quantity,
            )
        )
    return StockCheckOut(all_enough=all(line.enough for line in lines), items=lines)


@stock_router.post("/stock/reserve", response_model=StockChangeOut, summary="Trừ kho tất cả sản phẩm hoặc không trừ gì")
def reserve_stock(body: StockRequest, db: Db) -> StockChangeOut:
    """Khóa các dòng theo thứ tự id (tránh deadlock), kiểm tra đủ hàng cho mọi sản phẩm rồi mới trừ.
    Thiếu một sản phẩm là 409 và không sản phẩm nào bị trừ."""
    wanted = {item.product_id: item.quantity for item in body.items}
    try:
        products = {
            p.id: p for p in db.scalars(select(Product).where(Product.id.in_(wanted)).order_by(Product.id).with_for_update())
        }
        missing = sorted(set(wanted) - set(products))
        if missing:
            raise ApiError(404, "Không tìm thấy sản phẩm có id: " + ", ".join(map(str, missing)))
        short = [
            f"{p.name} (còn {p.quantity}, cần {wanted[p.id]})" for p in products.values() if p.quantity < wanted[p.id]
        ]
        if short:
            raise ApiError(409, "Không đủ hàng trong kho: " + "; ".join(short))
        for pid, product in products.items():
            product.quantity -= wanted[pid]
        db.commit()
    except Exception:
        db.rollback()
        raise
    return StockChangeOut(items=[_stock(p) for p in products.values()])


@stock_router.post("/stock/release", response_model=StockChangeOut, summary="Hoàn lại tồn kho (hủy đơn)")
def release_stock(body: StockRequest, db: Db) -> StockChangeOut:
    wanted = {item.product_id: item.quantity for item in body.items}
    try:
        products = {
            p.id: p for p in db.scalars(select(Product).where(Product.id.in_(wanted)).order_by(Product.id).with_for_update())
        }
        # Sản phẩm đã bị xóa thì bỏ qua: không còn gì để hoàn lại
        for pid, product in products.items():
            product.quantity += wanted[pid]
        db.commit()
    except Exception:
        db.rollback()
        raise
    return StockChangeOut(items=[_stock(p) for p in products.values()])


def _stock(product: Product) -> StockOut:
    return StockOut(product_id=product.id, sku=product.sku, name=product.name, quantity=product.quantity)


@stock_router.get("/{product_id}/stock", response_model=StockOut, summary="Xem tồn kho của một sản phẩm")
def get_stock(product_id: int, db: Db) -> StockOut:
    return _stock(_get_or_404(db, product_id))


@router.get("/{product_id}", response_model=ProductOut, summary="Xem một sản phẩm")
def get_product(product_id: int, db: Db) -> Product:
    return _get_or_404(db, product_id)


@router.put("/{product_id}", response_model=ProductOut, summary="Cập nhật toàn bộ sản phẩm")
def replace_product(product_id: int, body: ProductUpdate, db: Db) -> Product:
    product = _get_or_404(db, product_id)
    for field, value in body.model_dump().items():
        setattr(product, field, value)
    _commit_unique_sku(db, body.sku)
    db.refresh(product)
    return product


@router.patch("/{product_id}", response_model=ProductOut, summary="Cập nhật một phần sản phẩm")
def patch_product(product_id: int, body: ProductPatch, db: Db) -> Product:
    product = _get_or_404(db, product_id)
    data = body.model_dump(exclude_unset=True)
    for field in ("sku", "name", "price", "quantity"):
        if field in data and data[field] is None:
            raise ApiError(400, f"Dữ liệu không hợp lệ - {field}: không được để trống")
    for field, value in data.items():
        setattr(product, field, value)
    _commit_unique_sku(db, data.get("sku", product.sku))
    db.refresh(product)
    return product


@router.delete("/{product_id}", status_code=204, summary="Xóa sản phẩm")
def delete_product(product_id: int, db: Db) -> Response:
    db.delete(_get_or_404(db, product_id))
    db.commit()
    return Response(status_code=204)
