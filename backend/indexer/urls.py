"""
URL Routing configuration for VayuIndex indexer application.

Configures REST framework DefaultRouter for airports, flight routes,
fare observations, and Laspeyres CPI index time-series endpoints,
plus SSE live stream and macro index summary endpoints.
"""

from typing import List
from django.urls import URLPattern, URLResolver, include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AirportViewSet,
    CPIIndexViewSet,
    FareObservationViewSet,
    RouteViewSet,
    api_status_view,
    chatbot_message_view,
    export_policy_report_view,
    index_summary_view,
    live_fare_stream_view,
    simulate_shock_view,
    whatsapp_webhook_view,
)

router = DefaultRouter()
router.register(r"airports", AirportViewSet, basename="airport")
router.register(r"routes", RouteViewSet, basename="route")
router.register(r"fares", FareObservationViewSet, basename="fare")
router.register(r"cpi-indices", CPIIndexViewSet, basename="cpi-index")

urlpatterns: List[URLPattern | URLResolver] = [
    path("", api_status_view, name="api-root-status"),
    path("fares/live-stream/", live_fare_stream_view, name="live-fare-stream"),
    path("index/summary/", index_summary_view, name="index-summary"),
    path("index/simulate-shock/", simulate_shock_view, name="simulate-shock"),
    path("index/export-policy-report/", export_policy_report_view, name="export-policy-report"),
    path("chatbot/message/", chatbot_message_view, name="chatbot-message"),
    path("webhook/whatsapp/", whatsapp_webhook_view, name="whatsapp-webhook"),
    path("", include(router.urls)),
]
