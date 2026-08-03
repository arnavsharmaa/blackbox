.PHONY: setup dev api web seed test test-api test-web lint lint-api lint-web \
        typecheck build demo smoke schema clean

PY := .venv/bin/python
PIP := .venv/bin/pip

## setup: create the Python venv, install backend + frontend dependencies
setup:
	python3 -m venv .venv
	$(PIP) install --upgrade pip
	$(PIP) install -e "apps/api[dev]"
	@# Some pip/Python combinations emit an editable .pth that site skips;
	@# write an explicit one so `import blackbox_api` always works.
	$(PY) -c "import site, os; open(os.path.join(site.getsitepackages()[0], 'blackbox_api_dev.pth'), 'w').write(os.path.abspath('apps/api') + chr(10))"
	@# Python 3.13 skips .pth files carrying the macOS hidden flag.
	@if [ "$$(uname)" = "Darwin" ]; then chflags nohidden .venv/lib/python*/site-packages/*.pth 2>/dev/null || true; fi
	npm install
	@echo "✓ setup complete — run 'make demo' to seed data and start the app"

## seed: regenerate the deterministic sample incidents and load them
seed:
	$(PY) scripts/seed.py

## api: run the FastAPI backend with reload
api:
	$(PY) -m uvicorn blackbox_api.main:app --app-dir apps/api --host 0.0.0.0 --port 8000 --reload

## web: run the Next.js frontend
web:
	npm run dev

## dev: run backend and frontend together
dev:
	./scripts/dev.sh

## demo: seed the database, then start the full application
demo: seed dev

test: test-api test-web

test-api:
	cd apps/api && ../../$(PY) -m pytest -q

test-web:
	npm run test

## smoke: end-to-end smoke test against a running app (make demo in another shell)
smoke:
	$(PY) scripts/smoke.py

lint: lint-api lint-web typecheck

lint-api:
	cd apps/api && ../../.venv/bin/ruff check blackbox_api tests
	cd apps/api && ../../.venv/bin/mypy blackbox_api

lint-web:
	npm run lint

typecheck:
	npm run typecheck

## build: production build of the frontend (backend has no build step)
build:
	npm run build

## schema: re-export packages/schemas/incident.schema.json from the Pydantic models
schema:
	$(PY) scripts/export_schema.py

clean:
	rm -rf data/*.db apps/web/.next
