import os

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://nambede:nambede@127.0.0.1:55440/product_db_test"
)
os.environ["DATABASE_URL"] = TEST_DATABASE_URL

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from product_service.db import Base, SessionLocal, engine  # noqa: E402
from product_service.main import app  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def schema():
    """Tạo schema một lần cho cả phiên test trên Postgres thật, xóa khi xong."""
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture(autouse=True)
def clean(schema):
    with engine.begin() as connection:
        connection.execute(text("TRUNCATE products RESTART IDENTITY"))


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def make_product(client):
    counter = {"n": 0}

    def build(quantity: int = 10, price: str = "10000", **extra) -> dict:
        counter["n"] += 1
        body = {"sku": f"SP{counter['n']:03d}", "name": f"Sản phẩm {counter['n']}", "price": price, "quantity": quantity}
        body.update(extra)
        response = client.post("/products", json=body)
        assert response.status_code == 201, response.text
        return response.json()

    return build


@pytest.fixture
def db_session():
    with SessionLocal() as session:
        yield session
