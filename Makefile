.PHONY: help up up-alt re re-alt down clean build rebuild logs ps health test-backend

BACKEND_PORT ?= 8000
FRONTEND_PORT ?= 5173
VITE_API_BASE_URL ?= http://localhost:$(BACKEND_PORT)
CORS_ORIGINS ?= http://localhost:$(FRONTEND_PORT),http://127.0.0.1:$(FRONTEND_PORT)

help:
	@printf "Targets:\n"
	@printf "  make up            Start backend and frontend with Docker Compose\n"
	@printf "  make up-alt        Start on ports 8001 and 5174\n"
	@printf "  make re            Restart backend and frontend with Docker Compose\n"
	@printf "  make re-alt        Restart on ports 8001 and 5174\n"
	@printf "  make down          Stop containers\n"
	@printf "  make clean         Stop containers and remove demo data volume\n"
	@printf "  make build         Build Docker images\n"
	@printf "  make rebuild       Rebuild images without cache\n"
	@printf "  make logs          Follow Docker Compose logs\n"
	@printf "  make ps            Show container status\n"
	@printf "  make health        Check backend health endpoint\n"
	@printf "  make test-backend  Run backend tests in the Docker image\n"

up:
	BACKEND_PORT=$(BACKEND_PORT) FRONTEND_PORT=$(FRONTEND_PORT) VITE_API_BASE_URL=$(VITE_API_BASE_URL) CORS_ORIGINS=$(CORS_ORIGINS) docker compose up --build

up-alt:
	$(MAKE) up BACKEND_PORT=8001 FRONTEND_PORT=5174

re:
	$(MAKE) down
	$(MAKE) up BACKEND_PORT=$(BACKEND_PORT) FRONTEND_PORT=$(FRONTEND_PORT) VITE_API_BASE_URL=$(VITE_API_BASE_URL) CORS_ORIGINS=$(CORS_ORIGINS)

re-alt:
	$(MAKE) re BACKEND_PORT=8001 FRONTEND_PORT=5174

down:
	docker compose down

clean:
	docker compose down -v

build:
	docker compose build

rebuild:
	docker compose build --no-cache

logs:
	docker compose logs -f

ps:
	docker compose ps

health:
	curl -sS http://127.0.0.1:$(BACKEND_PORT)/health

test-backend:
	docker compose run --rm backend python -m pytest
