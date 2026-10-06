# Operations

## Production

- Deploy `frontend/` to Vercel with `API_INTERNAL_URL` and `NEXT_PUBLIC_API_URL` pointing to the Railway backend.
- Deploy backend and worker from the same image on Railway. Backend runs `python manage.py migrate && gunicorn config.wsgi:application`; worker runs `python manage.py process_jobs`.
- Use Railway PostgreSQL with TLS. Run migrations once before shifting traffic; rollback application first, then use a tested forward data migration rather than destructive reversal.
- Configure R2 credentials and a stable media custom domain. Enable bucket versioning/lifecycle rules and validate upload MIME, dimensions, and size.
- Back up PostgreSQL daily with point-in-time recovery and test restore quarterly. Back up/version object storage separately.
- Set unique production secrets, HTTPS-only cookies, exact CORS/CSRF origins, allowed hosts, and per-source webhook secrets. Rotate by provisioning a second source credential, updating the sender, observing delivery, then revoking the old credential.

Buyer records default to 365-day retention; run `purge_buyer_data --days 365` after legal review. Logs contain correlation IDs and entity IDs, never raw payloads, secrets, email addresses, phone numbers, or internal notes.

Health endpoints: `/health/` is liveness and `/ready/` checks the database. Monitor failed inbox events, oldest queued job, last reconciliation, and source sync age.

## Current production follow-up

Add infrastructure rate limiting at the CDN/proxy, malware scanning and derivative generation for uploads, managed secret encryption, error monitoring, production load testing, and the dealer snapshot endpoint before launch. The included application throttles are defense-in-depth, not DDoS protection.
