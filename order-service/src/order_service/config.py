from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Đọc từ biến môi trường (docker compose) hoặc file .env khi chạy local."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://nambede:nambede@127.0.0.1:55440/order_db"
    #: Địa chỉ product-service mà order-service gọi (trong Docker: http://product-service:8091)
    product_service_url: str = "http://127.0.0.1:8091"
    #: Địa chỉ product-service mà TRÌNH DUYỆT gọi (giao diện web), thường là localhost
    public_product_service_url: str = "http://localhost:8091"
    product_service_timeout: float = 5.0


@lru_cache
def get_settings() -> Settings:
    return Settings()
