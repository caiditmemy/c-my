import json
import os

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://nambede:nambede@127.0.0.1:55440/order_db_test"
)
os.environ["DATABASE_URL"] = TEST_DATABASE_URL

import httpx  # noqa: E402
import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from order_service.db import Base, SessionLocal, engine  # noqa: E402
from order_service.main import app  # noqa: E402
from order_service.product_client import ProductClient, get_product_client  # noqa: E402


class FakeProductService:
    """product-service giả chạy trong bộ nhớ, nói đúng giao thức HTTP của product-service thật (qua httpx.MockTransport)."""

    def __init__(self) -> None:
        self.products: dict[int, dict] = {}
        self.down = False
        self.calls: list[tuple[str, str]] = []

    def add(self, pid: int, name: str, price: str, quantity: int) -> None:
        self.products[pid] = {"id": pid, "sku": f"SP{pid}", "name": name, "price": price, "quantity": quantity}

    def stock(self, pid: int) -> int:
        return self.products[pid]["quantity"]

    def handler(self, request: httpx.Request) -> httpx.Response:
        if self.down:
            raise httpx.ConnectError("connection refused", request=request)
        path = request.url.path
        self.calls.append((request.method, path))
        body = json.loads(request.content) if request.content else None
        if request.method == "GET" and path.startswith("/products/"):
            product = self.products.get(int(path.rsplit("/", 1)[1]))
            if product is None:
                return httpx.Response(404, json={"message": "Không tìm thấy sản phẩm"})
            return httpx.Response(200, json=product)
        if path == "/products/stock/check":
            lines = []
            for item in body["items"]:
                product = self.products.get(item["product_id"])
                available = product["quantity"] if product else 0
                lines.append(
                    {
                        "product_id": item["product_id"],
                        "requested": item["quantity"],
                        "available": available,
                        "exists": product is not None,
                        "enough": product is not None and available >= item["quantity"],
                    }
                )
            return httpx.Response(200, json={"all_enough": all(l["enough"] for l in lines), "items": lines})
        if path == "/products/stock/reserve":
            for item in body["items"]:
                product = self.products.get(item["product_id"])
                if product is None:
                    return httpx.Response(404, json={"message": "Không tìm thấy sản phẩm"})
                if product["quantity"] < item["quantity"]:
                    return httpx.Response(409, json={"message": f"Không đủ hàng trong kho: {product['name']}"})
            for item in body["items"]:
                self.products[item["product_id"]]["quantity"] -= item["quantity"]
            return httpx.Response(200, json={"items": []})
        if path == "/products/stock/release":
            for item in body["items"]:
                if item["product_id"] in self.products:
                    self.products[item["product_id"]]["quantity"] += item["quantity"]
            return httpx.Response(200, json={"items": []})
        return httpx.Response(404, json={"message": "?"})


@pytest.fixture(scope="session", autouse=True)
def schema():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture(autouse=True)
def clean(schema):
    with engine.begin() as connection:
        connection.execute(text("TRUNCATE orders, order_items RESTART IDENTITY CASCADE"))


@pytest.fixture
def products() -> FakeProductService:
    fake = FakeProductService()
    fake.add(1, "Bút bi", "5000.00", 10)
    fake.add(2, "Vở kẻ ngang", "12000.50", 3)
    return fake


@pytest.fixture
def client(products):
    app.dependency_overrides[get_product_client] = lambda: ProductClient(
        "http://product-service", transport=httpx.MockTransport(products.handler)
    )
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def db_session():
    with SessionLocal() as session:
        yield session


CUSTOMER = {"customer_name": "Nguyễn Văn A", "customer_phone": "0901234567", "address": "Quy Nhơn"}


@pytest.fixture
def make_order(client):
    def build(items=None, **extra) -> dict:
        body = {**CUSTOMER, "items": items or [{"product_id": 1, "quantity": 2}], **extra}
        response = client.post("/orders", json=body)
        assert response.status_code == 201, response.text
        return response.json()

    return build
