from django.contrib import admin
from .models import Route, AirfareObservation, CPIAugmentationIndex


@admin.register(Route)
class RouteAdmin(admin.ModelAdmin):
    list_display = ("origin", "destination", "origin_city", "destination_city", "is_active", "created_at")
    search_fields = ("origin", "destination", "origin_city", "destination_city")
    list_filter = ("is_active",)


@admin.register(AirfareObservation)
class AirfareObservationAdmin(admin.ModelAdmin):
    list_display = ("route", "carrier", "departure_date", "days_to_departure", "fare_inr", "captured_at")
    search_fields = ("carrier", "route__origin", "route__destination")
    list_filter = ("carrier", "days_to_departure")


@admin.register(CPIAugmentationIndex)
class CPIAugmentationIndexAdmin(admin.ModelAdmin):
    list_display = ("month_year", "base_cpi_transport", "airfare_volatility_index", "augmented_cpi_value", "variance_pct")
    ordering = ("-month_year",)
