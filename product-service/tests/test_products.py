def test_create_and_get(client):
    response = client.post(
        "/products", json={"sku": " SP001 ", "name": "Bút bi", "description": "Xanh", "price": "5000.50", "quantity": 7}
    )
    assert response.status_code == 201
    body = response.json()
    assert body["sku"] == "SP001"
    assert body["quantity"] == 7
    assert float(body["price"]) == 5000.5
    assert body["created_at"] and body["updated_at"]
    got = client.get(f"/products/{body['id']}")
    assert got.status_code == 200 and got.json()["name"] == "Bút bi"


def test_quantity_defaults_to_zero(client):
    response = client.post("/products", json={"sku": "A", "name": "A", "price": 1})
    assert response.json()["quantity"] == 0


def test_duplicate_sku_is_409(client, make_product):
    make_product(sku="DUP")
    response = client.post("/products", json={"sku": "DUP", "name": "x", "price": 1})
    assert response.status_code == 409
    assert "DUP" in response.json()["message"]
    assert set(response.json()) == {"status", "error", "message", "path"}


def test_validation(client):
    bad = [
        {"sku": "A", "name": "A", "price": -1},
        {"sku": "A", "name": "A", "price": 1, "quantity": -5},
        {"sku": "", "name": "A", "price": 1},
        {"sku": "A", "name": "   ", "price": 1},
        {"sku": "A", "price": 1},
        {"sku": "A", "name": "A", "price": "abc"},
    ]
    for body in bad:
        response = client.post("/products", json=body)
        assert response.status_code == 400, body
        assert response.json()["message"].startswith("Dữ liệu không hợp lệ")


def test_get_missing_is_404(client):
    response = client.get("/products/999")
    assert response.status_code == 404
    assert "999" in response.json()["message"]


def test_list_search_and_paging(client, make_product):
    for i in range(5):
        make_product(name=f"Áo thun {i}")
    make_product(name="Quần jean", sku="QJ")
    page = client.get("/products", params={"size": 4}).json()
    assert page["total"] == 6 and len(page["items"]) == 4 and page["page"] == 1
    page2 = client.get("/products", params={"size": 4, "page": 2}).json()
    assert len(page2["items"]) == 2
    found = client.get("/products", params={"q": "áo"}).json()
    assert found["total"] == 5
    assert client.get("/products", params={"q": "qj"}).json()["total"] == 1
    assert client.get("/products", params={"q": "%"}).json()["total"] == 0
    assert client.get("/products", params={"page": 0}).status_code == 400


def test_put_and_patch(client, make_product):
    product = make_product()
    pid = product["id"]
    put = client.put(f"/products/{pid}", json={"sku": "NEW", "name": "Mới", "price": "1", "quantity": 3})
    assert put.status_code == 200 and put.json()["sku"] == "NEW" and put.json()["description"] is None
    patch = client.patch(f"/products/{pid}", json={"price": "99"})
    assert patch.status_code == 200
    assert float(patch.json()["price"]) == 99 and patch.json()["name"] == "Mới"
    assert client.patch(f"/products/{pid}", json={"quantity": -1}).status_code == 400
    assert client.patch(f"/products/{pid}", json={"name": None}).status_code == 400
    assert client.patch("/products/999", json={"price": 1}).status_code == 404
    assert client.put("/products/999", json={"sku": "Z", "name": "z", "price": 1, "quantity": 1}).status_code == 404


def test_update_to_existing_sku_is_409(client, make_product):
    a = make_product()
    b = make_product()
    assert client.patch(f"/products/{b['id']}", json={"sku": a["sku"]}).status_code == 409
    # chính sku của mình thì được
    assert client.patch(f"/products/{b['id']}", json={"sku": b["sku"]}).status_code == 200


def test_delete(client, make_product):
    pid = make_product()["id"]
    assert client.delete(f"/products/{pid}").status_code == 204
    assert client.get(f"/products/{pid}").status_code == 404
    assert client.delete(f"/products/{pid}").status_code == 404


def test_health_and_cors(client):
    assert client.get("/health").json() == {"status": "UP", "db": "UP"}
    response = client.options(
        "/products", headers={"Origin": "http://x", "Access-Control-Request-Method": "POST"}
    )
    assert response.headers["access-control-allow-origin"] in ("*", "http://x")


def test_unknown_path_error_format(client):
    response = client.get("/nope")
    assert response.status_code == 404
    assert response.json()["path"] == "/nope"
