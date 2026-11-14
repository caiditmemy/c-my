import logging
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from order_service.db import get_db
from order_service.errors import ApiError
from order_service.models import TRANSITIONS, Order, OrderItem, OrderStatus
from order_service.product_client import ProductClient, get_product_client
from order_service.schemas import (
    OrderCreate,
    OrderItemIn,
    OrderOut,
    OrderPage,
    OrderUpdate,
    StatusChange,
    StockCheckItemIn,
    StockLine,
    StockPreview,
)

log = logging.getLogger(__name__)

router = APIRouter(prefix="/orders", tags=["Đơn hàng"])

Db = Annotated[Session, Depends(get_db)]
Products = Annotated[ProductClient, Depends(get_product_client)]

LABELS = {
    OrderStatus.PENDING: "Chờ xác nhận",
    OrderStatus.CONFIRMED: "Đã xác nhận",
    OrderStatus.SHIPPING: "Đang giao",
    OrderStatus.DELIVERED: "Đã giao",
    OrderStatus.CANCELLED: "Đã hủy",
}


def _get_or_404(db: Session, order_id: int) -> Order:
    order = db.get(Order, order_id)
    if order is None:
        raise ApiError(404, f"Không tìm thấy đơn hàng có id {order_id}")
    return order


def _merge(items: list[OrderItemIn]) -> list[dict]:
    """Gộp các dòng cùng sản phẩm, giữ thứ tự xuất hiện."""
    merged: dict[int, int] = {}
    for item in items:
        merged[item.product_id] = merged.get(item.product_id, 0) + item.quantity
    return [{"product_id": pid, "quantity": qty} for pid, qty in merged.items()]


def _stock_items(order: Order) -> list[dict]:
    return [{"product_id": i.product_id, "quantity": i.quantity} for i in order.items]


def _preview(products: ProductClient, items: list[dict]) -> StockPreview:
    names = {}
    for item in items:
        product = products.get_product(item["product_id"])
        names[item["product_id"]] = product["name"] if product else None
    check = products.check_stock(items)
    lines = [
        StockLine(
            product_id=line["product_id"],
            product_name=names.get(line["product_id"]),
            requested=line["requested"],
            available=line["available"],
            exists=line["exists"],
            enough=line["enough"],
        )
        for line in check["items"]
    ]
    return StockPreview(all_enough=all(line.enough for line in lines), items=lines)


def _shortage_message(lines: list[StockLine]) -> str:
    parts = [
        f"{line.product_name or 'Sản phẩm #' + str(line.product_id)} (cần {line.requested}, còn {line.available})"
        for line in lines
        if not line.enough
    ]
    return "Không đủ hàng trong kho: " + "; ".join(parts)


@router.post("", response_model=OrderOut, status_code=201, summary="Tạo đơn hàng (kiểm tra và trừ tồn kho)")
def create_order(body: OrderCreate, db: Db, products: Products) -> Order:
    """Gọi product-service: lấy thông tin sản phẩm → kiểm tra tồn kho → trừ kho.
    Lưu đơn thất bại sau khi đã trừ kho thì hoàn kho lại."""
    wanted = _merge(body.items)
    details = {}
    for item in wanted:
        product = products.get_product(item["product_id"])
        if product is None:
            raise ApiError(404, f"Không tìm thấy sản phẩm có id {item['product_id']}")
        details[item["product_id"]] = product

    check = products.check_stock(wanted)
    if not check["all_enough"]:
        lines = [
            StockLine(
                product_id=line["product_id"],
                product_name=details[line["product_id"]]["name"],
                requested=line["requested"],
                available=line["available"],
                exists=line["exists"],
                enough=line["enough"],
            )
            for line in check["items"]
        ]
        raise ApiError(409, _shortage_message(lines))

    products.reserve(wanted)  # có thể vẫn 409 nếu người khác vừa mua mất hàng
    try:
        order = Order(
            customer_name=body.customer_name,
            customer_phone=body.customer_phone,
            address=body.address,
            note=body.note,
            status=OrderStatus.PENDING.value,
            total_amount=Decimal(0),
        )
        for item in wanted:
            product = details[item["product_id"]]
            unit_price = Decimal(str(product["price"]))
            line_total = unit_price * item["quantity"]
            order.items.append(
                OrderItem(
                    product_id=item["product_id"],
                    product_name=product["name"],
                    unit_price=unit_price,
                    quantity=item["quantity"],
                    line_total=line_total,
                )
            )
            order.total_amount += line_total
        db.add(order)
        db.commit()
    except Exception:
        db.rollback()
        log.exception("Lưu đơn hàng thất bại, hoàn lại tồn kho")
        try:
            products.release(wanted)
        except ApiError:
            log.error("Không hoàn được tồn kho cho %s, cần xử lý thủ công", wanted)
        raise
    db.refresh(order)
    return order


@router.post("/check-stock", response_model=StockPreview, summary="Xem trước tồn kho cho danh sách sản phẩm (không trừ kho)")
def check_stock_preview(body: StockCheckItemIn, products: Products) -> StockPreview:
    return _preview(products, _merge(body.items))


@router.get("", response_model=OrderPage, summary="Danh sách đơn hàng (lọc theo trạng thái, phân trang)")
def list_orders(
    db: Db,
    status: Annotated[OrderStatus | None, Query(description="Lọc theo trạng thái")] = None,
    page: Annotated[int, Query(ge=1, description="Trang (từ 1)")] = 1,
    size: Annotated[int, Query(ge=1, le=200, description="Số dòng mỗi trang")] = 20,
) -> OrderPage:
    query = select(Order)
    if status is not None:
        query = query.where(Order.status == status.value)
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    items = db.scalars(query.order_by(Order.id.desc()).offset((page - 1) * size).limit(size)).all()
    return OrderPage(items=items, total=total, page=page, size=size)


@router.get("/{order_id}", response_model=OrderOut, summary="Xem một đơn hàng")
def get_order(order_id: int, db: Db) -> Order:
    return _get_or_404(db, order_id)


@router.get("/{order_id}/check-stock", response_model=StockPreview, summary="Tồn kho hiện tại so với các dòng của đơn")
def check_order_stock(order_id: int, db: Db, products: Products) -> StockPreview:
    return _preview(products, _stock_items(_get_or_404(db, order_id)))


@router.put("/{order_id}", response_model=OrderOut, summary="Cập nhật thông tin khách hàng (chỉ khi đơn đang chờ xác nhận)")
def update_order(order_id: int, body: OrderUpdate, db: Db) -> Order:
    order = _get_or_404(db, order_id)
    if order.status != OrderStatus.PENDING.value:
        raise ApiError(409, f"Chỉ sửa được đơn đang ở trạng thái 'Chờ xác nhận' (hiện tại: {LABELS[OrderStatus(order.status)]})")
    for field, value in body.model_dump().items():
        setattr(order, field, value)
    db.commit()
    db.refresh(order)
    return order


@router.patch("/{order_id}/status", response_model=OrderOut, summary="Cập nhật trạng thái đơn hàng")
def change_status(order_id: int, body: StatusChange, db: Db, products: Products) -> Order:
    """PENDING → CONFIRMED → SHIPPING → DELIVERED; PENDING/CONFIRMED → CANCELLED (hoàn tồn kho)."""
    order = _get_or_404(db, order_id)
    current = OrderStatus(order.status)
    target = body.status
    if target not in TRANSITIONS[current]:
        allowed = ", ".join(s.value for s in sorted(TRANSITIONS[current])) or "không có"
        raise ApiError(409, f"Không thể chuyển đơn từ '{current.value}' sang '{target.value}' (được phép: {allowed})")
    if target == OrderStatus.CANCELLED:
        products.release(_stock_items(order))  # lỗi (503) thì giữ nguyên trạng thái, thử lại được
    order.status = target.value
    db.commit()
    db.refresh(order)
    return order


@router.delete("/{order_id}", status_code=204, summary="Xóa đơn hàng (chỉ khi chờ xác nhận hoặc đã hủy)")
def delete_order(order_id: int, db: Db, products: Products) -> Response:
    order = _get_or_404(db, order_id)
    status = OrderStatus(order.status)
    if status not in (OrderStatus.PENDING, OrderStatus.CANCELLED):
        raise ApiError(409, f"Chỉ xóa được đơn 'Chờ xác nhận' hoặc 'Đã hủy' (hiện tại: {LABELS[status]})")
    if status == OrderStatus.PENDING:
        products.release(_stock_items(order))
    db.delete(order)
    db.commit()
    return Response(status_code=204)
