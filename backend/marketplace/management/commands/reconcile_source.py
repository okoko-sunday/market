import json, urllib.request
from django.core.management.base import BaseCommand,CommandError
from django.db import transaction
from django.utils import timezone
from marketplace.models import IntegrationSource,IntegrationInboxEvent,BackgroundJob,ReconciliationRun

class Command(BaseCommand):
    help="Consume an authenticated, paginated dealer snapshot"
    def add_arguments(self,p): p.add_argument("source")
    def handle(self,*args,**opts):
        source=IntegrationSource.objects.get(slug=opts["source"])
        if not source.snapshot_url or not source.snapshot_token: raise CommandError("Snapshot URL/token are not configured")
        run=ReconciliationRun.objects.create(source=source); cursor=None
        try:
            while True:
                url=source.snapshot_url+(f"?cursor={cursor}&limit=100" if cursor else "?limit=100")
                req=urllib.request.Request(url,headers={"Authorization":f"Bearer {source.snapshot_token}"})
                with urllib.request.urlopen(req,timeout=20) as response: page=json.load(response)
                if not isinstance(page.get("items"),list): raise ValueError("Invalid snapshot page")
                for item in page["items"]:
                    event_id=item.get("event_id") or item["snapshot_id"]
                    event,created=IntegrationInboxEvent.objects.get_or_create(source=source,event_id=event_id,defaults={"event_type":item["event_type"],"occurred_at":item.get("occurred_at",timezone.now().isoformat()),"payload":item["data"],"body_digest":item.get("digest",str(event_id).replace("-",""))[:64]})
                    if created: BackgroundJob.objects.create(kind="process_inbox_event",payload={"event_id":str(event.id)}); run.changed_count+=1
                    run.seen_count+=1
                cursor=page.get("next_cursor"); run.checkpoint=page.get("checkpoint",{}); run.save()
                if not cursor:
                    if not page.get("complete"): raise ValueError("Snapshot ended without complete=true; no absence-based withdrawal performed")
                    run.complete=True; run.status="succeeded"; run.save(); break
        except Exception as exc:
            run.status="failed"; run.error=str(exc)[:2000]; run.save(); raise CommandError(str(exc))
