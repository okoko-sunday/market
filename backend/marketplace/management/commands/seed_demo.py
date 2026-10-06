import uuid
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand,CommandError
from django.utils import timezone
from marketplace.models import IntegrationSource,IntegrationInboxEvent
from marketplace.integration import process_event

class Command(BaseCommand):
    help="Load clearly labelled development fixtures"
    def handle(self,*args,**opts):
        if not settings.DEBUG: raise CommandError("Development fixtures are disabled outside DEBUG")
        User=get_user_model(); user,_=User.objects.get_or_create(username="admin",defaults={"is_staff":True,"is_superuser":True,"email":"admin@example.test"}); user.set_password("motori-demo-2026"); user.save()
        source=IntegrationSource.objects.get(slug=settings.INTEGRATION_SOURCE_SLUG); dealer_id=uuid.uuid4()
        dealer={"id":str(dealer_id),"version":1,"name":"Eko Auto House","slug":"eko-auto-house","tagline":"Carefully presented cars in Lagos","story":"A development fixture dealer used for local evaluation.","email":"hello@example.test","phone":"+234 800 000 0000","address":"Victoria Island, Lagos","location":"Lagos","website_url":"https://example.test","updated_at":timezone.now().isoformat()}
        vehicle={"id":str(uuid.uuid4()),"dealer_id":str(dealer_id),"version":1,"title":"2022 Toyota Camry XSE","slug":"2022-toyota-camry-xse","make":"Toyota","model":"Camry XSE","year":2022,"price":"48500000.00","currency":"NGN","mileage_km":31000,"transmission":"Automatic","fuel_type":"Petrol","condition":"Foreign used","location":"Victoria Island, Lagos","description":"Dealer-provided description: clean interior, complete documentation and two keys.","features":["Leather interior","Reverse camera","Adaptive cruise control"],"known_issues":"Light stone chip on the bonnet.","seller_history":"Imported in 2025; service records available from the seller.","video_url":"","availability":"available","publication_status":"published","images":[],"updated_at":timezone.now().isoformat()}
        for typ,data in [("dealer.created.v1",dealer),("vehicle.published.v1",vehicle)]:
            event=IntegrationInboxEvent.objects.create(source=source,event_id=uuid.uuid4(),event_type=typ,occurred_at=timezone.now(),payload=data,body_digest=uuid.uuid4().hex); process_event(event.id)
        self.stdout.write(self.style.SUCCESS("Loaded development fixtures; imported vehicle remains Pending review."))
