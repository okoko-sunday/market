# Motori marketplace

Motori is a standalone Nigerian vehicle marketplace. It imports signed dealer inventory events into a Django/DRF modular monolith, keeps marketplace moderation separate from source-owned facts, and serves a Next.js storefront and staff workspace.

## Quick start

```bash
cp .env.example .env
docker compose up --build
```

Open the marketplace at <http://localhost:3001>, the API at <http://localhost:8002/api/v1/>, and Django admin at <http://localhost:8002/admin/>. Development fixtures are opt-in:

```bash
docker compose exec backend python manage.py seed_demo
```

This creates `admin` / `motori-demo-2026` only in `DEBUG` mode. Never use those credentials in production.

## Checks

```bash
cd backend && ../.venv/bin/python manage.py test
cd frontend && npm run typecheck && npm run build
```

See [architecture](docs/architecture.md), [integration](docs/integration.md), [operations](docs/operations.md), and [demo guide](docs/demo.md).
