"""
ViewSets and API views for VayuIndex REST API layer.

Provides optimized viewsets for domestic airports, flight routes, fare observations,
and Laspeyres CPI price index time-series metrics.
"""

import logging
from typing import Any, Optional

from django.db.models import Avg, QuerySet
from rest_framework import status, viewsets
from rest_framework.decorators import action, api_view
from rest_framework.request import Request
from rest_framework.response import Response

from .models import Airport, DailyCPIIndex, FareObservation, FlightRoute
from .serializers import (
    AirportSerializer,
    DailyCPIIndexSerializer,
    FareObservationSerializer,
    FlightRouteSerializer,
)
from .services import ingest_simulated_scraped_fares

logger = logging.getLogger(__name__)


class AirportViewSet(viewsets.ModelViewSet):
    """
    CRUD API endpoints for domestic Indian airports.
    """

    queryset = Airport.objects.all().order_by("iata_code")
    serializer_class = AirportSerializer


class RouteViewSet(viewsets.ModelViewSet):
    """
    CRUD API endpoints for directed domestic flight routes.
    Optimized with select_related on origin and destination foreign keys,
    and annotated with database average observed fare to eliminate N+1 queries.
    """

    queryset = (
        FlightRoute.objects.select_related("origin", "destination")
        .annotate(current_avg_fare=Avg("fares__observed_price_inr"))
        .all()
        .order_by("origin__iata_code", "destination__iata_code")
    )
    serializer_class = FlightRouteSerializer


# Backward compatibility alias
FlightRouteViewSet = RouteViewSet


class FareObservationViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only API endpoints for observed scraped airfares.
    Supports filtering by carrier and route ID.
    Provides custom endpoint to trigger live fare ingestion and index recalculation.
    """

    serializer_class = FareObservationSerializer

    def get_queryset(self) -> QuerySet[FareObservation]:
        """
        Retrieves fare observations optimized with foreign key joins,
        filtered dynamically by carrier and route ID query parameters.
        """
        queryset = (
            FareObservation.objects.select_related(
                "route", "route__origin", "route__destination"
            )
            .all()
            .order_by("-scraped_at")
        )

        carrier = self.request.query_params.get("carrier")
        if carrier:
            queryset = queryset.filter(carrier__iexact=carrier.strip())

        route_param = self.request.query_params.get("route") or self.request.query_params.get("route_id")
        if route_param:
            queryset = queryset.filter(route_id=route_param)

        return queryset

    @action(detail=False, methods=["post"], url_path="trigger-ingestion")
    def trigger_ingestion(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """
        Triggers the simulated fare ingestion pipeline across configured trunk routes,
        persists fresh FareObservation records, and updates the DailyCPIIndex.
        """
        try:
            seed: Optional[int] = None
            if "seed" in request.data and request.data["seed"] is not None:
                seed = int(request.data["seed"])

            use_median: bool = True
            if "use_median" in request.data:
                raw_median = request.data["use_median"]
                if isinstance(raw_median, str):
                    use_median = raw_median.lower() in ("true", "1", "yes")
                else:
                    use_median = bool(raw_median)

            result = ingest_simulated_scraped_fares(
                seed=seed,
                use_median=use_median,
            )
            return Response(result, status=status.HTTP_200_OK)
        except Exception as exc:
            logger.exception("Error executing simulated fare ingestion pipeline")
            return Response(
                {"status": "error", "message": str(exc)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class CPIIndexViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only API endpoints for the daily Laspeyres CPI index time-series.
    Ordered by calculation_date descending.
    Provides custom endpoint for retrieving the latest computed index.
    """

    queryset = DailyCPIIndex.objects.all().order_by("-calculation_date")
    serializer_class = DailyCPIIndexSerializer

    @action(detail=False, methods=["get"], url_path="latest")
    def latest(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """
        Returns the single most recent daily Laspeyres CPI index record.
        """
        latest_record = self.get_queryset().first()
        if not latest_record:
            return Response(
                {"detail": "No CPI index records found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = self.get_serializer(latest_record)
        return Response(serializer.data, status=status.HTTP_200_OK)


# Backward compatibility alias
DailyCPIIndexViewSet = CPIIndexViewSet


@api_view(["GET"])
def api_status_view(request: Request) -> Response:
    """API Root discovery and status endpoint."""
    return Response(
        {
            "service": "VayuIndex API",
            "description": "Domestic Indian Airfare Volatility & CPI Augmentation Engine",
            "version": "1.0.0",
            "status": "operational",
            "endpoints": {
                "airports": "/api/airports/",
                "routes": "/api/routes/",
                "fares": "/api/fares/",
                "fares_trigger_ingestion": "/api/fares/trigger-ingestion/",
                "cpi_indices": "/api/cpi-indices/",
                "cpi_indices_latest": "/api/cpi-indices/latest/",
            },
        }
    )
