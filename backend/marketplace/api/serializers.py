from django.utils import timezone
from rest_framework import serializers
from marketplace.models import BuyerRequest,MarketplaceOwnedVehicle,MarketplaceListing,VehicleMedia

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

class VehicleMediaSerializer(serializers.ModelSerializer):
    url=serializers.SerializerMethodField()
    class Meta: model=VehicleMedia; fields=["id","url","alt_text","position"]
    def get_url(self,obj): return obj.file.url

class VehicleMediaUploadSerializer(serializers.ModelSerializer):
    class Meta: model=VehicleMedia; fields=["file","alt_text","position"]
    def validate_file(self,file):
        if file.size>8*1024*1024: raise serializers.ValidationError("Images must not exceed 8 MB.")
        if getattr(file,"content_type","") not in {"image/jpeg","image/png","image/webp"}: raise serializers.ValidationError("Use JPEG, PNG, or WebP.")
        try:
            from PIL import Image
            image=Image.open(file); image.verify()
            if image.width<640 or image.height<360 or image.width>12000 or image.height>12000: raise serializers.ValidationError("Images must be between 640×360 and 12000×12000 pixels.")
            file.seek(0)
        except serializers.ValidationError: raise
        except Exception: raise serializers.ValidationError("The uploaded file is not a valid image.")
        return file
