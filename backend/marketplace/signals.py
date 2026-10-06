from django.conf import settings
from django.contrib.auth.models import Group, Permission
from django.db.models.signals import post_migrate
from django.dispatch import receiver
from .models import IntegrationSource

@receiver(post_migrate)
def ensure_local_source(sender, **kwargs):
    if sender.name != "marketplace": return
    source,_=IntegrationSource.objects.get_or_create(slug=settings.INTEGRATION_SOURCE_SLUG,defaults={"name":"Dealer platform","secret":settings.INTEGRATION_WEBHOOK_SECRET,"public_base_url":settings.INTEGRATION_PUBLIC_BASE_URL,"snapshot_url":settings.INTEGRATION_SNAPSHOT_URL,"snapshot_token":settings.INTEGRATION_SNAPSHOT_TOKEN})
    changed=[]
    for field,value in {"public_base_url":settings.INTEGRATION_PUBLIC_BASE_URL,"snapshot_url":settings.INTEGRATION_SNAPSHOT_URL,"snapshot_token":settings.INTEGRATION_SNAPSHOT_TOKEN}.items():
        if value and getattr(source,field)!=value: setattr(source,field,value); changed.append(field)
    if changed: source.save(update_fields=changed+["updated_at"])
    matrix={
        "Platform administrator":["add_marketplaceownedvehicle","change_marketplaceownedvehicle","change_marketplacelisting","change_dealerprofileprojection","change_buyerrequest","change_integrationinboxevent"],
        "Moderator":["change_marketplacelisting","change_dealerprofileprojection"],
        "Inventory manager":["add_marketplaceownedvehicle","change_marketplaceownedvehicle","add_vehiclemedia","change_vehiclemedia"],
        "Support operator":["view_buyerrequest","change_buyerrequest","add_buyerrequestactivity"],
        "Read-only analyst":["view_marketplacelisting","view_dealerprofileprojection","view_dealervehicleprojection","view_buyerrequest","view_integrationinboxevent","view_auditentry"],
    }
    for name,codes in matrix.items():
        group,_=Group.objects.get_or_create(name=name); group.permissions.set(Permission.objects.filter(content_type__app_label="marketplace",codename__in=codes))
