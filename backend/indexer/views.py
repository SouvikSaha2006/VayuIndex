"""
ViewSets and API views for VayuIndex REST API layer.

Provides optimized viewsets for domestic airports, flight routes, fare observations,
and Laspeyres CPI price index time-series metrics, as well as real-time SSE streaming,
source-destination route search, and macro summary endpoints.
"""

import json
import logging
import random
import time
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional

from django.db.models import Avg, Max, Min, Q, QuerySet
from django.http import HttpRequest, StreamingHttpResponse
from django.utils import timezone
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
from .services import compute_daily_airfare_index, ingest_simulated_scraped_fares

logger = logging.getLogger(__name__)


def generate_live_fare_sse():
    """
    Generator yielding Server-Sent Events (text/event-stream) every 3 seconds
    containing a fresh simulated fare observation and current Laspeyres index.
    """
    while True:
        try:
            routes = list(FlightRoute.objects.select_related("origin", "destination").all())
            if routes:
                route = random.choice(routes)
                carrier = random.choice([
                    FareObservation.Carrier.INDIGO,
                    FareObservation.Carrier.AIRINDIA,
                    FareObservation.Carrier.SPICEJET,
                    FareObservation.Carrier.AKASA,
                ])
                portal = random.choice([
                    FareObservation.SourcePortal.DIRECT,
                    FareObservation.SourcePortal.MAKEMYTRIP,
                    FareObservation.SourcePortal.EASEMYTRIP,
                    FareObservation.SourcePortal.YATRA,
                ])
                band = random.choice([7, 14, 21])
                base_fare = float(route.base_benchmark_fare)
                noise = random.uniform(-0.15, 0.25)
                price_inr = round(max(base_fare * (1.0 + noise), 1800.0), 2)
                today = timezone.localdate()

                obs = FareObservation.objects.create(
                    route=route,
                    carrier=carrier,
                    source_portal=portal,
                    observed_price_inr=Decimal(str(price_inr)),
                    departure_date=today + timedelta(days=band),
                    advance_booking_days=band,
                )

                cpi_record = compute_daily_airfare_index(calculation_date=today)

                payload = {
                    "event": "fare_update",
                    "fare": {
                        "id": obs.id,
                        "route_id": route.id,
                        "origin_code": route.origin.iata_code,
                        "origin_city": route.origin.city_name,
                        "destination_code": route.destination.iata_code,
                        "destination_city": route.destination.city_name,
                        "route_code": f"{route.origin.iata_code} -> {route.destination.iata_code}",
                        "route_name": f"{route.origin.city_name} to {route.destination.city_name}",
                        "carrier": obs.carrier,
                        "carrier_display": obs.get_carrier_display(),
                        "source_portal": obs.source_portal,
                        "source_portal_display": obs.get_source_portal_display(),
                        "observed_price_inr": float(obs.observed_price_inr),
                        "advance_booking_days": obs.advance_booking_days,
                        "scraped_at": obs.scraped_at.isoformat(),
                    },
                    "index": {
                        "laspeyres_index_value": cpi_record.laspeyres_index_value,
                        "inflation_rate_mom": cpi_record.inflation_rate_mom,
                        "total_observations_analyzed": cpi_record.total_observations_analyzed,
                        "calculation_date": cpi_record.calculation_date.isoformat(),
                    },
                }
                yield f"data: {json.dumps(payload)}\n\n"
        except Exception as err:
            logger.error(f"Error in SSE generator: {err}")
        time.sleep(3)


@api_view(["GET"])
def live_fare_stream_view(request: HttpRequest) -> StreamingHttpResponse:
    """
    Streaming endpoint returning live real-time Server-Sent Events (SSE).
    GET /api/fares/live-stream/
    """
    response = StreamingHttpResponse(generate_live_fare_sse(), content_type="text/event-stream")
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response


class AirportViewSet(viewsets.ModelViewSet):
    """
    CRUD API endpoints for domestic Indian airports.
    """

    queryset = Airport.objects.all().order_by("iata_code")
    serializer_class = AirportSerializer


class RouteViewSet(viewsets.ModelViewSet):
    """
    CRUD API endpoints for directed domestic flight routes.
    Includes custom search action for origin-destination price matrix analysis.
    """

    queryset = (
        FlightRoute.objects.select_related("origin", "destination")
        .annotate(current_avg_fare=Avg("fares__observed_price_inr"))
        .all()
        .order_by("origin__iata_code", "destination__iata_code")
    )
    serializer_class = FlightRouteSerializer

    @action(detail=False, methods=["get"], url_path="search")
    def search(self, request: Request) -> Response:
        """
        GET /api/routes/search/?origin=CCU&destination=DEL
        Resilient search endpoint with exact matching, reverse route fallback,
        on-the-fly fare observation generation, carrier price breakdown, and window pricing.
        """
        origin_param = (request.query_params.get("origin") or "").strip().upper()
        dest_param = (request.query_params.get("destination") or "").strip().upper()

        routes_qs = FlightRoute.objects.select_related("origin", "destination").all()

        if origin_param and dest_param:
            # 1. Exact match lookup
            matched_routes = list(routes_qs.filter(
                origin__iata_code__iexact=origin_param,
                destination__iata_code__iexact=dest_param,
            ))

            # 2. Fallback 1: Check reverse direction (destination -> origin)
            if not matched_routes:
                reverse_route = routes_qs.filter(
                    origin__iata_code__iexact=dest_param,
                    destination__iata_code__iexact=origin_param,
                ).first()

                if reverse_route:
                    # Dynamically mirror route in DB
                    new_route, _ = FlightRoute.objects.get_or_create(
                        origin=reverse_route.destination,
                        destination=reverse_route.origin,
                        defaults={
                            "passenger_traffic_weight": reverse_route.passenger_traffic_weight,
                            "base_benchmark_fare": reverse_route.base_benchmark_fare,
                        },
                    )
                    matched_routes = [new_route]
                else:
                    # Fallback 2: Check if origin and destination airports exist in DB
                    orig_apt = Airport.objects.filter(Q(iata_code__iexact=origin_param) | Q(city_name__icontains=origin_param)).first()
                    dest_apt = Airport.objects.filter(Q(iata_code__iexact=dest_param) | Q(city_name__icontains=dest_param)).first()

                    if orig_apt and dest_apt and orig_apt != dest_apt:
                        new_route, _ = FlightRoute.objects.get_or_create(
                            origin=orig_apt,
                            destination=dest_apt,
                            defaults={
                                "passenger_traffic_weight": 1.5,
                                "base_benchmark_fare": Decimal("4800.00"),
                            },
                        )
                        matched_routes = [new_route]
        else:
            if origin_param:
                routes_qs = routes_qs.filter(
                    Q(origin__iata_code__iexact=origin_param) | Q(origin__city_name__icontains=origin_param)
                )
            if dest_param:
                routes_qs = routes_qs.filter(
                    Q(destination__iata_code__iexact=dest_param) | Q(destination__city_name__icontains=dest_param)
                )
            matched_routes = list(routes_qs)

        if not matched_routes:
            return Response(
                {
                    "query": {"origin": origin_param, "destination": dest_param},
                    "routes_found": 0,
                    "results": [],
                    "message": "No matching routes found for the requested origin and destination.",
                },
                status=status.HTTP_200_OK,
            )

        results = []
        first_route_payload = None

        for route in matched_routes:
            fares_qs = FareObservation.objects.filter(route=route).order_by("-scraped_at")

            # 3. Auto-generate fare observations if fewer than 4 exist
            if fares_qs.count() < 4:
                ingest_simulated_scraped_fares(routes=[route])
                fares_qs = FareObservation.objects.filter(route=route).order_by("-scraped_at")

            aggregate_data = fares_qs.aggregate(
                lowest=Min("observed_price_inr"),
                highest=Max("observed_price_inr"),
                average=Avg("observed_price_inr"),
            )

            # Carrier breakdown & comparison
            carrier_breakdown = []
            carrier_comparison = []
            for carrier_code, carrier_label in FareObservation.Carrier.choices:
                c_fares = fares_qs.filter(carrier=carrier_code)
                c_agg = c_fares.aggregate(min_p=Min("observed_price_inr"), avg_p=Avg("observed_price_inr"))
                if c_agg["min_p"] is not None:
                    portal_used = c_fares.first().source_portal if c_fares.exists() else "DIRECT"
                    carrier_info = {
                        "carrier": carrier_code,
                        "carrier_display": carrier_label,
                        "price": float(c_agg["min_p"]),
                        "lowest_price": float(c_agg["min_p"]),
                        "average_price": round(float(c_agg["avg_p"]), 2),
                        "portal": portal_used,
                        "sample_count": c_fares.count(),
                    }
                    carrier_breakdown.append(carrier_info)
                    carrier_comparison.append(carrier_info)

            # Advance booking horizon pricing (3d, 7d, 14d, 21d)
            advance_breakdown = []
            advance_window_pricing = {}
            for band in [3, 7, 14, 21]:
                b_fares = fares_qs.filter(advance_booking_days=band)
                b_agg = b_fares.aggregate(avg_p=Avg("observed_price_inr"))
                if b_agg["avg_p"] is not None:
                    avg_p_val = round(float(b_agg["avg_p"]), 2)
                    advance_breakdown.append({
                        "advance_days": band,
                        "average_price": avg_p_val,
                    })
                    advance_window_pricing[f"{band}d"] = avg_p_val
                    advance_window_pricing[str(band)] = avg_p_val

            recent_fares = [
                {
                    "id": f.id,
                    "carrier": f.carrier,
                    "carrier_display": f.get_carrier_display(),
                    "source_portal": f.source_portal,
                    "source_portal_display": f.get_source_portal_display(),
                    "observed_price_inr": float(f.observed_price_inr),
                    "departure_date": f.departure_date.isoformat(),
                    "advance_booking_days": f.advance_booking_days,
                    "scraped_at": f.scraped_at.isoformat(),
                }
                for f in fares_qs[:15]
            ]

            base_benchmark = float(route.base_benchmark_fare)
            avg_fare = float(aggregate_data["average"]) if aggregate_data["average"] is not None else base_benchmark
            lowest_fare = float(aggregate_data["lowest"]) if aggregate_data["lowest"] is not None else base_benchmark
            highest_fare = float(aggregate_data["highest"]) if aggregate_data["highest"] is not None else base_benchmark
            deviation_pct = round(((avg_fare - base_benchmark) / base_benchmark) * 100, 2)

            route_item = {
                "route_id": route.id,
                "origin": route.origin.iata_code,
                "origin_code": route.origin.iata_code,
                "origin_city": route.origin.city_name,
                "destination": route.destination.iata_code,
                "destination_code": route.destination.iata_code,
                "destination_city": route.destination.city_name,
                "route_name": f"{route.origin.city_name} -> {route.destination.city_name}",
                "passenger_traffic_weight": route.passenger_traffic_weight,
                "weight": route.passenger_traffic_weight,
                "base_benchmark_fare": base_benchmark,
                "benchmark": base_benchmark,
                "lowest_fare": lowest_fare,
                "highest_fare": highest_fare,
                "average_fare": round(avg_fare, 2),
                "deviation_percentage": deviation_pct,
                "carrier_comparison": carrier_comparison,
                "carrier_breakdown": carrier_breakdown,
                "advance_window_pricing": advance_window_pricing,
                "advance_breakdown": advance_breakdown,
                "observations": recent_fares,
                "recent_fares": recent_fares,
            }
            results.append(route_item)
            if not first_route_payload:
                first_route_payload = route_item

        response_dict = {
            "query": {"origin": origin_param, "destination": dest_param},
            "routes_found": len(results),
            "results": results,
        }

        if first_route_payload:
            response_dict.update({
                "route": {
                    "id": first_route_payload["route_id"],
                    "origin": first_route_payload["origin_code"],
                    "origin_city": first_route_payload["origin_city"],
                    "destination": first_route_payload["destination_code"],
                    "destination_city": first_route_payload["destination_city"],
                    "benchmark": first_route_payload["base_benchmark_fare"],
                    "weight": first_route_payload["passenger_traffic_weight"],
                },
                "lowest_fare": first_route_payload["lowest_fare"],
                "average_fare": first_route_payload["average_fare"],
                "highest_fare": first_route_payload["highest_fare"],
                "deviation_percentage": first_route_payload["deviation_percentage"],
                "carrier_comparison": first_route_payload["carrier_comparison"],
                "advance_window_pricing": first_route_payload["advance_window_pricing"],
                "observations": first_route_payload["recent_fares"],
            })

        return Response(response_dict, status=status.HTTP_200_OK)


# Backward compatibility alias
FlightRouteViewSet = RouteViewSet


class FareObservationViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only API endpoints for observed scraped airfares.
    Supports live SSE streaming and manual pipeline trigger.
    """

    serializer_class = FareObservationSerializer

    def get_queryset(self) -> QuerySet[FareObservation]:
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

    @action(detail=False, methods=["get"], url_path="live-stream")
    def live_stream(self, request: Request) -> StreamingHttpResponse:
        """GET /api/fares/live-stream/"""
        return live_fare_stream_view(request)

    @action(detail=False, methods=["post"], url_path="trigger-ingestion")
    def trigger_ingestion(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Triggers simulated fare ingestion pipeline across active trunk routes."""
        try:
            if not FlightRoute.objects.exists():
                logger.info("No FlightRoute records found. Auto-seeding initial Indian trunk corridors...")
                from indexer.management.commands.seed_data import run_seed_data
                run_seed_data()

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

            result = ingest_simulated_scraped_fares(seed=seed, use_median=use_median)
            result["records_logged"] = result.get("records_ingested", result.get("record_count", 0))
            result["updated_index"] = result.get("updated_index_value", result.get("index_value", 100.0))
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
    """

    queryset = DailyCPIIndex.objects.all().order_by("-calculation_date")
    serializer_class = DailyCPIIndexSerializer

    @action(detail=False, methods=["get"], url_path="latest")
    def latest(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        latest_record = self.get_queryset().first()
        if not latest_record:
            return Response(
                {"detail": "No CPI index records found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = self.get_serializer(latest_record)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=False, methods=["get"], url_path="summary")
    def summary(self, request: Request) -> Response:
        """GET /api/cpi-indices/summary/ or GET /api/index/summary/"""
        return index_summary_view(request)


# Backward compatibility alias
DailyCPIIndexViewSet = CPIIndexViewSet


@api_view(["GET"])
def index_summary_view(request: HttpRequest) -> Response:
    """
    GET /api/index/summary/
    Returns aggregated macro stats, top surging & discounted corridors,
    and 7-day Laspeyres historical index trend data.
    """
    latest_index = DailyCPIIndex.objects.all().order_by("-calculation_date").first()
    total_obs = FareObservation.objects.count()
    total_routes = FlightRoute.objects.count()

    # Route deviations
    routes = FlightRoute.objects.select_related("origin", "destination").annotate(
        avg_fare=Avg("fares__observed_price_inr")
    )

    top_surging = None
    top_discounted = None
    max_dev = -999.0
    min_dev = 999.0

    for r in routes:
        base_f = float(r.base_benchmark_fare)
        avg_f = float(r.avg_fare) if r.avg_fare is not None else base_f
        dev = ((avg_f - base_f) / base_f) * 100.0

        r_info = {
            "route_id": r.id,
            "corridor": f"{r.origin.iata_code} -> {r.destination.iata_code}",
            "route_name": f"{r.origin.city_name} to {r.destination.city_name}",
            "base_benchmark_fare": base_f,
            "average_fare": round(avg_f, 2),
            "deviation_percentage": round(dev, 2),
        }

        if dev > max_dev:
            max_dev = dev
            top_surging = r_info
        if dev < min_dev:
            min_dev = dev
            top_discounted = r_info

    # 7-day trend
    trend_qs = DailyCPIIndex.objects.all().order_by("-calculation_date")[:7]
    historical_trend_7d = [
        {
            "calculation_date": idx.calculation_date.isoformat(),
            "laspeyres_index_value": idx.laspeyres_index_value,
            "inflation_rate_mom": idx.inflation_rate_mom,
            "total_observations_analyzed": idx.total_observations_analyzed,
        }
        for idx in reversed(trend_qs)
    ]

    latest_data = (
        {
            "calculation_date": latest_index.calculation_date.isoformat(),
            "laspeyres_index_value": latest_index.laspeyres_index_value,
            "inflation_rate_mom": latest_index.inflation_rate_mom,
            "total_observations_analyzed": latest_index.total_observations_analyzed,
        }
        if latest_index
        else {
            "calculation_date": timezone.localdate().isoformat(),
            "laspeyres_index_value": 100.0,
            "inflation_rate_mom": 0.0,
            "total_observations_analyzed": 0,
        }
    )

    return Response(
        {
            "latest_index": latest_data,
            "total_observations": total_obs,
            "total_corridors": total_routes,
            "top_surging_route": top_surging,
            "top_discounted_route": top_discounted,
            "historical_trend_7d": historical_trend_7d,
        },
        status=status.HTTP_200_OK,
    )


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
                "routes_search": "/api/routes/search/?origin=DEL&destination=BOM",
                "fares": "/api/fares/",
                "fares_live_stream": "/api/fares/live-stream/",
                "fares_trigger_ingestion": "/api/fares/trigger-ingestion/",
                "cpi_indices": "/api/cpi-indices/",
                "cpi_indices_latest": "/api/cpi-indices/latest/",
                "index_summary": "/api/index/summary/",
            },
        }
    )
