from django.contrib import admin
from .models import *
for model in [IntegrationSource,DealerProfileProjection,DealerVehicleProjection,MarketplaceOwnedVehicle,VehicleMedia,MarketplaceListing,ModerationDecision,BuyerRequest,BuyerRequestActivity,IntegrationInboxEvent,BackgroundJob,ReconciliationRun,AuditEntry]: admin.site.register(model)
