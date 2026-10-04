"""
Serializers for VayuIndex REST API layer.

Defines model serialization, dynamic computed fields, and currency/route
representations for Indian aviation CPI price relative tracking.
"""

from decimal import Decimal
from typing import Optional
from django.db.models import Avg
from rest_framework import serializers

from .models import Airport, DailyCPIIndex, FareObservation, FlightRoute


class AirportSerializer(serializers.ModelSerializer):
    """
    ModelSerializer for Airport representing domestic Indian origin and destination nodes.
    """

    class Meta:
        model = Airport
        fields = [
            "id",
            "iata_code",
            "city_name",
            "state_name",
            "latitude",
            "longitude",
            "metro_tier",
        ]


class FlightRouteSerializer(serializers.ModelSerializer):
    """
    ModelSerializer for FlightRoute corridor connecting origin and destination airports.
    Includes dynamic computed fields for origin/destination airport metadata and current average fare.
    """

    origin_code = serializers.SerializerMethodField()
    origin_city = serializers.SerializerMethodField()
    destination_code = serializers.SerializerMethodField()
    destination_city = serializers.SerializerMethodField()
    current_avg_fare = serializers.SerializerMethodField()
    route_name = serializers.CharField(source="__str__", read_only=True)

    origin_tier = serializers.CharField(source="origin.metro_tier", read_only=True)
    destination_tier = serializers.CharField(source="destination.metro_tier", read_only=True)
    tier_classification = serializers.SerializerMethodField()

    class Meta:
        model = FlightRoute
        fields = [
            "id",
            "origin",
            "destination",
            "passenger_traffic_weight",
            "base_benchmark_fare",
            "route_name",
            "origin_code",
            "origin_city",
            "origin_tier",
            "destination_code",
            "destination_city",
            "destination_tier",
            "tier_classification",
            "current_avg_fare",
        ]

    def get_origin_code(self, obj: FlightRoute) -> str:
        """Returns 3-letter uppercase IATA code for the departure airport."""
        return obj.origin.iata_code

    def get_origin_city(self, obj: FlightRoute) -> str:
        """Returns city name for the departure airport."""
        return obj.origin.city_name

    def get_destination_code(self, obj: FlightRoute) -> str:
        """Returns 3-letter uppercase IATA code for the destination airport."""
        return obj.destination.iata_code

    def get_destination_city(self, obj: FlightRoute) -> str:
        """Returns city name for the destination airport."""
        return obj.destination.city_name

    def get_tier_classification(self, obj: FlightRoute) -> str:
        """Returns route tier classification string."""
        if obj.origin.metro_tier == "T1" and obj.destination.metro_tier == "T1":
            return "T1 Metro"
        elif "T3" in (obj.origin.metro_tier, obj.destination.metro_tier):
            return "T3 UDAN"
        else:
            return "T2 Feeder"

    def get_current_avg_fare(self, obj: FlightRoute) -> Optional[float]:
        """
        Dynamically computes the current average fare for this route.
        Checks for queryset annotation first, then falls back to calculating the average
        from related FareObservations, or uses base_benchmark_fare if no observations exist.
        """
        if hasattr(obj, "current_avg_fare") and obj.current_avg_fare is not None:
            return round(float(obj.current_avg_fare), 2)

        fare_avg = obj.fares.aggregate(avg=Avg("observed_price_inr"))["avg"]
        if fare_avg is not None:
            return round(float(fare_avg), 2)

        if obj.base_benchmark_fare is not None:
            return round(float(obj.base_benchmark_fare), 2)

        return None


class FareObservationSerializer(serializers.ModelSerializer):
    """
    ModelSerializer for FareObservation snapshots across carriers and distribution portals.
    Includes route string representation and formatted currency string.
    """

    route_str = serializers.CharField(source="route.__str__", read_only=True)
    route_name = serializers.CharField(source="route.__str__", read_only=True)
    formatted_price = serializers.SerializerMethodField()
    formatted_currency = serializers.SerializerMethodField()
    carrier_display = serializers.CharField(source="get_carrier_display", read_only=True)
    source_portal_display = serializers.CharField(source="get_source_portal_display", read_only=True)

    class Meta:
        model = FareObservation
        fields = [
            "id",
            "route",
            "route_str",
            "route_name",
            "carrier",
            "carrier_display",
            "source_portal",
            "source_portal_display",
            "observed_price_inr",
            "formatted_price",
            "formatted_currency",
            "departure_date",
            "advance_booking_days",
            "scraped_at",
        ]

    def get_formatted_price(self, obj: FareObservation) -> str:
        """Returns the observed fare formatted with Indian Rupee currency symbol."""
        if obj.observed_price_inr is not None:
            return f"₹{obj.observed_price_inr:,.2f}"
        return ""

    def get_formatted_currency(self, obj: FareObservation) -> str:
        """Alias for formatted_price providing explicit currency representation."""
        return self.get_formatted_price(obj)


class DailyCPIIndexSerializer(serializers.ModelSerializer):
    """
    ModelSerializer for DailyCPIIndex representing daily aggregated Laspeyres price index metrics.
    """

    class Meta:
        model = DailyCPIIndex
        fields = [
            "id",
            "calculation_date",
            "laspeyres_index_value",
            "metro_sub_index",
            "regional_sub_index",
            "inflation_rate_mom",
            "total_observations_analyzed",
            "recorded_at",
        ]
