from django.contrib import admin
from .models import Airport, FlightRoute, FareObservation, DailyCPIIndex


@admin.register(Airport)
class AirportAdmin(admin.ModelAdmin):
    list_display = ("iata_code", "city_name", "metro_tier")
    search_fields = ("iata_code", "city_name")
    list_filter = ("metro_tier",)


@admin.register(FlightRoute)
class FlightRouteAdmin(admin.ModelAdmin):
    list_display = ("__str__", "origin", "destination", "passenger_traffic_weight", "base_benchmark_fare")
    search_fields = ("origin__iata_code", "origin__city_name", "destination__iata_code", "destination__city_name")
    list_filter = ("origin__metro_tier", "destination__metro_tier")


@admin.register(FareObservation)
class FareObservationAdmin(admin.ModelAdmin):
    list_display = (
        "route",
        "carrier",
        "source_portal",
        "observed_price_inr",
        "departure_date",
        "advance_booking_days",
        "scraped_at",
    )
    search_fields = (
        "carrier",
        "route__origin__iata_code",
        "route__destination__iata_code",
    )
    list_filter = ("carrier", "source_portal", "advance_booking_days")
    date_hierarchy = "departure_date"


@admin.register(DailyCPIIndex)
class DailyCPIIndexAdmin(admin.ModelAdmin):
    list_display = (
        "calculation_date",
        "laspeyres_index_value",
        "inflation_rate_mom",
        "total_observations_analyzed",
        "recorded_at",
    )
    ordering = ("-calculation_date",)
    date_hierarchy = "calculation_date"
