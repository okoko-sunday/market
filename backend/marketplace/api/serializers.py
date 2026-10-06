from django.utils import timezone
from rest_framework import serializers
from marketplace.models import BuyerRequest,MarketplaceOwnedVehicle,MarketplaceListing

class BuyerRequestSerializer(serializers.ModelSerializer):
    class Meta: model=BuyerRequest; fields=["id","listing","kind","name","email","phone","message","preferred_at","offer_amount","created_at"]; read_only_fields=["id","created_at"]
    def validate(self,data):
        listing=data["listing"]
        from marketplace.catalog import eligible_public
        if not eligible_public(include_sold=False).filter(id=listing.id).exists(): raise serializers.ValidationError("This vehicle is not available for requests.")
        if data["kind"]=="offer" and not data.get("offer_amount"): raise serializers.ValidationError({"offer_amount":"An offer amount is required."})
        if data["kind"]=="viewing" and (not data.get("preferred_at") or data["preferred_at"]<=timezone.now()): raise serializers.ValidationError({"preferred_at":"Choose a future time."})
        return data

class OwnedVehicleSerializer(serializers.ModelSerializer):
    listing_id=serializers.UUIDField(source="listing.id",read_only=True)
    class Meta: model=MarketplaceOwnedVehicle; fields="__all__"
    def create(self,validated):
        vehicle=super().create(validated); MarketplaceListing.objects.create(owned_vehicle=vehicle); return vehicle
