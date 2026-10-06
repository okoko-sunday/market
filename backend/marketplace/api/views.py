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
from django.utils.dateparse import parse_datetime
from rest_framework import status
from rest_framework.decorators import api_view,permission_classes,throttle_classes
from rest_framework.permissions import IsAdminUser,AllowAny,DjangoModelPermissions
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from marketplace.catalog import eligible_public,vehicle_data
from marketplace.integration import validate_envelope
from marketplace.models import IntegrationSource,IntegrationInboxEvent,BackgroundJob,DealerProfileProjection,MarketplaceListing,BuyerRequest,AuditEntry,MarketplaceOwnedVehicle
from marketplace.moderation import decide
from .serializers import BuyerRequestSerializer,OwnedVehicleSerializer

@ensure_csrf_cookie
def csrf(request): return JsonResponse({"csrf":"set"})

@csrf_protect
def session_login(request):
    if request.method!="POST": return JsonResponse({"error":{"code":"method_not_allowed"}},status=405)
    try: data=json.loads(request.body)
    except ValueError: return JsonResponse({"error":{"code":"invalid_json"}},status=400)
    user=authenticate(request,username=data.get("username",""),password=data.get("password",""))
    if not user or not user.is_staff: return JsonResponse({"error":{"code":"invalid_credentials","detail":"Check your staff username and password."}},status=401)
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
    for key,lookup in {"make":"iexact","model":"iexact","location":"icontains","transmission":"iexact","fuel_type":"iexact","condition":"iexact"}.items():
        if value:=request.GET.get(key): qs=qs.filter(Q(**{f"imported_vehicle__{key}__{lookup}":value})|Q(**{f"owned_vehicle__{key}__{lookup}":value}))
    if q:=request.GET.get("q"): qs=qs.filter(Q(imported_vehicle__title__icontains=q)|Q(owned_vehicle__title__icontains=q))
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

def sitemap(request):
    origin=request.build_absolute_uri("/").rstrip("/"); urls=[f"{origin}/vehicles/{x.id}" for x in eligible_public()]
    body='<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'+''.join(f'<url><loc>{u}</loc></url>' for u in urls)+'</urlset>'
    return HttpResponse(body,content_type="application/xml")
