from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    AirportViewSet,
    FlightRouteViewSet,
    FareObservationViewSet,
    DailyCPIIndexViewSet,
    api_status_view,
)

router = DefaultRouter()
router.register(r"airports", AirportViewSet, basename="airport")
router.register(r"routes", FlightRouteViewSet, basename="route")
router.register(r"fares", FareObservationViewSet, basename="fare")
router.register(r"cpi-indices", DailyCPIIndexViewSet, basename="cpi-index")

urlpatterns = [
    path("", api_status_view, name="api-root-status"),
    path("", include(router.urls)),
]
