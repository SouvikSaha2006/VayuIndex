"""
URL configuration for VayuIndex backend.

The `urlpatterns` list routes URLs to views:
    - /       : Health check & service discovery
    - /admin/ : Django Admin interface
    - /api/   : VayuIndex REST Framework API endpoints
"""

from typing import List, Union
from django.contrib import admin
from django.http import HttpRequest, JsonResponse
from django.urls import URLPattern, URLResolver, include, path


def root_health_check(request: HttpRequest) -> JsonResponse:
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


urlpatterns: List[Union[URLPattern, URLResolver]] = [
    path("", root_health_check, name="root-health-check"),
    path("admin/", admin.site.urls),
    path("api/", include("indexer.urls")),
]
