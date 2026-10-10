.PHONY: install api web test e2e lint dev
install:
	cd backend && pip install -e ".[dev]"
	cd frontend && npm install
api:
	cd backend && uvicorn asclepius.main:create_app --factory --reload --port 8000
web:
	cd frontend && npm run dev
test:
	cd backend && python -m pytest --cov=asclepius -q
e2e:
	cd frontend && npm run e2e
e2e:
	cd frontend && npm run e2e
lint:
	cd backend && ruff check asclepius tests
	cd frontend && npm run lint
dev:
	$(MAKE) -j2 api web
