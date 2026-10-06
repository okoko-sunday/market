# Dealer integration v1

`POST /api/integrations/v1/dealer-events/` receives the dealer product's exact JSON envelope and requires `X-Event-ID` plus `X-Showroom-Signature: sha256=<HMAC-SHA256>`. The signature covers the raw body. The source is selected by `X-Integration-Source` (default `dealer-platform`) and must be active. Bodies above 1 MiB are rejected.

A valid event is committed to the inbox before a `202` response. Replays with the same digest return `200`; reuse of an event ID with different bytes returns `409`. Unsupported or malformed events return `400`, missing/invalid credentials `401`, and temporary server failures `503`. A worker applies events with bounded exponential retries.

Dealer and vehicle snapshots use the fields already emitted by `/home/l2euser/cars/dealers/services.py`. Relative image URLs are resolved only against the source's configured public base URL; production should emit stable R2/CDN URLs. Event payloads never grant marketplace publication.

## Snapshot/reconciliation contract gap

The inspected dealer product does not currently expose an authenticated snapshot endpoint. The compatible additive endpoint should be `GET /api/integrations/v1/marketplace-snapshot/?cursor=...&limit=100`, authenticated with a separate bearer credential, returning full dealer and vehicle snapshots plus `{next_cursor, complete, checkpoint}`. The cursor must order by `(updated_at, id)` so equal timestamps cannot be skipped. Tombstones are explicit; absence is not deletion unless a complete reconciliation run is confirmed.

The marketplace command `python manage.py reconcile_source dealer-platform` consumes that shape. Initial snapshots create pending listings. Failed or incomplete pagination never withdraws missing records.

Local Docker networking: set the dealer worker URL to `http://host.docker.internal:8002/api/integrations/v1/dealer-events/` when projects run in separate Compose networks, or attach both worker containers to a shared external network and use `http://market-backend:8000/...`. Never use `localhost` inside the dealer worker.
