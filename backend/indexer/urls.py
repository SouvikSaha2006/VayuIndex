from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    RouteViewSet,
    AirfareObservationViewSet,
    CPIAugmentationIndexViewSet,
    api_status_view,
)

router = DefaultRouter()
router.register(r"routes", RouteViewSet, basename="route")
router.register(r"fares", AirfareObservationViewSet, basename="fare")
router.register(r"cpi-indices", CPIAugmentationIndexViewSet, basename="cpi-index")

urlpatterns = [
    path("", api_status_view, name="api-root-status"),
    path("", include(router.urls)),
]
