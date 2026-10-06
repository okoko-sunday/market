from django.db import transaction
from django.utils import timezone
from .models import MarketplaceListing,ModerationDecision,AuditEntry

@transaction.atomic
def decide(listing_id,decision,reason,actor):
    listing=MarketplaceListing.objects.select_for_update().get(id=listing_id)
    if decision not in dict(MarketplaceListing.Decision.choices): raise ValueError("Invalid decision")
    if listing.imported_vehicle and decision==MarketplaceListing.Decision.APPROVED and not listing.imported_vehicle.source_eligible: raise ValueError("Source is not eligible for publication")
    previous=listing.decision; listing.decision=decision; listing.reviewed_at=timezone.now(); listing.reviewed_by=actor; listing.save(update_fields=["decision","reviewed_at","reviewed_by","updated_at"])
    record=ModerationDecision.objects.create(listing=listing,actor=actor,previous=previous,decision=decision,reason=reason)
    AuditEntry.objects.create(actor=actor,action=f"listing.{decision}",entity_type="listing",entity_id=str(listing.id),changes={"from":previous,"to":decision,"reason":reason},correlation_id=record.correlation_id)
    return listing
