from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Đọc từ biến môi trường (docker compose) hoặc file .env khi chạy local."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://nambede:nambede@127.0.0.1:55440/product_db"
    #: Các origin được phép gọi từ trình duyệt (giao diện web do order-service phục vụ)
    cors_origins: str = "*"


@lru_cache
def get_settings() -> Settings:
    return Settings()
