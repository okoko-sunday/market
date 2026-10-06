from django.db.models import Q
from .models import MarketplaceListing

def eligible_public(include_sold=True):
    imported=Q(imported_vehicle__source_eligible=True,imported_vehicle__dealer__source_active=True,imported_vehicle__dealer__marketplace_suspended=False)
    owned=Q(owned_vehicle__isnull=False)
    qs=MarketplaceListing.objects.filter(decision=MarketplaceListing.Decision.APPROVED).filter(imported|owned).select_related("imported_vehicle__dealer","owned_vehicle").prefetch_related("owned_vehicle__media")
    if not include_sold: qs=qs.exclude(Q(imported_vehicle__availability="sold")|Q(owned_vehicle__availability="sold"))
    return qs

def vehicle_data(listing):
    if listing.imported_vehicle:
        v=listing.imported_vehicle; dealer=v.dealer
        return {"id":str(listing.id),"slug":f"{dealer.slug}-{v.slug}","title":v.title,"make":v.make,"model":v.model,"year":v.year,"price":str(v.price),"currency":v.currency,"mileage_km":v.mileage_km,"transmission":v.transmission,"fuel_type":v.fuel_type,"condition":v.condition,"location":v.location,"description":v.description,"features":v.features,"known_issues":v.known_issues,"seller_history":v.seller_history,"video_url":v.video_url,"images":v.image_data,"availability":v.availability,"is_featured":listing.is_featured,"ownership":"dealer","seller":{"id":str(dealer.id),"slug":dealer.slug,"name":dealer.name,"location":dealer.location or dealer.address,"logo_url":dealer.logo_url,"website_url":dealer.website_url},"updated_at":v.updated_at.isoformat()}
    v=listing.owned_vehicle
    return {"id":str(listing.id),"slug":v.slug,"title":v.title,"make":v.make,"model":v.model,"year":v.year,"price":str(v.price),"currency":v.currency,"mileage_km":v.mileage_km,"transmission":v.transmission,"fuel_type":v.fuel_type,"condition":v.condition,"location":v.location,"description":v.description,"features":v.features,"known_issues":v.known_issues,"seller_history":v.seller_history,"video_url":v.video_url,"images":[{"url":m.file.url,"alt":m.alt_text,"position":m.position} for m in v.media.all()],"availability":v.availability,"is_featured":listing.is_featured,"ownership":"marketplace","seller":{"name":"Motori marketplace"},"updated_at":v.updated_at.isoformat()}
