import uuid
from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q

class Timestamped(models.Model):
    created_at=models.DateTimeField(auto_now_add=True); updated_at=models.DateTimeField(auto_now=True)
    class Meta: abstract=True

class IntegrationSource(Timestamped):
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False); slug=models.SlugField(unique=True); name=models.CharField(max_length=160); secret=models.CharField(max_length=255); public_base_url=models.URLField(blank=True); snapshot_url=models.URLField(blank=True); snapshot_token=models.CharField(max_length=255,blank=True); is_active=models.BooleanField(default=True); last_synced_at=models.DateTimeField(null=True,blank=True)

class DealerProfileProjection(Timestamped):
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False); source=models.ForeignKey(IntegrationSource,on_delete=models.PROTECT,related_name="dealers"); external_id=models.UUIDField(); source_version=models.PositiveBigIntegerField(default=0); name=models.CharField(max_length=160); slug=models.SlugField(max_length=180); tagline=models.CharField(max_length=240,blank=True); story=models.TextField(blank=True); email=models.EmailField(blank=True); phone=models.CharField(max_length=40,blank=True); whatsapp=models.CharField(max_length=40,blank=True); address=models.TextField(blank=True); location=models.CharField(max_length=160,blank=True); opening_hours=models.CharField(max_length=240,blank=True); logo_url=models.URLField(blank=True); website_url=models.URLField(blank=True); source_active=models.BooleanField(default=True); marketplace_suspended=models.BooleanField(default=False); raw_payload=models.JSONField(default=dict)
    class Meta:
        constraints=[models.UniqueConstraint(fields=["source","external_id"],name="unique_source_dealer")]; indexes=[models.Index(fields=["marketplace_suspended","source_active","name"])]

class DealerVehicleProjection(Timestamped):
    class Availability(models.TextChoices): AVAILABLE="available","Available"; RESERVED="reserved","Reserved"; SOLD="sold","Sold"
    class Publication(models.TextChoices): PUBLISHED="published","Published"; UNPUBLISHED="unpublished","Unpublished"
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False); source=models.ForeignKey(IntegrationSource,on_delete=models.PROTECT,related_name="vehicles"); external_id=models.UUIDField(); dealer=models.ForeignKey(DealerProfileProjection,on_delete=models.PROTECT,related_name="vehicles"); source_version=models.PositiveBigIntegerField(default=0); title=models.CharField(max_length=240); slug=models.SlugField(max_length=200); make=models.CharField(max_length=80); model=models.CharField(max_length=100); year=models.PositiveSmallIntegerField(); price=models.DecimalField(max_digits=14,decimal_places=2,validators=[MinValueValidator(0)]); currency=models.CharField(max_length=3,default="NGN"); mileage_km=models.PositiveIntegerField(default=0); transmission=models.CharField(max_length=40); fuel_type=models.CharField(max_length=40); condition=models.CharField(max_length=80); location=models.CharField(max_length=160); description=models.TextField(); features=models.JSONField(default=list); known_issues=models.TextField(blank=True); seller_history=models.TextField(blank=True); video_url=models.URLField(blank=True); image_data=models.JSONField(default=list); availability=models.CharField(max_length=16,choices=Availability.choices); publication_status=models.CharField(max_length=16,choices=Publication.choices); source_eligible=models.BooleanField(default=False); raw_payload=models.JSONField(default=dict); source_updated_at=models.DateTimeField(null=True,blank=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=["source","external_id"],name="unique_source_vehicle")]; indexes=[models.Index(fields=["source_eligible","availability","-updated_at"]),models.Index(fields=["dealer","source_version"]),models.Index(fields=["make","model","year"])]

class MarketplaceOwnedVehicle(Timestamped):
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False); title=models.CharField(max_length=240); slug=models.SlugField(unique=True,max_length=200); make=models.CharField(max_length=80); model=models.CharField(max_length=100); year=models.PositiveSmallIntegerField(); price=models.DecimalField(max_digits=14,decimal_places=2,validators=[MinValueValidator(0)]); currency=models.CharField(max_length=3,default="NGN"); mileage_km=models.PositiveIntegerField(default=0); transmission=models.CharField(max_length=40); fuel_type=models.CharField(max_length=40); condition=models.CharField(max_length=80); location=models.CharField(max_length=160); description=models.TextField(); features=models.JSONField(default=list); known_issues=models.TextField(blank=True); seller_history=models.TextField(blank=True); video_url=models.URLField(blank=True); availability=models.CharField(max_length=16,choices=DealerVehicleProjection.Availability.choices,default="available")

class VehicleMedia(Timestamped):
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False); vehicle=models.ForeignKey(MarketplaceOwnedVehicle,on_delete=models.CASCADE,related_name="media"); file=models.ImageField(upload_to="marketplace/%Y/%m/"); alt_text=models.CharField(max_length=180); position=models.PositiveSmallIntegerField(default=0)
    class Meta: ordering=["position","id"]; constraints=[models.UniqueConstraint(fields=["vehicle","position"],name="unique_owned_media_position")]

class MarketplaceListing(Timestamped):
    class Decision(models.TextChoices): PENDING="pending_review","Pending review"; APPROVED="approved","Public"; HIDDEN="hidden","Hidden"; REJECTED="rejected","Rejected"; REMOVED="removed","Removed"; WITHDRAWN="withdrawn","Withdrawn"
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False); imported_vehicle=models.OneToOneField(DealerVehicleProjection,null=True,blank=True,on_delete=models.PROTECT,related_name="listing"); owned_vehicle=models.OneToOneField(MarketplaceOwnedVehicle,null=True,blank=True,on_delete=models.PROTECT,related_name="listing"); decision=models.CharField(max_length=24,choices=Decision.choices,default=Decision.PENDING); is_featured=models.BooleanField(default=False); internal_note=models.TextField(blank=True); reviewed_at=models.DateTimeField(null=True,blank=True); reviewed_by=models.ForeignKey(settings.AUTH_USER_MODEL,null=True,blank=True,on_delete=models.SET_NULL,related_name="reviewed_listings")
    class Meta:
        constraints=[models.CheckConstraint(condition=(Q(imported_vehicle__isnull=False,owned_vehicle__isnull=True)|Q(imported_vehicle__isnull=True,owned_vehicle__isnull=False)),name="listing_exactly_one_owner")]; indexes=[models.Index(fields=["decision","-updated_at"]),models.Index(fields=["is_featured","decision"])]

class ModerationDecision(models.Model):
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False); listing=models.ForeignKey(MarketplaceListing,on_delete=models.PROTECT,related_name="decisions"); actor=models.ForeignKey(settings.AUTH_USER_MODEL,null=True,on_delete=models.SET_NULL); previous=models.CharField(max_length=24); decision=models.CharField(max_length=24,choices=MarketplaceListing.Decision.choices); reason=models.TextField(); correlation_id=models.UUIDField(default=uuid.uuid4); created_at=models.DateTimeField(auto_now_add=True)
    class Meta: ordering=["-created_at"]

class BuyerRequest(Timestamped):
    class Kind(models.TextChoices): INQUIRY="inquiry","Inquiry"; VIEWING="viewing","Viewing / test drive"; OFFER="offer","Offer"
    class Status(models.TextChoices): NEW="new","New"; CONTACTED="contacted","Contacted"; SCHEDULED="scheduled","Scheduled"; CLOSED="closed","Closed"
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False); listing=models.ForeignKey(MarketplaceListing,on_delete=models.PROTECT,related_name="buyer_requests"); kind=models.CharField(max_length=16,choices=Kind.choices); status=models.CharField(max_length=16,choices=Status.choices,default=Status.NEW); name=models.CharField(max_length=120); email=models.EmailField(); phone=models.CharField(max_length=40); message=models.TextField(blank=True); preferred_at=models.DateTimeField(null=True,blank=True); offer_amount=models.DecimalField(max_digits=14,decimal_places=2,null=True,blank=True,validators=[MinValueValidator(1)]); internal_note=models.TextField(blank=True)
    class Meta: indexes=[models.Index(fields=["status","-created_at"]),models.Index(fields=["listing","-created_at"])]

class BuyerRequestActivity(models.Model):
    request=models.ForeignKey(BuyerRequest,on_delete=models.CASCADE,related_name="activities"); actor=models.ForeignKey(settings.AUTH_USER_MODEL,null=True,on_delete=models.SET_NULL); action=models.CharField(max_length=80); note=models.TextField(blank=True); created_at=models.DateTimeField(auto_now_add=True)

class IntegrationInboxEvent(Timestamped):
    class Status(models.TextChoices): RECEIVED="received","Received"; PROCESSING="processing","Processing"; PROCESSED="processed","Processed"; IGNORED="ignored","Ignored"; FAILED="failed","Failed"
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False); source=models.ForeignKey(IntegrationSource,on_delete=models.PROTECT,related_name="events"); event_id=models.UUIDField(); event_type=models.CharField(max_length=80); occurred_at=models.DateTimeField(); payload=models.JSONField(); body_digest=models.CharField(max_length=64); status=models.CharField(max_length=16,choices=Status.choices,default=Status.RECEIVED); attempts=models.PositiveSmallIntegerField(default=0); error=models.TextField(blank=True); next_attempt_at=models.DateTimeField(auto_now_add=True); processed_at=models.DateTimeField(null=True,blank=True); correlation_id=models.UUIDField(default=uuid.uuid4)
    class Meta: constraints=[models.UniqueConstraint(fields=["source","event_id"],name="unique_source_event")]; indexes=[models.Index(fields=["status","next_attempt_at"]),models.Index(fields=["event_type","-created_at"])]

class BackgroundJob(Timestamped):
    class Status(models.TextChoices): QUEUED="queued","Queued"; RUNNING="running","Running"; SUCCEEDED="succeeded","Succeeded"; FAILED="failed","Failed"
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False); kind=models.CharField(max_length=80); payload=models.JSONField(default=dict); status=models.CharField(max_length=16,choices=Status.choices,default=Status.QUEUED); attempts=models.PositiveSmallIntegerField(default=0); max_attempts=models.PositiveSmallIntegerField(default=8); run_after=models.DateTimeField(auto_now_add=True); locked_at=models.DateTimeField(null=True,blank=True); last_error=models.TextField(blank=True); correlation_id=models.UUIDField(default=uuid.uuid4)
    class Meta: indexes=[models.Index(fields=["status","run_after"])]

class ReconciliationRun(Timestamped):
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False); source=models.ForeignKey(IntegrationSource,on_delete=models.PROTECT); status=models.CharField(max_length=24,default="running"); checkpoint=models.JSONField(default=dict); seen_count=models.PositiveIntegerField(default=0); changed_count=models.PositiveIntegerField(default=0); complete=models.BooleanField(default=False); error=models.TextField(blank=True)

class AuditEntry(models.Model):
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False); actor=models.ForeignKey(settings.AUTH_USER_MODEL,null=True,on_delete=models.SET_NULL); action=models.CharField(max_length=100); entity_type=models.CharField(max_length=80); entity_id=models.CharField(max_length=64); changes=models.JSONField(default=dict); correlation_id=models.UUIDField(default=uuid.uuid4); created_at=models.DateTimeField(auto_now_add=True)
    class Meta: indexes=[models.Index(fields=["entity_type","entity_id"]),models.Index(fields=["-created_at"])]
