"""Kiểm thử toàn luồng qua HTTP trên hai service đang chạy. Thoát mã khác 0 nếu có bước sai.

    python3 scripts/smoke.py [--product-url http://127.0.0.1:8091] [--order-url http://127.0.0.1:8092]
"""

import argparse
import os
import sys
import time
import uuid

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _http import call  # noqa: E402

failures = 0


def check(name: str, condition: bool, detail: object = "") -> None:
    global failures
    print(("  OK   " if condition else "  FAIL ") + name + ("" if condition else f"  -> {detail}"))
    if not condition:
        failures += 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--product-url", default=os.environ.get("PRODUCT_URL", "http://127.0.0.1:8091"))
    parser.add_argument("--order-url", default=os.environ.get("ORDER_URL", "http://127.0.0.1:8092"))
    args = parser.parse_args()
    p, o = args.product_url.rstrip("/"), args.order_url.rstrip("/")

    print("Health")
    for _ in range(30):
        try:
            if call("GET", p + "/health")[0] == 200 and call("GET", o + "/health")[0] == 200:
                break
        except OSError:
            pass
        time.sleep(1)
    status, body = call("GET", o + "/health")
    check("order-service UP, thấy product-service", status == 200 and body["product_service"] == "UP", body)

    tag = uuid.uuid4().hex[:8]
    print("Sản phẩm")
    status, a = call("POST", p + "/products", {"sku": f"SMK-A-{tag}", "name": f"Smoke A {tag}", "price": "10000", "quantity": 10})
    check("tạo sản phẩm A (tồn 10)", status == 201, a)
    status, b = call("POST", p + "/products", {"sku": f"SMK-B-{tag}", "name": f"Smoke B {tag}", "price": "2500.5", "quantity": 2})
    check("tạo sản phẩm B (tồn 2)", status == 201, b)
    status, body = call("POST", p + "/products", {"sku": f"SMK-A-{tag}", "name": "dup", "price": 1})
    check("trùng SKU -> 409", status == 409, body)
    status, body = call("GET", p + f"/products?q={tag}")
    check("tìm kiếm theo q", status == 200 and body["total"] == 2, body)

    def stock(product: dict) -> int:
        return call("GET", p + f"/products/{product['id']}/stock")[1]["quantity"]

    customer = {"customer_name": "Smoke Test", "customer_phone": "0900000000", "address": "Quy Nhơn"}
    print("Tạo đơn")
    status, order = call("POST", o + "/orders", {**customer, "items": [{"product_id": a["id"], "quantity": 3}, {"product_id": b["id"], "quantity": 1}]})
    check("tạo đơn -> 201 PENDING", status == 201 and order["status"] == "PENDING", order)
    check("tổng tiền = 3*10000 + 2500.5", status == 201 and float(order["total_amount"]) == 32500.5, order)
    check("tồn kho bị trừ (A=7, B=1)", stock(a) == 7 and stock(b) == 1, (stock(a), stock(b)))

    status, body = call("POST", o + "/orders", {**customer, "items": [{"product_id": a["id"], "quantity": 1}, {"product_id": b["id"], "quantity": 5}]})
    check("thiếu hàng -> 409 có thông báo tiếng Việt", status == 409 and "Không đủ hàng" in body["message"], body)
    check("409 không trừ kho (A=7, B=1)", stock(a) == 7 and stock(b) == 1, (stock(a), stock(b)))
    status, body = call("POST", o + "/orders", {**customer, "items": [{"product_id": 999999999, "quantity": 1}]})
    check("sản phẩm không tồn tại -> 404", status == 404, body)
    status, body = call("POST", o + "/orders/check-stock", {"items": [{"product_id": b["id"], "quantity": 5}]})
    check("xem trước tồn kho: không đủ", status == 200 and body["all_enough"] is False and stock(b) == 1, body)

    print("Luồng trạng thái")
    oid = order["id"]
    status, body = call("PATCH", o + f"/orders/{oid}/status", {"status": "DELIVERED"})
    check("PENDING -> DELIVERED bị 409", status == 409, body)
    status, body = call("PUT", o + f"/orders/{oid}", {**customer, "customer_name": "Smoke Test 2"})
    check("sửa thông tin khi PENDING", status == 200 and body["customer_name"] == "Smoke Test 2", body)
    for target in ("CONFIRMED", "SHIPPING", "DELIVERED"):
        status, body = call("PATCH", o + f"/orders/{oid}/status", {"status": target})
        check(f"-> {target}", status == 200 and body["status"] == target, body)
    status, body = call("PATCH", o + f"/orders/{oid}/status", {"status": "CANCELLED"})
    check("DELIVERED -> CANCELLED bị 409", status == 409, body)
    status, body = call("DELETE", o + f"/orders/{oid}")
    check("không xóa được đơn đã giao (409)", status == 409, body)

    print("Hủy đơn hoàn kho")
    status, order2 = call("POST", o + "/orders", {**customer, "items": [{"product_id": a["id"], "quantity": 7}]})
    check("đặt hết 7 sản phẩm A", status == 201 and stock(a) == 0, order2)
    status, body = call("POST", o + "/orders", {**customer, "items": [{"product_id": a["id"], "quantity": 1}]})
    check("A hết hàng -> 409", status == 409, body)
    status, body = call("PATCH", o + f"/orders/{order2['id']}/status", {"status": "CANCELLED"})
    check("hủy đơn -> CANCELLED", status == 200 and body["status"] == "CANCELLED", body)
    check("tồn kho A trở lại 7", stock(a) == 7, stock(a))

    print("Xóa")
    status, _ = call("DELETE", o + f"/orders/{order2['id']}")
    check("xóa đơn đã hủy -> 204", status == 204, status)
    status, order3 = call("POST", o + "/orders", {**customer, "items": [{"product_id": b["id"], "quantity": 1}]})
    check("đơn mới trừ B về 0", status == 201 and stock(b) == 0, order3)
    status, _ = call("DELETE", o + f"/orders/{order3['id']}")
    check("xóa đơn PENDING -> 204", status == 204, status)
    check("xóa đơn PENDING hoàn kho B=1", stock(b) == 1, stock(b))
    status, _ = call("GET", o + f"/orders/{order3['id']}")
    check("đơn đã xóa -> 404", status == 404, status)
    status, body = call("GET", o + "/orders?status=DELIVERED&size=5")
    check("lọc đơn theo trạng thái", status == 200 and all(x["status"] == "DELIVERED" for x in body["items"]) and any(x["id"] == oid for x in body["items"]), body)

    for product in (a, b):
        status, _ = call("DELETE", p + f"/products/{product['id']}")
        check(f"xóa sản phẩm #{product['id']}", status == 204, status)

    print()
    if failures:
        print(f"SMOKE THẤT BẠI: {failures} bước sai")
        return 1
    print("SMOKE THÀNH CÔNG")
    return 0


if __name__ == "__main__":
    sys.exit(main())
