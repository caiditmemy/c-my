"""Gọi HTTP JSON chỉ bằng thư viện chuẩn (chạy được không cần cài gì)."""

import json
import urllib.error
import urllib.request


def call(method: str, url: str, body: dict | None = None, timeout: float = 10.0) -> tuple[int, dict | None]:
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(url, data=data, method=method, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read()
            return response.status, json.loads(raw) if raw else None
    except urllib.error.HTTPError as error:
        raw = error.read()
        return error.code, json.loads(raw) if raw else None
