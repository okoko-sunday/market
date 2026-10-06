import hashlib,hmac,json,uuid
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse,HttpResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from django.contrib.auth import authenticate, login, logout
from django.core.cache import cache
from django.db import connection
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework import status
from rest_framework.decorators import api_view,permission_classes,throttle_classes
from rest_framework.permissions import IsAdminUser,AllowAny,DjangoModelPermissions
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from marketplace.catalog import eligible_public,vehicle_data
from marketplace.integration import validate_envelope
from marketplace.models import IntegrationSource,IntegrationInboxEvent,BackgroundJob,DealerProfileProjection,MarketplaceListing,BuyerRequest,BuyerRequestActivity,AuditEntry,MarketplaceOwnedVehicle,VehicleMedia,ReconciliationRun
from marketplace.moderation import decide
from .serializers import BuyerRequestSerializer,OwnedVehicleSerializer,VehicleMediaSerializer,VehicleMediaUploadSerializer

@ensure_csrf_cookie
def csrf(request): return JsonResponse({"csrf":"set"})

@csrf_protect
def session_login(request):
    if request.method!="POST": return JsonResponse({"error":{"code":"method_not_allowed"}},status=405)
    throttle_key=f"staff-login:{request.META.get('REMOTE_ADDR','unknown')}"
    attempts=cache.get(throttle_key,0)
    if attempts>=10: return JsonResponse({"error":{"code":"rate_limited","detail":"Too many sign-in attempts. Try again later."}},status=429)
    try: data=json.loads(request.body)
    except ValueError: return JsonResponse({"error":{"code":"invalid_json"}},status=400)
    user=authenticate(request,username=data.get("username",""),password=data.get("password",""))
    if not user or not user.is_staff:
        cache.set(throttle_key,attempts+1,3600)
        return JsonResponse({"error":{"code":"invalid_credentials","detail":"Check your staff username and password."}},status=401)
    cache.delete(throttle_key)
    login(request,user); return JsonResponse({"user":{"name":user.get_full_name() or user.username}})

@csrf_protect
def session_logout(request):
    if request.method!="POST": return JsonResponse({"error":{"code":"method_not_allowed"}},status=405)
    logout(request); return JsonResponse({"status":"signed_out"})

@api_view(["GET"])
@permission_classes([IsAdminUser])
def session_me(request): return Response({"user":{"name":request.user.get_full_name() or request.user.username,"permissions":sorted(request.user.get_all_permissions())}})

def page_response(request,items,serialize):
    try: size=min(max(int(request.GET.get("page_size",12)),1),48); number=max(int(request.GET.get("page",1)),1)
    except ValueError: return Response({"error":{"code":"invalid_pagination","detail":"page and page_size must be integers"}},status=400)
    page=Paginator(items,size).get_page(number)
    return Response({"count":page.paginator.count,"page":page.number,"pages":page.paginator.num_pages,"results":[serialize(x) for x in page.object_list]})

@api_view(["GET"])
def vehicles(request):
    qs=eligible_public(include_sold=request.GET.get("availability")!="available")
    if request.GET.get("featured") in {"1","true"}: qs=qs.filter(is_featured=True)
    for key,lookup in {"make":"iexact","model":"iexact","location":"icontains","transmission":"iexact","fuel_type":"iexact","condition":"iexact"}.items():
        if value:=request.GET.get(key): qs=qs.filter(Q(**{f"imported_vehicle__{key}__{lookup}":value})|Q(**{f"owned_vehicle__{key}__{lookup}":value}))
    if q:=request.GET.get("q"):
        if connection.vendor=="postgresql":
            from django.contrib.postgres.search import SearchQuery,SearchRank,SearchVector
            vector=SearchVector("imported_vehicle__title",weight="A")+SearchVector("imported_vehicle__description",weight="B")+SearchVector("owned_vehicle__title",weight="A")+SearchVector("owned_vehicle__description",weight="B")
            qs=qs.annotate(search=vector,rank=SearchRank(vector,SearchQuery(q))).filter(search=SearchQuery(q))
        else: qs=qs.filter(Q(imported_vehicle__title__icontains=q)|Q(imported_vehicle__description__icontains=q)|Q(owned_vehicle__title__icontains=q)|Q(owned_vehicle__description__icontains=q))
    if value:=request.GET.get("min_price"): qs=qs.filter(Q(imported_vehicle__price__gte=value)|Q(owned_vehicle__price__gte=value))
    if value:=request.GET.get("max_price"): qs=qs.filter(Q(imported_vehicle__price__lte=value)|Q(owned_vehicle__price__lte=value))
    if value:=request.GET.get("min_year"): qs=qs.filter(Q(imported_vehicle__year__gte=value)|Q(owned_vehicle__year__gte=value))
    ordering={"newest":"-updated_at","price_asc":"imported_vehicle__price","price_desc":"-imported_vehicle__price","year_desc":"-imported_vehicle__year"}.get(request.GET.get("sort","newest"),"-updated_at")
    return page_response(request,qs.order_by(ordering,"id"),vehicle_data)

@api_view(["GET"])
def vehicle_detail(request,listing_id): return Response(vehicle_data(get_object_or_404(eligible_public(),id=listing_id)))

@api_view(["GET"])
def dealers(request):
    qs=DealerProfileProjection.objects.filter(source_active=True,marketplace_suspended=False,vehicles__listing__decision="approved",vehicles__source_eligible=True).distinct().order_by("name")
    return page_response(request,qs,lambda d:{"id":str(d.id),"slug":d.slug,"name":d.name,"tagline":d.tagline,"location":d.location or d.address,"logo_url":d.logo_url,"website_url":d.website_url})

@api_view(["GET"])
def dealer_detail(request,slug):
    d=get_object_or_404(DealerProfileProjection,slug=slug,source_active=True,marketplace_suspended=False)
    cars=eligible_public().filter(imported_vehicle__dealer=d).order_by("-updated_at")[:24]
    return Response({"dealer":{"id":str(d.id),"slug":d.slug,"name":d.name,"tagline":d.tagline,"story":d.story,"location":d.location or d.address,"logo_url":d.logo_url,"website_url":d.website_url,"phone":d.phone},"vehicles":[vehicle_data(x) for x in cars]})

class BuyerThrottle(ScopedRateThrottle): scope="buyer"
@api_view(["POST"])
@throttle_classes([BuyerThrottle])
def buyer_request(request):
    s=BuyerRequestSerializer(data=request.data); s.is_valid(raise_exception=True); obj=s.save()
    AuditEntry.objects.create(action="buyer_request.created",entity_type="buyer_request",entity_id=str(obj.id),changes={"kind":obj.kind,"listing":str(obj.listing_id)})
    return Response({"id":obj.id,"message":"Request received. Motori support will contact you and coordinate with the seller. This does not complete a sale."},status=201)

@csrf_exempt
def dealer_event(request):
    if request.method!="POST": return JsonResponse({"error":{"code":"method_not_allowed"}},status=405)
    if len(request.body)>1024*1024: return JsonResponse({"error":{"code":"payload_too_large"}},status=413)
    slug=request.headers.get("X-Integration-Source",settings.INTEGRATION_SOURCE_SLUG)
    source=IntegrationSource.objects.filter(slug=slug,is_active=True).first()
    signature=request.headers.get("X-Showroom-Signature",""); expected="sha256="+hmac.new((source.secret if source else "").encode(),request.body,hashlib.sha256).hexdigest()
    if not source or not hmac.compare_digest(signature,expected): return JsonResponse({"error":{"code":"invalid_signature"}},status=401)
    try:
        envelope=validate_envelope(json.loads(request.body)); header_id=request.headers.get("X-Event-ID"); event_uuid=uuid.UUID(str(envelope["event_id"])); occurred=parse_datetime(envelope["occurred_at"])
        if not header_id or str(event_uuid)!=header_id or not occurred: raise ValidationError("Event identifiers or occurred_at are invalid.")
    except Exception as exc: return JsonResponse({"error":{"code":"invalid_event","detail":str(exc)}},status=400)
    digest=hashlib.sha256(request.body).hexdigest()
    with transaction.atomic():
        existing=IntegrationInboxEvent.objects.select_for_update().filter(source=source,event_id=event_uuid).first()
        if existing:
            if existing.body_digest!=digest: return JsonResponse({"error":{"code":"event_id_reused"}},status=409)
            return JsonResponse({"status":"duplicate","event_id":str(event_uuid)},status=200)
        event=IntegrationInboxEvent.objects.create(source=source,event_id=event_uuid,event_type=envelope["event_type"],occurred_at=occurred,payload=envelope["data"],body_digest=digest)
        BackgroundJob.objects.create(kind="process_inbox_event",payload={"event_id":str(event.id)},correlation_id=event.correlation_id)
    return JsonResponse({"status":"accepted","event_id":str(event_uuid)},status=202)

@api_view(["GET"])
@permission_classes([IsAdminUser])
def staff_overview(request):
    counts={key:MarketplaceListing.objects.filter(decision=key).count() for key,_ in MarketplaceListing.Decision.choices}
    counts.update({"reserved":MarketplaceListing.objects.filter(imported_vehicle__availability="reserved").count(),"sold":MarketplaceListing.objects.filter(imported_vehicle__availability="sold").count()})
    return Response({"counts":counts,"sync_failures":IntegrationInboxEvent.objects.filter(status="failed").count(),"buyer_requests":BuyerRequest.objects.filter(status="new").count()})

@api_view(["GET"])
@permission_classes([IsAdminUser])
def staff_listings(request):
    qs=MarketplaceListing.objects.select_related("imported_vehicle__dealer","owned_vehicle").order_by("-updated_at")
    if request.GET.get("decision"): qs=qs.filter(decision=request.GET["decision"])
    return page_response(request,qs,lambda x:{**vehicle_data(x),"decision":x.decision,"source_version":x.imported_vehicle.source_version if x.imported_vehicle else None,"internal_note":x.internal_note})

@api_view(["GET"])
@permission_classes([IsAdminUser])
def staff_listing_detail(request,listing_id):
    listing=get_object_or_404(MarketplaceListing.objects.select_related("imported_vehicle__dealer","owned_vehicle"),id=listing_id)
    return Response({**vehicle_data(listing),"decision":listing.decision,"source_version":listing.imported_vehicle.source_version if listing.imported_vehicle else None,"internal_note":listing.internal_note,"moderation_history":[{"id":str(x.id),"previous":x.previous,"decision":x.decision,"reason":x.reason,"actor":x.actor.get_username() if x.actor else None,"created_at":x.created_at} for x in listing.decisions.select_related("actor").all()[:100]]})

@api_view(["POST"])
@permission_classes([IsAdminUser])
def staff_moderate(request,listing_id):
    if not request.user.has_perm("marketplace.change_marketplacelisting"): return Response({"error":{"code":"forbidden"}},status=403)
    try: listing=decide(listing_id,request.data.get("decision"),request.data.get("reason","").strip(),request.user)
    except (ValueError,MarketplaceListing.DoesNotExist) as exc: return Response({"error":{"code":"invalid_decision","detail":str(exc)}},status=400)
    return Response({"id":listing.id,"decision":listing.decision})

@api_view(["GET","POST"])
@permission_classes([IsAdminUser])
def staff_owned(request):
    if request.method=="GET": return page_response(request,MarketplaceOwnedVehicle.objects.order_by("-updated_at"),lambda v:OwnedVehicleSerializer(v).data)
    if not request.user.has_perm("marketplace.add_marketplaceownedvehicle"): return Response(status=403)
    s=OwnedVehicleSerializer(data=request.data); s.is_valid(raise_exception=True); return Response(OwnedVehicleSerializer(s.save()).data,status=201)

@api_view(["GET","PATCH"])
@permission_classes([IsAdminUser])
def staff_owned_detail(request,vehicle_id):
    vehicle=get_object_or_404(MarketplaceOwnedVehicle,id=vehicle_id)
    if request.method=="GET": return Response({**OwnedVehicleSerializer(vehicle).data,"media":VehicleMediaSerializer(vehicle.media.all(),many=True).data})
    if not request.user.has_perm("marketplace.change_marketplaceownedvehicle"): return Response(status=403)
    serializer=OwnedVehicleSerializer(vehicle,data=request.data,partial=True); serializer.is_valid(raise_exception=True); vehicle=serializer.save()
    AuditEntry.objects.create(actor=request.user,action="owned_vehicle.updated",entity_type="owned_vehicle",entity_id=str(vehicle.id),changes=list(serializer.validated_data.keys()))
    return Response(OwnedVehicleSerializer(vehicle).data)

@api_view(["POST"])
@permission_classes([IsAdminUser])
def staff_owned_media(request,vehicle_id):
    if not request.user.has_perm("marketplace.add_vehiclemedia"): return Response(status=403)
    vehicle=get_object_or_404(MarketplaceOwnedVehicle,id=vehicle_id)
    serializer=VehicleMediaUploadSerializer(data=request.data); serializer.is_valid(raise_exception=True)
    if vehicle.media.count()>=30: return Response({"error":{"code":"gallery_limit","detail":"A vehicle can have up to 30 images."}},status=400)
    media=serializer.save(vehicle=vehicle); AuditEntry.objects.create(actor=request.user,action="owned_vehicle.media_added",entity_type="owned_vehicle",entity_id=str(vehicle.id),changes={"media_id":str(media.id)})
    return Response(VehicleMediaSerializer(media).data,status=201)

@api_view(["PATCH","DELETE"])
@permission_classes([IsAdminUser])
def staff_owned_media_detail(request,vehicle_id,media_id):
    media=get_object_or_404(VehicleMedia,vehicle_id=vehicle_id,id=media_id)
    if request.method=="DELETE":
        if not request.user.has_perm("marketplace.delete_vehiclemedia"): return Response(status=403)
        media.delete(); AuditEntry.objects.create(actor=request.user,action="owned_vehicle.media_removed",entity_type="owned_vehicle",entity_id=str(vehicle_id),changes={"media_id":str(media_id)}); return Response(status=204)
    if not request.user.has_perm("marketplace.change_vehiclemedia"): return Response(status=403)
    serializer=VehicleMediaUploadSerializer(media,data={k:v for k,v in request.data.items() if k in {"alt_text","position"}},partial=True); serializer.is_valid(raise_exception=True); return Response(VehicleMediaSerializer(serializer.save()).data)

@api_view(["GET","PATCH"])
@permission_classes([IsAdminUser])
def staff_buyer_requests(request,request_id=None):
    if request.method=="GET":
        qs=BuyerRequest.objects.select_related("listing","listing__imported_vehicle__dealer").order_by("-created_at")
        if request.GET.get("status"): qs=qs.filter(status=request.GET["status"])
        return page_response(request,qs,lambda x:{"id":str(x.id),"listing":str(x.listing_id),"vehicle":vehicle_data(x.listing)["title"],"seller":vehicle_data(x.listing)["seller"]["name"],"kind":x.kind,"status":x.status,"name":x.name,"email":x.email,"phone":x.phone,"message":x.message,"preferred_at":x.preferred_at,"offer_amount":str(x.offer_amount) if x.offer_amount else None,"internal_note":x.internal_note,"created_at":x.created_at,"activities":[{"action":a.action,"note":a.note,"actor":a.actor.get_username() if a.actor else None,"created_at":a.created_at} for a in x.activities.select_related("actor").all()]})
    if not request.user.has_perm("marketplace.change_buyerrequest"): return Response(status=403)
    item=get_object_or_404(BuyerRequest,id=request_id); allowed={k:v for k,v in request.data.items() if k in {"status","internal_note"}}
    if "status" in allowed and allowed["status"] not in dict(BuyerRequest.Status.choices): return Response({"error":{"code":"invalid_status"}},status=400)
    previous=item.status
    for k,v in allowed.items(): setattr(item,k,v)
    item.save(); BuyerRequestActivity.objects.create(request=item,actor=request.user,action="status_changed" if previous!=item.status else "note_updated",note=request.data.get("activity_note",""))
    AuditEntry.objects.create(actor=request.user,action="buyer_request.updated",entity_type="buyer_request",entity_id=str(item.id),changes={"status":{"from":previous,"to":item.status}})
    return Response({"id":item.id,"status":item.status})

@api_view(["GET","PATCH"])
@permission_classes([IsAdminUser])
def staff_dealers(request,dealer_id=None):
    if request.method=="GET":
        return page_response(request,DealerProfileProjection.objects.order_by("name"),lambda d:{"id":str(d.id),"name":d.name,"slug":d.slug,"source_active":d.source_active,"marketplace_suspended":d.marketplace_suspended,"last_source_update":d.updated_at,"public_inventory":d.vehicles.filter(source_eligible=True,listing__decision="approved").count()})
    if not request.user.has_perm("marketplace.change_dealerprofileprojection"): return Response(status=403)
    dealer=get_object_or_404(DealerProfileProjection,id=dealer_id); suspended=request.data.get("marketplace_suspended")
    if not isinstance(suspended,bool): return Response({"error":{"code":"invalid_suspension"}},status=400)
    dealer.marketplace_suspended=suspended; dealer.save(update_fields=["marketplace_suspended","updated_at"]); AuditEntry.objects.create(actor=request.user,action="dealer.suspended" if suspended else "dealer.restored",entity_type="dealer",entity_id=str(dealer.id),changes={"marketplace_suspended":suspended}); return Response({"id":dealer.id,"marketplace_suspended":suspended})

@api_view(["GET","POST"])
@permission_classes([IsAdminUser])
def staff_integration_events(request,event_id=None):
    if request.method=="POST":
        if not request.user.has_perm("marketplace.change_integrationinboxevent"): return Response(status=403)
        event=get_object_or_404(IntegrationInboxEvent,id=event_id); event.status="received"; event.error=""; event.next_attempt_at=timezone.now(); event.save(); BackgroundJob.objects.create(kind="process_inbox_event",payload={"event_id":str(event.id)},correlation_id=event.correlation_id); return Response({"status":"queued"},status=202)
    qs=IntegrationInboxEvent.objects.select_related("source").order_by("-created_at")
    if request.GET.get("status"): qs=qs.filter(status=request.GET["status"])
    return page_response(request,qs,lambda e:{"id":str(e.id),"event_id":str(e.event_id),"source":e.source.slug,"event_type":e.event_type,"status":e.status,"attempts":e.attempts,"error":e.error,"correlation_id":str(e.correlation_id),"created_at":e.created_at,"processed_at":e.processed_at})

@api_view(["GET"])
@permission_classes([IsAdminUser])
def staff_reconciliations(request): return page_response(request,ReconciliationRun.objects.select_related("source").order_by("-created_at"),lambda x:{"id":str(x.id),"source":x.source.slug,"status":x.status,"seen_count":x.seen_count,"changed_count":x.changed_count,"complete":x.complete,"checkpoint":x.checkpoint,"error":x.error,"created_at":x.created_at})

@api_view(["POST"])
@permission_classes([IsAdminUser])
def staff_reconcile(request):
    if not request.user.has_perm("marketplace.change_integrationinboxevent"): return Response(status=403)
    source=get_object_or_404(IntegrationSource,slug=request.data.get("source",settings.INTEGRATION_SOURCE_SLUG),is_active=True)
    if not source.snapshot_url or not source.snapshot_token: return Response({"error":{"code":"snapshot_not_configured"}},status=409)
    job=BackgroundJob.objects.create(kind="reconcile_source",payload={"source":source.slug})
    AuditEntry.objects.create(actor=request.user,action="reconciliation.queued",entity_type="integration_source",entity_id=str(source.id),changes={"job_id":str(job.id)})
    return Response({"job_id":job.id,"status":"queued"},status=202)

@api_view(["GET"])
@permission_classes([IsAdminUser])
def staff_audit(request):
    return page_response(request,AuditEntry.objects.select_related("actor").order_by("-created_at"),lambda x:{"id":str(x.id),"actor":x.actor.get_username() if x.actor else None,"action":x.action,"entity_type":x.entity_type,"entity_id":x.entity_id,"changes":x.changes,"correlation_id":str(x.correlation_id),"created_at":x.created_at})

def sitemap(request):
    origin=request.build_absolute_uri("/").rstrip("/"); urls=[f"{origin}/vehicles/{x.id}" for x in eligible_public()]
    body='<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'+''.join(f'<url><loc>{u}</loc></url>' for u in urls)+'</urlset>'
    return HttpResponse(body,content_type="application/xml")
