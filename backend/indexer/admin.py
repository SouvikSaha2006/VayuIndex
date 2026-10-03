"""
Enterprise-grade Django Admin Control Center for VayuIndex.

Provides operational governance over airport nodes, trunk flight routes,
raw scraped fare observations, and computed Laspeyres airfare CPI price indices.
"""

from django.contrib import admin, messages
from django.db.models import QuerySet
from django.http import HttpRequest
from django.utils.html import format_html
from django.utils.safestring import SafeString

from .models import Airport, DailyCPIIndex, FareObservation, FlightRoute
from .services import compute_daily_airfare_index

# Global Admin Site Customization
admin.site.site_header = "VayuIndex Control Center"
admin.site.site_title = "VayuIndex Admin"
admin.site.index_title = "National Airfare CPI Augmentation Engine"


@admin.register(Airport)
class AirportAdmin(admin.ModelAdmin):
    """
    Operational governance for domestic Indian airport hubs.
    """

    list_display = ("iata_code", "city_name", "metro_tier")
    search_fields = ("iata_code", "city_name")
    list_filter = ("metro_tier",)
    ordering = ("iata_code",)
    list_per_page = 25


@admin.register(FlightRoute)
class FlightRouteAdmin(admin.ModelAdmin):
    """
    Administrative control for directed domestic flight corridors.
    Enables inline editing of statistical traffic weights for Laspeyres basket formulation
    and triggers on-demand recalculation of the national airfare CPI index.
    """

    list_display = (
        "origin",
        "destination",
        "passenger_traffic_weight",
        "base_benchmark_fare",
    )
    list_editable = ("passenger_traffic_weight",)
    list_select_related = ("origin", "destination")
    search_fields = (
        "origin__iata_code",
        "origin__city_name",
        "destination__iata_code",
        "destination__city_name",
    )
    list_filter = ("origin__metro_tier", "destination__metro_tier")
    ordering = ("origin__iata_code", "destination__iata_code")
    list_per_page = 30
    actions = ["recalculate_cpi_index_now"]

    @admin.action(description="Recalculate CPI Index Now")
    def recalculate_cpi_index_now(
        self, request: HttpRequest, queryset: QuerySet[FlightRoute]
    ) -> None:
        """
        Triggers on-demand calculation of the Laspeyres airfare CPI index
        incorporating all fresh fare observations for the active session.
        """
        try:
            daily_index = compute_daily_airfare_index()
            self.message_user(
                request,
                f"Successfully recalculated Laspeyres Airfare Index for {daily_index.calculation_date}: "
                f"Index Value = {daily_index.laspeyres_index_value:.2f}, "
                f"MoM Inflation = {daily_index.inflation_rate_mom:+.2f}%, "
                f"Analyzed Observations = {daily_index.total_observations_analyzed}.",
                level=messages.SUCCESS,
            )
        except Exception as exc:
            self.message_user(
                request,
                f"Failed to recalculate CPI index: {exc}",
                level=messages.ERROR,
            )


@admin.register(FareObservation)
class FareObservationAdmin(admin.ModelAdmin):
    """
    Auditing interface for individual scraped airfare observations across carriers and booking portals.
    """

    list_display = (
        "route",
        "carrier",
        "source_portal",
        "observed_price_inr",
        "departure_date",
        "scraped_at",
    )
    list_filter = ("carrier", "source_portal")
    date_hierarchy = "scraped_at"
    list_select_related = ("route", "route__origin", "route__destination")
    search_fields = (
        "carrier",
        "route__origin__iata_code",
        "route__destination__iata_code",
        "route__origin__city_name",
        "route__destination__city_name",
    )
    ordering = ("-scraped_at",)
    readonly_fields = ("scraped_at",)
    list_per_page = 50


@admin.register(DailyCPIIndex)
class DailyCPIIndexAdmin(admin.ModelAdmin):
    """
    Time-series management of the daily aggregated Laspeyres airfare index
    with visual alert badges for inflation vs deflation trends.
    """

    list_display = (
        "calculation_date",
        "laspeyres_index_value",
        "inflation_rate_mom",
        "total_observations_analyzed",
    )
    ordering = ("-calculation_date",)
    date_hierarchy = "calculation_date"
    readonly_fields = ("recorded_at",)
    list_per_page = 30

    @admin.display(description="Inflation Rate (MoM)", ordering="inflation_rate_mom")
    def inflation_rate_mom(self, obj: DailyCPIIndex) -> SafeString:
        """
        Renders colored pill badge:
        - Red for positive inflation (+%), indicating rising consumer travel costs.
        - Green for negative inflation (-%), indicating price reductions/deflation.
        - Gray for neutral zero change.
        """
        rate = obj.inflation_rate_mom
        if rate > 0:
            bg_color = "#dc2626"  # Tailwind red-600
            fg_color = "#ffffff"
            sign = "+"
        elif rate < 0:
            bg_color = "#16a34a"  # Tailwind green-600
            fg_color = "#ffffff"
            sign = ""
        else:
            bg_color = "#4b5563"  # Tailwind gray-600
            fg_color = "#ffffff"
            sign = ""

        formatted_rate = f"{sign}{rate:0.2f}%"
        return format_html(
            '<span style="background-color: {}; color: {}; font-weight: 700; '
            'padding: 3px 10px; border-radius: 9999px; font-size: 0.85em; '
            'display: inline-block; min-width: 60px; text-align: center;">'
            '{}</span>',
            bg_color,
            fg_color,
            formatted_rate,
        )
