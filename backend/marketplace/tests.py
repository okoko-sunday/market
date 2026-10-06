import hashlib,hmac,json,threading,uuid
from django.contrib.auth import get_user_model
from django.test import TestCase,TransactionTestCase,override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient
from .catalog import eligible_public
from .integration import process_event
from .models import *
from .moderation import decide

@override_settings(SECURE_SSL_REDIRECT=False)
class MarketplaceTests(TestCase):
    def setUp(self):
        self.source=IntegrationSource.objects.create(slug="test",name="Test",secret="secret",public_base_url="http://dealer.test")
        self.dealer=DealerProfileProjection.objects.create(source=self.source,external_id=uuid.uuid4(),source_version=1,name="Dealer",slug="dealer")
        self.user=get_user_model().objects.create_superuser("admin","a@example.test","long-test-password")
    def data(self,version=1,availability="available",publication="published"):
        return {"id":str(getattr(self,"vehicle_id",uuid.uuid4())),"dealer_id":str(self.dealer.external_id),"version":version,"title":"2022 Toyota Camry","slug":"camry","make":"Toyota","model":"Camry","year":2022,"price":"40000000.00","currency":"NGN","mileage_km":12000,"transmission":"Automatic","fuel_type":"Petrol","condition":"Used","location":"Lagos","description":"Dealer provided","features":[],"known_issues":"","seller_history":"","images":[],"availability":availability,"publication_status":publication,"updated_at":timezone.now().isoformat()}
    def event(self,typ,data):
        e=IntegrationInboxEvent.objects.create(source=self.source,event_id=uuid.uuid4(),event_type=typ,occurred_at=timezone.now(),payload=data,body_digest=uuid.uuid4().hex); process_event(e.id); e.refresh_from_db(); return e
    def test_import_pending_then_moderation_public(self):
        self.vehicle_id=uuid.uuid4(); self.event("vehicle.published.v1",self.data())
        listing=MarketplaceListing.objects.get(); self.assertEqual(listing.decision,"pending_review"); self.assertFalse(eligible_public().exists())
        decide(listing.id,"approved","Meets listing rules",self.user); self.assertTrue(eligible_public().exists())
    def test_updates_preserve_hidden_and_sold_applies(self):
        self.vehicle_id=uuid.uuid4(); self.event("vehicle.published.v1",self.data()); listing=MarketplaceListing.objects.get(); decide(listing.id,"hidden","review",self.user)
        self.event("vehicle.updated.v1",{**self.data(2),"price":"39000000.00"}); listing.refresh_from_db(); self.assertEqual(listing.decision,"hidden"); self.assertEqual(listing.imported_vehicle.price,39000000)
        self.event("vehicle.sold.v1",self.data(3,"available")); listing.imported_vehicle.refresh_from_db(); self.assertEqual(listing.imported_vehicle.availability,"sold")
    def test_withdraw_republish_needs_review_and_stale_ignored(self):
        self.vehicle_id=uuid.uuid4(); self.event("vehicle.published.v1",self.data(2)); listing=MarketplaceListing.objects.get(); decide(listing.id,"approved","ok",self.user)
        self.event("vehicle.withdrawn.v1",self.data(3,publication="unpublished")); listing.refresh_from_db(); self.assertEqual(listing.decision,"withdrawn"); self.assertFalse(eligible_public().exists())
        self.event("vehicle.published.v1",self.data(4)); listing.refresh_from_db(); self.assertEqual(listing.decision,"pending_review")
        stale=self.event("vehicle.updated.v1",{**self.data(2),"price":"1.00"}); self.assertEqual(stale.status,"ignored"); listing.imported_vehicle.refresh_from_db(); self.assertEqual(listing.imported_vehicle.price,40000000)
    def test_vehicle_dealer_cannot_be_reassigned(self):
        self.vehicle_id=uuid.uuid4(); self.event("vehicle.published.v1",self.data()); other=DealerProfileProjection.objects.create(source=self.source,external_id=uuid.uuid4(),source_version=1,name="Other",slug="other")
        event=IntegrationInboxEvent.objects.create(source=self.source,event_id=uuid.uuid4(),event_type="vehicle.updated.v1",occurred_at=timezone.now(),payload={**self.data(2),"dealer_id":str(other.external_id)},body_digest=uuid.uuid4().hex)
        with self.assertRaises(Exception): process_event(event.id)
    def test_buyer_validation_and_imported_fields_have_no_write_api(self):
        self.vehicle_id=uuid.uuid4(); self.event("vehicle.published.v1",self.data()); listing=MarketplaceListing.objects.get(); decide(listing.id,"approved","ok",self.user)
        r=APIClient().post("/api/v1/buyer-requests/",{"listing":str(listing.id),"kind":"offer","name":"Buyer","email":"b@example.test","phone":"0800"},format="json"); self.assertEqual(r.status_code,400)
        client=APIClient(); client.force_authenticate(self.user)
        self.assertEqual(client.patch(f"/api/v1/staff/listings/{listing.id}/",{"price":"1"},format="json").status_code,405)
    def test_unauthorized_cannot_moderate(self):
        self.vehicle_id=uuid.uuid4(); self.event("vehicle.published.v1",self.data()); listing=MarketplaceListing.objects.get(); self.assertEqual(APIClient().post(f"/api/v1/staff/listings/{listing.id}/moderate/",{"decision":"approved"},format="json").status_code,403)

@override_settings(SECURE_SSL_REDIRECT=False)
class ReceiverTests(TestCase):
    def setUp(self): self.source=IntegrationSource.objects.get(slug="dealer-platform"); self.source.secret="secret"; self.source.save()
    def post(self,envelope,signature=True,header=None):
        body=json.dumps(envelope,separators=(",",":")).encode(); sig=hmac.new(b"secret",body,hashlib.sha256).hexdigest() if signature else "bad"
        return self.client.post("/api/integrations/v1/dealer-events/",body,content_type="application/json",HTTP_X_EVENT_ID=header or envelope.get("event_id",""),HTTP_X_SHOWROOM_SIGNATURE=f"sha256={sig}")
    def test_signature_dedup_and_collision(self):
        e={"event_id":str(uuid.uuid4()),"event_type":"dealer.created.v1","occurred_at":timezone.now().isoformat(),"data":{"id":str(uuid.uuid4()),"version":1,"name":"D","slug":"d"}}
        self.assertEqual(self.post(e,False).status_code,401); self.assertEqual(self.post(e).status_code,202); self.assertEqual(self.post(e).status_code,200)
        changed={**e,"data":{**e["data"],"name":"Changed"}}; self.assertEqual(self.post(changed).status_code,409)
    def test_malformed_and_mismatched_id_rejected(self):
        e={"event_id":str(uuid.uuid4()),"event_type":"bad","occurred_at":timezone.now().isoformat(),"data":{}}
        self.assertEqual(self.post(e).status_code,400); self.assertEqual(self.post({**e,"event_type":"dealer.created.v1"},header=str(uuid.uuid4())).status_code,400)

@override_settings(SECURE_SSL_REDIRECT=False)
class OwnedVehicleTests(TestCase):
    def test_authorized_staff_can_create_owned_vehicle(self):
        user=get_user_model().objects.create_superuser("admin","a@x.test","long-test-password"); client=APIClient(); client.force_authenticate(user)
        data={"title":"2024 Lexus RX","slug":"2024-lexus-rx","make":"Lexus","model":"RX","year":2024,"price":"90000000.00","currency":"NGN","mileage_km":100,"transmission":"Automatic","fuel_type":"Petrol","condition":"New","location":"Abuja","description":"Marketplace inventory","features":[],"known_issues":"","seller_history":"","video_url":"","availability":"available"}
        self.assertEqual(client.post("/api/v1/staff/owned-vehicles/",data,format="json").status_code,201); self.assertTrue(MarketplaceListing.objects.filter(owned_vehicle__isnull=False).exists())
