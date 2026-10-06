import time
from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.db import transaction
from django.utils import timezone
from marketplace.integration import process_event
from marketplace.models import BackgroundJob

class Command(BaseCommand):
    help="Process durable marketplace jobs"
    def add_arguments(self,p): p.add_argument("--once",action="store_true"); p.add_argument("--limit",type=int,default=100)
    def handle(self,*args,**opts):
        while True:
            processed=0
            for _ in range(opts["limit"]):
                with transaction.atomic():
                    job=BackgroundJob.objects.select_for_update(skip_locked=True).filter(status__in=["queued","failed"],run_after__lte=timezone.now()).order_by("run_after").first()
                    if not job: break
                    job.status="running"; job.locked_at=timezone.now(); job.attempts+=1; job.save()
                try:
                    if job.kind=="process_inbox_event": process_event(job.payload["event_id"])
                    elif job.kind=="reconcile_source": call_command("reconcile_source",job.payload["source"])
                    else: raise ValueError(f"Unknown job kind {job.kind}")
                    job.status="succeeded"; job.last_error=""
                except Exception as exc:
                    job.last_error=str(exc)[:2000]
                    if job.attempts>=job.max_attempts: job.status="failed"; job.run_after=timezone.now()+timezone.timedelta(days=3650)
                    else: job.status="failed"; job.run_after=timezone.now()+timezone.timedelta(minutes=min(2**job.attempts,60))
                job.save(); processed+=1
            if opts["once"]: break
            if not processed: time.sleep(5)
