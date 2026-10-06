from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path
from django.db import connection
def health(_): return JsonResponse({"status":"ok"})
def ready(_):
    try:
        with connection.cursor() as c: c.execute("SELECT 1")
        return JsonResponse({"status":"ready"})
    except Exception: return JsonResponse({"status":"unavailable"},status=503)
urlpatterns=[path("admin/",admin.site.urls),path("health/",health),path("ready/",ready),path("api/",include("marketplace.urls"))]
