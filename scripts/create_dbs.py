"""Tạo các database trên Postgres chạy sẵn (dùng cho Postgres native: make db-up). Chạy lại không lỗi.

    uv run --project product-service python scripts/create_dbs.py
"""

import os

import psycopg
from psycopg import sql

HOST = os.environ.get("PGHOST", "127.0.0.1")
PORT = os.environ.get("PGPORT", "55440")
USER = os.environ.get("PGUSER", "nambede")
PASSWORD = os.environ.get("PGPASSWORD", "nambede")
DATABASES = ["product_db", "order_db", "product_db_test", "order_db_test"]

with psycopg.connect(host=HOST, port=PORT, user=USER, password=PASSWORD, dbname="postgres", autocommit=True) as conn:
    existing = {row[0] for row in conn.execute("SELECT datname FROM pg_database")}
    for name in DATABASES:
        if name in existing:
            print(f"đã có   {name}")
        else:
            conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
            print(f"đã tạo  {name}")
