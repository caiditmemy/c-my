"""Client HTTP gọi product-service. Order-service chỉ biết product-service qua API này, không đọc product_db."""

import logging
from typing import Any

import httpx

from order_service.config import get_settings
from order_service.errors import ApiError

log = logging.getLogger(__name__)

UNAVAILABLE = "Không kết nối được dịch vụ sản phẩm (product-service), vui lòng thử lại sau"


class ProductClient:
    def __init__(self, base_url: str, timeout: float = 5.0, transport: httpx.BaseTransport | None = None) -> None:
        self._http = httpx.Client(base_url=base_url.rstrip("/"), timeout=timeout, transport=transport)

    def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        try:
            return self._http.request(method, path, **kwargs)
        except httpx.HTTPError as exc:
            log.warning("product-service không phản hồi (%s %s): %s", method, path, exc)
            raise ApiError(503, UNAVAILABLE) from None

    def _json(self, response: httpx.Response) -> Any:
        if response.status_code >= 500:
            raise ApiError(503, UNAVAILABLE)
        return response.json()

    def get_product(self, product_id: int) -> dict | None:
        """None nếu sản phẩm không tồn tại."""
        response = self._request("GET", f"/products/{product_id}")
        if response.status_code == 404:
            return None
        if response.status_code != 200:
            raise ApiError(503, UNAVAILABLE)
        return response.json()

    def check_stock(self, items: list[dict]) -> dict:
        response = self._request("POST", "/products/stock/check", json={"items": items})
        if response.status_code != 200:
            raise ApiError(503, UNAVAILABLE)
        return response.json()

    def reserve(self, items: list[dict]) -> None:
        """Trừ kho tất cả hoặc không gì cả. 409 nếu thiếu hàng, 404 nếu sản phẩm biến mất."""
        response = self._request("POST", "/products/stock/reserve", json={"items": items})
        if response.status_code == 200:
            return
        if response.status_code in (404, 409):
            raise ApiError(response.status_code, self._json(response).get("message", "Không giữ được hàng trong kho"))
        raise ApiError(503, UNAVAILABLE)

    def release(self, items: list[dict]) -> None:
        response = self._request("POST", "/products/stock/release", json={"items": items})
        if response.status_code != 200:
            raise ApiError(503, UNAVAILABLE)

    def ping(self) -> bool:
        try:
            return self._http.get("/health").status_code == 200
        except httpx.HTTPError:
            return False


def get_product_client() -> ProductClient:
    """FastAPI dependency (test thay bằng client giả / MockTransport)."""
    settings = get_settings()
    return ProductClient(settings.product_service_url, settings.product_service_timeout)
