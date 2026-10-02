"""
URL configuration for VayuIndex backend.

The `urlpatterns` list routes URLs to views:
    - /admin/ : Django Admin interface
    - /api/   : VayuIndex REST Framework API endpoints
"""

from django.contrib import admin
from django.urls import path, include
from django.http import JsonResponse


def root_health_check(request):
    """Simple health check and API discovery endpoint."""
    return JsonResponse(
        {
            "service": "VayuIndex API",
            "description": "Domestic Indian Airfare Volatility & CPI Augmentation Engine",
            "status": "healthy",
            "endpoints": {
                "admin": "/admin/",
                "api": "/api/",
            },
        }
    )


urlpatterns = [
    path("", root_health_check, name="root-health-check"),
    path("admin/", admin.site.urls),
    path("api/", include("indexer.urls")),
]
