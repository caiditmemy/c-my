# Mini SOA quản lý đơn hàng. Xem README.md
PG_BIN  ?= /workspace/pg17/bin
PG_DATA ?= /tmp/th4-pg
PG_PORT ?= 55440
PRODUCT_URL ?= http://127.0.0.1:8091
ORDER_URL   ?= http://127.0.0.1:8092

.PHONY: install db-up db-down run-product run-order test test-dbs test-product test-order docker-up docker-down docker-seed seed smoke

install:
	cd product-service && uv sync
	cd order-service && uv sync

# Postgres native (không Docker): khởi tạo lần đầu, khởi động và tạo 4 database
db-up:
	@test -d $(PG_DATA) || (echo nambede > $(PG_DATA).pw && $(PG_BIN)/initdb -D $(PG_DATA) -U nambede --pwfile=$(PG_DATA).pw -A scram-sha-256 >/dev/null)
	@$(PG_BIN)/pg_ctl -D $(PG_DATA) status >/dev/null 2>&1 || $(PG_BIN)/pg_ctl -D $(PG_DATA) -o "-p $(PG_PORT) -k /tmp -c listen_addresses=127.0.0.1" -l $(PG_DATA).log -w start
	uv run --project product-service python scripts/create_dbs.py

db-down:
	$(PG_BIN)/pg_ctl -D $(PG_DATA) stop

run-product:
	cd product-service && uv run alembic upgrade head && uv run uvicorn product_service.main:app --port 8091 --reload

run-order:
	cd order-service && uv run alembic upgrade head && PRODUCT_SERVICE_URL=$(PRODUCT_URL) uv run uvicorn order_service.main:app --port 8092 --reload

# Test chạy trên Postgres ở cổng 55440 (native hoặc Docker): tạo trước *_test nếu chưa có
test: test-dbs test-product test-order

test-dbs:
	uv run --project product-service python scripts/create_dbs.py

test-product:
	cd product-service && uv run pytest -q

test-order:
	cd order-service && uv run pytest -q

docker-up:
	docker compose up -d --build --wait

docker-down:
	docker compose down

docker-seed:
	docker compose run --rm seed

seed:
	python3 scripts/seed.py --product-url $(PRODUCT_URL)

smoke:
	python3 scripts/smoke.py --product-url $(PRODUCT_URL) --order-url $(ORDER_URL)
