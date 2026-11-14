from decimal import Decimal
from unittest import mock

import pytest
from sqlalchemy import func, select

from order_service.models import Order
from tests.conftest import CUSTOMER


def test_create_order_success(client, products):
    response = client.post(
        "/orders", json={**CUSTOMER, "items": [{"product_id": 1, "quantity": 2}, {"product_id": 2, "quantity": 1}]}
    )
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "PENDING"
    assert Decimal(body["total_amount"]) == Decimal("22000.50")
    assert [(i["product_id"], i["product_name"], i["quantity"]) for i in body["items"]] == [(1, "Bút bi", 2), (2, "Vở kẻ ngang", 1)]
    assert Decimal(body["items"][0]["line_total"]) == 10000
    assert products.stock(1) == 8 and products.stock(2) == 2
    assert client.get(f"/orders/{body['id']}").json()["id"] == body["id"]


def test_duplicate_lines_are_merged(client, products):
    response = client.post("/orders", json={**CUSTOMER, "items": [{"product_id": 1, "quantity": 2}, {"product_id": 1, "quantity": 3}]})
    assert response.status_code == 201
    assert len(response.json()["items"]) == 1 and response.json()["items"][0]["quantity"] == 5
    assert products.stock(1) == 5


def test_price_snapshot_is_kept(client, products, make_order):
    order = make_order()
    products.products[1]["price"] = "99999"
    assert Decimal(client.get(f"/orders/{order['id']}").json()["items"][0]["unit_price"]) == 5000


def test_insufficient_stock_409_lists_items_and_reserves_nothing(client, products):
    response = client.post(
        "/orders", json={**CUSTOMER, "items": [{"product_id": 1, "quantity": 2}, {"product_id": 2, "quantity": 5}]}
    )
    assert response.status_code == 409
    message = response.json()["message"]
    assert "Không đủ hàng" in message and "Vở kẻ ngang" in message and "cần 5" in message and "còn 3" in message
    assert "Bút bi" not in message
    assert products.stock(1) == 10 and products.stock(2) == 3
    assert client.get("/orders").json()["total"] == 0


def test_reserve_race_409_creates_no_order(client, products):
    """check_stock báo đủ nhưng lúc trừ kho thì người khác đã mua mất."""
    original = products.handler

    def racing(request):
        if request.url.path == "/products/stock/reserve":
            products.products[1]["quantity"] = 0
        return original(request)

    from order_service.main import app
    from order_service.product_client import ProductClient, get_product_client
    import httpx

    app.dependency_overrides[get_product_client] = lambda: ProductClient("http://p", transport=httpx.MockTransport(racing))
    response = client.post("/orders", json={**CUSTOMER, "items": [{"product_id": 1, "quantity": 2}]})
    assert response.status_code == 409
    assert client.get("/orders").json()["total"] == 0


def test_product_missing_404(client, products):
    response = client.post("/orders", json={**CUSTOMER, "items": [{"product_id": 1, "quantity": 1}, {"product_id": 77, "quantity": 1}]})
    assert response.status_code == 404
    assert "77" in response.json()["message"]
    assert products.stock(1) == 10


def test_product_service_down_503(client, products):
    products.down = True
    response = client.post("/orders", json={**CUSTOMER, "items": [{"product_id": 1, "quantity": 1}]})
    assert response.status_code == 503
    assert "product-service" in response.json()["message"]
    assert set(response.json()) == {"status", "error", "message", "path"}


def test_failed_save_releases_stock(client, products):
    with mock.patch("sqlalchemy.orm.Session.commit", side_effect=RuntimeError("db down")):
        with pytest.raises(RuntimeError):
            client.post("/orders", json={**CUSTOMER, "items": [{"product_id": 1, "quantity": 4}]})
    assert products.stock(1) == 10
    assert ("POST", "/products/stock/release") in products.calls


def test_create_validation(client):
    bad = [
        {**CUSTOMER, "items": []},
        {**CUSTOMER, "items": [{"product_id": 1, "quantity": 0}]},
        {**CUSTOMER, "items": [{"product_id": 0, "quantity": 1}]},
        {"customer_phone": "0901234567", "items": [{"product_id": 1, "quantity": 1}]},
        {**CUSTOMER, "customer_phone": "1", "items": [{"product_id": 1, "quantity": 1}]},
        {**CUSTOMER, "customer_name": "  ", "items": [{"product_id": 1, "quantity": 1}]},
    ]
    for body in bad:
        response = client.post("/orders", json=body)
        assert response.status_code == 400, body
        assert response.json()["message"].startswith("Dữ liệu không hợp lệ")


def test_list_filter_paging(client, make_order):
    a = make_order()
    b = make_order()
    make_order()
    client.patch(f"/orders/{b['id']}/status", json={"status": "CONFIRMED"})
    page = client.get("/orders", params={"size": 2}).json()
    assert page["total"] == 3 and len(page["items"]) == 2
    assert page["items"][0]["id"] > page["items"][1]["id"]
    confirmed = client.get("/orders", params={"status": "CONFIRMED"}).json()
    assert [o["id"] for o in confirmed["items"]] == [b["id"]]
    assert client.get("/orders", params={"status": "PENDING"}).json()["total"] == 2
    assert client.get("/orders", params={"status": "BOGUS"}).status_code == 400
    assert a["id"]


def test_get_missing_404(client):
    response = client.get("/orders/123")
    assert response.status_code == 404 and "123" in response.json()["message"]


def test_update_customer_only_while_pending(client, make_order):
    order = make_order()
    url = f"/orders/{order['id']}"
    response = client.put(url, json={"customer_name": "Trần B", "customer_phone": "0987654321", "address": "Hà Nội", "note": "Giao giờ hành chính"})
    assert response.status_code == 200
    assert response.json()["customer_name"] == "Trần B" and response.json()["items"][0]["quantity"] == 2
    client.patch(f"{url}/status", json={"status": "CONFIRMED"})
    again = client.put(url, json={"customer_name": "X", "customer_phone": "0987654321"})
    assert again.status_code == 409
    assert client.put("/orders/999", json={"customer_name": "X", "customer_phone": "0987654321"}).status_code == 404


def test_status_happy_path(client, make_order, products):
    order = make_order()
    url = f"/orders/{order['id']}/status"
    for status in ("CONFIRMED", "SHIPPING", "DELIVERED"):
        response = client.patch(url, json={"status": status})
        assert response.status_code == 200 and response.json()["status"] == status
    assert products.stock(1) == 8  # giao hàng thì không hoàn kho


@pytest.mark.parametrize(
    ("path", "target"),
    [
        (["CONFIRMED"], "PENDING"),
        ([], "SHIPPING"),
        ([], "DELIVERED"),
        ([], "PENDING"),
        (["CONFIRMED", "SHIPPING"], "CANCELLED"),
        (["CONFIRMED", "SHIPPING", "DELIVERED"], "CANCELLED"),
        (["CANCELLED"], "CONFIRMED"),
        (["CANCELLED"], "CANCELLED"),
        (["CONFIRMED"], "DELIVERED"),
    ],
)
def test_invalid_transitions_409(client, make_order, products, path, target):
    order = make_order()
    url = f"/orders/{order['id']}/status"
    for status in path:
        assert client.patch(url, json={"status": status}).status_code == 200
    stock_before = products.stock(1)
    response = client.patch(url, json={"status": target})
    assert response.status_code == 409
    assert "Không thể chuyển" in response.json()["message"]
    assert products.stock(1) == stock_before


def test_unknown_status_is_400(client, make_order):
    order = make_order()
    assert client.patch(f"/orders/{order['id']}/status", json={"status": "FLYING"}).status_code == 400
    assert client.patch("/orders/999/status", json={"status": "CONFIRMED"}).status_code == 404


@pytest.mark.parametrize("path", [[], ["CONFIRMED"]])
def test_cancel_releases_stock(client, make_order, products, path):
    order = make_order([{"product_id": 1, "quantity": 4}, {"product_id": 2, "quantity": 2}])
    url = f"/orders/{order['id']}/status"
    for status in path:
        client.patch(url, json={"status": status})
    assert products.stock(1) == 6 and products.stock(2) == 1
    response = client.patch(url, json={"status": "CANCELLED"})
    assert response.status_code == 200 and response.json()["status"] == "CANCELLED"
    assert products.stock(1) == 10 and products.stock(2) == 3
    # hủy hai lần không hoàn kho hai lần
    assert client.patch(url, json={"status": "CANCELLED"}).status_code == 409
    assert products.stock(1) == 10


def test_cancel_when_product_service_down_keeps_status(client, make_order, products):
    order = make_order()
    products.down = True
    response = client.patch(f"/orders/{order['id']}/status", json={"status": "CANCELLED"})
    assert response.status_code == 503
    products.down = False
    assert client.get(f"/orders/{order['id']}").json()["status"] == "PENDING"
    assert products.stock(1) == 8


def test_delete_pending_releases_stock(client, make_order, products):
    order = make_order()
    assert products.stock(1) == 8
    assert client.delete(f"/orders/{order['id']}").status_code == 204
    assert products.stock(1) == 10
    assert client.get(f"/orders/{order['id']}").status_code == 404
    assert client.delete(f"/orders/{order['id']}").status_code == 404


def test_delete_cancelled_does_not_release_twice(client, make_order, products, db_session):
    order = make_order()
    client.patch(f"/orders/{order['id']}/status", json={"status": "CANCELLED"})
    assert client.delete(f"/orders/{order['id']}").status_code == 204
    assert products.stock(1) == 10
    assert db_session.scalar(select(func.count()).select_from(Order)) == 0


@pytest.mark.parametrize("path", [["CONFIRMED"], ["CONFIRMED", "SHIPPING"], ["CONFIRMED", "SHIPPING", "DELIVERED"]])
def test_delete_rejected_after_confirmation(client, make_order, products, path):
    order = make_order()
    for status in path:
        client.patch(f"/orders/{order['id']}/status", json={"status": status})
    response = client.delete(f"/orders/{order['id']}")
    assert response.status_code == 409
    assert client.get(f"/orders/{order['id']}").status_code == 200
    assert products.stock(1) == 8


def test_check_stock_preview(client, products):
    response = client.post(
        "/orders/check-stock", json={"items": [{"product_id": 1, "quantity": 3}, {"product_id": 2, "quantity": 9}, {"product_id": 55, "quantity": 1}]}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["all_enough"] is False
    lines = {l["product_id"]: l for l in body["items"]}
    assert lines[1]["enough"] is True and lines[1]["product_name"] == "Bút bi"
    assert lines[2]["enough"] is False and lines[2]["available"] == 3
    assert lines[55]["exists"] is False and lines[55]["product_name"] is None
    assert products.stock(1) == 10  # không trừ kho


def test_order_check_stock(client, make_order, products):
    order = make_order([{"product_id": 2, "quantity": 3}])
    body = client.get(f"/orders/{order['id']}/check-stock").json()
    # đơn đã giữ hết 3 cái, nên tồn hiện tại là 0
    assert body["all_enough"] is False and body["items"][0]["available"] == 0
    assert client.get("/orders/999/check-stock").status_code == 404


def test_health_reports_product_service(client, products):
    body = client.get("/health").json()
    assert body["status"] == "UP" and body["db"] == "UP"
    assert body["product_service"] in ("UP", "DOWN")


def test_ui_is_served(client):
    response = client.get("/")
    assert response.status_code == 200 and "text/html" in response.headers["content-type"]
    assert "PRODUCT_API" in client.get("/config.js").text
