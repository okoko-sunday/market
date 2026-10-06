from django.core.management.base import BaseCommand
from django.utils import timezone
from marketplace.models import BuyerRequest
class Command(BaseCommand):
    def add_arguments(self,p): p.add_argument("--days",type=int,default=365)
    def handle(self,*args,**o):
        cutoff=timezone.now()-timezone.timedelta(days=o["days"]); qs=BuyerRequest.objects.filter(created_at__lt=cutoff,status="closed"); count=qs.update(name="Deleted buyer",email="deleted@example.invalid",phone="",message="",internal_note="")
        self.stdout.write(f"Anonymised {count} closed buyer requests")
