import threading

from sqlalchemy import select

from product_service.models import Product


def test_get_stock(client, make_product):
    product = make_product(quantity=12)
    response = client.get(f"/products/{product['id']}/stock")
    assert response.status_code == 200
    assert response.json()["quantity"] == 12
    assert client.get("/products/999/stock").status_code == 404


def test_check(client, make_product):
    a = make_product(quantity=5)
    b = make_product(quantity=1)
    response = client.post(
        "/products/stock/check",
        json={"items": [{"product_id": a["id"], "quantity": 5}, {"product_id": b["id"], "quantity": 2}, {"product_id": 999, "quantity": 1}]},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["all_enough"] is False
    lines = {line["product_id"]: line for line in body["items"]}
    assert lines[a["id"]]["enough"] is True
    assert lines[b["id"]] == {"product_id": b["id"], "requested": 2, "available": 1, "exists": True, "enough": False}
    assert lines[999]["exists"] is False and lines[999]["enough"] is False
    # check không trừ kho
    assert client.get(f"/products/{a['id']}/stock").json()["quantity"] == 5


def test_check_all_enough(client, make_product):
    a = make_product(quantity=5)
    body = client.post("/products/stock/check", json={"items": [{"product_id": a["id"], "quantity": 3}]}).json()
    assert body["all_enough"] is True


def test_reserve_success_and_release(client, make_product):
    a = make_product(quantity=10)
    b = make_product(quantity=4)
    items = [{"product_id": b["id"], "quantity": 4}, {"product_id": a["id"], "quantity": 3}]
    response = client.post("/products/stock/reserve", json={"items": items})
    assert response.status_code == 200
    assert {i["product_id"]: i["quantity"] for i in response.json()["items"]} == {a["id"]: 7, b["id"]: 0}
    assert client.get(f"/products/{a['id']}/stock").json()["quantity"] == 7
    released = client.post("/products/stock/release", json={"items": items})
    assert released.status_code == 200
    assert client.get(f"/products/{a['id']}/stock").json()["quantity"] == 10
    assert client.get(f"/products/{b['id']}/stock").json()["quantity"] == 4


def test_reserve_is_atomic_when_insufficient(client, make_product):
    a = make_product(quantity=10)
    b = make_product(quantity=1)
    response = client.post(
        "/products/stock/reserve",
        json={"items": [{"product_id": a["id"], "quantity": 5}, {"product_id": b["id"], "quantity": 2}]},
    )
    assert response.status_code == 409
    assert "Không đủ hàng" in response.json()["message"] and b["name"] in response.json()["message"]
    # sản phẩm đủ hàng cũng không bị trừ
    assert client.get(f"/products/{a['id']}/stock").json()["quantity"] == 10
    assert client.get(f"/products/{b['id']}/stock").json()["quantity"] == 1


def test_reserve_missing_product_is_404_and_nothing_changes(client, make_product):
    a = make_product(quantity=10)
    response = client.post(
        "/products/stock/reserve",
        json={"items": [{"product_id": a["id"], "quantity": 1}, {"product_id": 999, "quantity": 1}]},
    )
    assert response.status_code == 404
    assert client.get(f"/products/{a['id']}/stock").json()["quantity"] == 10


def test_reserve_exact_stock_to_zero(client, make_product):
    a = make_product(quantity=3)
    assert client.post("/products/stock/reserve", json={"items": [{"product_id": a["id"], "quantity": 3}]}).status_code == 200
    assert client.post("/products/stock/reserve", json={"items": [{"product_id": a["id"], "quantity": 1}]}).status_code == 409


def test_release_ignores_deleted_product(client, make_product):
    a = make_product(quantity=3)
    b = make_product(quantity=3)
    client.delete(f"/products/{b['id']}")
    response = client.post(
        "/products/stock/release",
        json={"items": [{"product_id": a["id"], "quantity": 2}, {"product_id": b["id"], "quantity": 2}]},
    )
    assert response.status_code == 200
    assert client.get(f"/products/{a['id']}/stock").json()["quantity"] == 5


def test_stock_request_validation(client, make_product):
    a = make_product()
    for path in ("check", "reserve", "release"):
        url = f"/products/stock/{path}"
        assert client.post(url, json={"items": []}).status_code == 400
        assert client.post(url, json={"items": [{"product_id": a["id"], "quantity": 0}]}).status_code == 400
        assert client.post(url, json={"items": [{"product_id": a["id"], "quantity": -1}]}).status_code == 400
        dup = {"items": [{"product_id": a["id"], "quantity": 1}] * 2}
        assert client.post(url, json=dup).status_code == 400


def test_concurrent_reserve_never_oversells(client, make_product, db_session):
    product = make_product(quantity=5)
    results = []

    def worker():
        response = client.post("/products/stock/reserve", json={"items": [{"product_id": product["id"], "quantity": 1}]})
        results.append(response.status_code)

    threads = [threading.Thread(target=worker) for _ in range(12)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(results).count(200) == 5 and results.count(409) == 7
    assert db_session.scalar(select(Product.quantity).where(Product.id == product["id"])) == 0
