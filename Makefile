ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
export PYTHONPATH := $(ROOT)/apps/api/src$(if $(PYTHONPATH),:$(PYTHONPATH))

ifneq (,$(wildcard $(ROOT)/.env))
include $(ROOT)/.env
export
endif

.PHONY: up down api web seed reset test bench memtest benchsuite benchllm

up:
	docker compose up -d --build

down:
	docker compose down

api:
	cd $(ROOT)/apps/api && uv run uvicorn faultline.main:app --reload --host 127.0.0.1 --port $(API_PORT)

web:
	cd $(ROOT)/apps/web && npm run dev

seed:
	cd $(ROOT)/apps/api && uv run python -m faultline.graph.seed

reset:
	cd $(ROOT)/apps/api && uv run python -m faultline.graph.reset

test:
	cd $(ROOT)/apps/api && uv run pytest

bench:
	cd $(ROOT)/apps/api && uv run python -m faultline.bench.run

memtest:
	cd $(ROOT)/apps/api && uv run python -m faultline.bench.memory_tests

benchsuite:
	cd $(ROOT)/apps/api && uv run python -m faultline.bench.report

benchllm:
	cd $(ROOT)/apps/api && uv run python -m faultline.bench.llm_eval
