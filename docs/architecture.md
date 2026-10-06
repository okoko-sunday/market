# Architecture and ownership

## Boundaries

The marketplace and dealer product remain separate deployments and databases. Django owns all domain rules and exposes versioned JSON APIs. Next.js renders public and staff experiences and never treats hidden buttons as authorization. PostgreSQL is authoritative; the database-backed `BackgroundJob` queue is processed by a separate worker.

The backend package is divided by concern: catalog/public eligibility, dealer projection, moderation, buyer requests, integration inbox/reconciliation, staff capabilities, and auditing. They share one transaction boundary as a modular monolith.

## Core schema and invariants

- `IntegrationSource`: server-configured sender identity and HMAC secret. Secrets are encrypted/platform-managed in production; the local value is development-only.
- `DealerProfileProjection`: source-owned dealer facts, versioned per source. Suspension is marketplace-owned.
- `DealerVehicleProjection`: typed, searchable dealer facts. `(source, external_id)` is unique and `dealer` cannot be silently reassigned.
- `MarketplaceOwnedVehicle`: editable marketplace-owned facts.
- `MarketplaceListing`: exactly one of the two vehicle relations must be populated. Moderation and featuring live here, never in source projections.
- `VehicleMedia`: ordered media for marketplace-owned vehicles. Dealer media remains in immutable source snapshots.
- `ModerationDecision`: append-only decision history.
- `BuyerRequest` / `BuyerRequestActivity`: buyer workflow and private activity.
- `IntegrationInboxEvent`: exact body digest, processing state, and deduplication by `(source, event_id)`.
- `BackgroundJob`, `ReconciliationRun`, and `AuditEntry`: durable operations and traceability.

Critical ownership combinations use database check constraints. Money is `Decimal(14,2)` with explicit three-character currency. UUIDs identify all externally referenced records. Foreign keys use `PROTECT` where deletion would destroy provenance. Media ordering is unique per marketplace vehicle.

## Eligibility

One query function is reused by public lists, details, featured inventory, dealer storefronts, recommendations, and sitemaps. A listing is public only when approved, not removed, its source is published, its dealer is active and not suspended, and the projection is complete. Available search adds `availability=available`. Approved sold pages remain addressable but have no buyer-request actions.

Withdrawal forces a source eligibility flag off and moves the listing to `withdrawn`. A later source publish moves it to `pending_review`; it is never silently restored. Ordinary updates and sold events do not reset moderation.

## Permissions

| Capability | Administrator | Moderator | Inventory manager | Support | Analyst |
|---|---:|---:|---:|---:|---:|
| View staff data | yes | yes | yes | yes | yes |
| Moderate imported inventory | yes | yes | no | no | no |
| Edit marketplace inventory | yes | no | yes | no | no |
| Suspend dealers | yes | yes | no | no | no |
| Manage buyer requests | yes | no | no | yes | no |
| Retry integration jobs | yes | no | no | no | no |

Capabilities are Django permissions checked on every protected endpoint; group names only seed those explicit permissions.

## Concurrency

Inbox rows are persisted before processing. Processing locks the inbox row and target projection, compares monotonic source versions, and updates source facts without touching moderation fields. Moderation locks only the listing and appends a decision in the same transaction. This preserves concurrent source and marketplace changes.
