"""Tạo vài sản phẩm demo qua API của product-service. Chạy lại không bị trùng (bỏ qua mã SKU đã có).

    python3 scripts/seed.py [--product-url http://127.0.0.1:8091]
"""

import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _http import call  # noqa: E402

PRODUCTS = [
    {"sku": "DEMO-BUT", "name": "Bút bi Thiên Long", "description": "Mực xanh 0.5mm", "price": "5000", "quantity": 200},
    {"sku": "DEMO-VO", "name": "Vở kẻ ngang 96 trang", "description": "Giấy trắng", "price": "12000", "quantity": 100},
    {"sku": "DEMO-BALO", "name": "Balo học sinh", "description": "Chống nước", "price": "250000", "quantity": 15},
    {"sku": "DEMO-MAYTINH", "name": "Máy tính Casio FX-580", "description": None, "price": "650000", "quantity": 5},
    {"sku": "DEMO-HET", "name": "Sản phẩm hết hàng (để thử lỗi 409)", "description": None, "price": "10000", "quantity": 0},
]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--product-url", default=os.environ.get("PRODUCT_URL", "http://127.0.0.1:8091"))
    base = parser.parse_args().product_url.rstrip("/")

    for _ in range(30):  # chờ product-service sẵn sàng
        try:
            if call("GET", base + "/health")[0] == 200:
                break
        except OSError:
            pass
        time.sleep(1)
    else:
        print(f"Không kết nối được {base}", file=sys.stderr)
        return 1

    for product in PRODUCTS:
        status, body = call("POST", base + "/products", product)
        if status == 201:
            print(f"đã tạo   {product['sku']}")
        elif status == 409:
            print(f"đã có    {product['sku']}")
        else:
            print(f"LỖI {status} {product['sku']}: {body}", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
