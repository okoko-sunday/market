# Performance baseline

The catalog uses bounded pagination (maximum 48), allow-listed sorting, indexed eligibility/availability and `select_related`/`prefetch_related` to avoid N+1 queries. No ordinary endpoint loads the full catalog.

Reproduce a local PostgreSQL baseline after loading fixtures:

```bash
docker compose exec backend python manage.py shell -c "from django.test import Client; import time; c=Client(); s=time.perf_counter(); [c.get('/api/v1/vehicles/?page_size=24&availability=available') for _ in range(100)]; print((time.perf_counter()-s)*10, 'ms mean')"
```

For an HTTP baseline, run `scripts/catalog-load.sh http://localhost:8002` after approving fixture inventory. Record p50/p95, database row count, machine, and commit. The repository build environment used SQLite and an empty public result set, so no production-scale latency claim is made here; Railway/PostgreSQL measurements are a launch requirement.
