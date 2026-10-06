import json
from decimal import Decimal, InvalidOperation
from urllib.parse import urljoin, urlparse
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from .models import DealerProfileProjection,DealerVehicleProjection,MarketplaceListing,IntegrationInboxEvent,AuditEntry

EVENTS={"dealer.created.v1","dealer.updated.v1","vehicle.published.v1","vehicle.updated.v1","vehicle.availability_changed.v1","vehicle.sold.v1","vehicle.withdrawn.v1"}
REQUIRED_VEHICLE={"id","dealer_id","version","title","slug","make","model","year","price","currency","mileage_km","transmission","fuel_type","condition","location","description","availability","publication_status","updated_at"}

def validate_envelope(envelope):
    if not isinstance(envelope,dict) or set(("event_id","event_type","occurred_at","data"))-set(envelope): raise ValidationError("Envelope requires event_id, event_type, occurred_at and data.")
    if envelope["event_type"] not in EVENTS: raise ValidationError("Unsupported event type.")
    if not isinstance(envelope["data"],dict): raise ValidationError("data must be an object.")
    if envelope["event_type"].startswith("vehicle.") and REQUIRED_VEHICLE-set(envelope["data"]): raise ValidationError("Vehicle snapshot is missing required fields.")
    return envelope

def safe_media_url(source,url):
    absolute=urljoin(source.public_base_url.rstrip("/")+"/",url)
    parsed=urlparse(absolute)
    if parsed.scheme not in {"http","https"}: raise ValidationError("Unsupported media URL.")
    return absolute

@transaction.atomic
def process_event(event_id):
    event=IntegrationInboxEvent.objects.select_for_update().select_related("source").get(id=event_id)
    if event.status in {event.Status.PROCESSED,event.Status.IGNORED}: return event
    event.status=event.Status.PROCESSING; event.attempts+=1; event.save(update_fields=["status","attempts","updated_at"])
    try:
        if event.event_type.startswith("dealer."): _apply_dealer(event)
        else: _apply_vehicle(event)
        event.status=event.Status.PROCESSED; event.error=""; event.processed_at=timezone.now()
    except StaleEvent:
        event.status=event.Status.IGNORED; event.error="stale source version"; event.processed_at=timezone.now()
    except Exception as exc:
        event.status=event.Status.FAILED; event.error=str(exc)[:2000]; event.next_attempt_at=timezone.now()+timezone.timedelta(minutes=min(2**event.attempts,60)); event.save(); raise
    event.save(); event.source.last_synced_at=timezone.now(); event.source.save(update_fields=["last_synced_at","updated_at"]); return event

class StaleEvent(Exception): pass

def _apply_dealer(event):
    d=event.payload; ext=d["id"]; version=int(d["version"])
    dealer=DealerProfileProjection.objects.select_for_update().filter(source=event.source,external_id=ext).first()
    if dealer and dealer.source_version>=version: raise StaleEvent
    values={"source_version":version,"name":d["name"],"slug":d["slug"],"tagline":d.get("tagline",""),"story":d.get("story",""),"email":d.get("email",""),"phone":d.get("phone",""),"whatsapp":d.get("whatsapp",""),"address":d.get("address",""),"location":d.get("location",""),"opening_hours":d.get("opening_hours",""),"logo_url":safe_media_url(event.source,d["logo_url"]) if d.get("logo_url") else "","website_url":d.get("website_url",d.get("domain_url","")),"source_active":bool(d.get("is_active",True)),"raw_payload":d}
    if dealer:
        for k,v in values.items(): setattr(dealer,k,v)
        dealer.save()
    else: DealerProfileProjection.objects.create(source=event.source,external_id=ext,**values)

def _apply_vehicle(event):
    d=event.payload; version=int(d["version"])
    try: price=Decimal(str(d["price"])); updated=parse_datetime(d["updated_at"])
    except (InvalidOperation,TypeError): raise ValidationError("Invalid vehicle price or updated_at.")
    dealer,_=DealerProfileProjection.objects.get_or_create(source=event.source,external_id=d["dealer_id"],defaults={"name":"Incomplete dealer profile","slug":f"pending-{str(d['dealer_id'])[:8]}","source_version":0,"source_active":False})
    vehicle=DealerVehicleProjection.objects.select_for_update().filter(source=event.source,external_id=d["id"]).first()
    if vehicle and vehicle.dealer_id!=dealer.id: raise ValidationError("Vehicle dealer identity cannot be reassigned.")
    if vehicle and vehicle.source_version>=version: raise StaleEvent
    availability="sold" if event.event_type=="vehicle.sold.v1" else d["availability"]
    if availability not in dict(DealerVehicleProjection.Availability.choices): raise ValidationError("Invalid availability.")
    publication=d["publication_status"]
    if publication not in {"published","unpublished"}: raise ValidationError("Invalid publication status.")
    images=[]
    for image in d.get("images",[]): images.append({"url":safe_media_url(event.source,image["url"]),"alt":image.get("alt",d["title"]),"position":int(image.get("position",0))})
    source_eligible=publication=="published" and event.event_type!="vehicle.withdrawn.v1"
    values={"dealer":dealer,"source_version":version,"title":d["title"],"slug":d["slug"],"make":d["make"],"model":d["model"],"year":int(d["year"]),"price":price,"currency":d["currency"],"mileage_km":int(d["mileage_km"]),"transmission":d["transmission"],"fuel_type":d["fuel_type"],"condition":d["condition"],"location":d["location"],"description":d["description"],"features":d.get("features",[]),"known_issues":d.get("known_issues",""),"seller_history":d.get("seller_history",""),"video_url":d.get("video_url",""),"image_data":images,"availability":availability,"publication_status":publication,"source_eligible":source_eligible,"raw_payload":d,"source_updated_at":updated}
    created=vehicle is None
    if created: vehicle=DealerVehicleProjection.objects.create(source=event.source,external_id=d["id"],**values)
    else:
        for k,v in values.items(): setattr(vehicle,k,v)
        vehicle.save()
    listing,_=MarketplaceListing.objects.select_for_update().get_or_create(imported_vehicle=vehicle,defaults={"decision":MarketplaceListing.Decision.PENDING})
    if event.event_type=="vehicle.withdrawn.v1": listing.decision=MarketplaceListing.Decision.WITHDRAWN; listing.save(update_fields=["decision","updated_at"])
    elif not created and listing.decision==MarketplaceListing.Decision.WITHDRAWN and source_eligible:
        listing.decision=MarketplaceListing.Decision.PENDING; listing.save(update_fields=["decision","updated_at"])
    AuditEntry.objects.create(action=f"integration.{event.event_type}",entity_type="vehicle",entity_id=str(vehicle.id),changes={"source_version":version},correlation_id=event.correlation_id)
