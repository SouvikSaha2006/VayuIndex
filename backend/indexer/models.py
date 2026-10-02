from decimal import Decimal
from django.db import models
from django.core.validators import RegexValidator


class Airport(models.Model):
    """
    Airport entity representing domestic Indian departure and arrival points.
    """
    class MetroTier(models.TextChoices):
        TIER_1 = "T1", "Tier 1 Metro"
        TIER_2 = "T2", "Tier 2 Regional Hub"

    iata_code_validator = RegexValidator(
        regex=r"^[A-Z]{3}$",
        message="IATA code must be exactly 3 uppercase letters (e.g., DEL, BOM, BLR).",
    )

    iata_code = models.CharField(
        max_length=3,
        unique=True,
        validators=[iata_code_validator],
        help_text="3-character uppercase unique IATA airport identifier (e.g., DEL, BOM, BLR)",
    )
    city_name = models.CharField(
        max_length=100,
        help_text="Associated metropolitan area or city name",
    )
    metro_tier = models.CharField(
        max_length=2,
        choices=MetroTier.choices,
        default=MetroTier.TIER_1,
        help_text="Hub classification for demographic and traffic clustering",
    )

    class Meta:
        ordering = ["iata_code"]
        verbose_name = "Airport"
        verbose_name_plural = "Airports"

    def clean(self):
        super().clean()
        if self.iata_code:
            self.iata_code = self.iata_code.strip().upper()

    def save(self, *args, **kwargs):
        if self.iata_code:
            self.iata_code = self.iata_code.strip().upper()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.iata_code} ({self.city_name})"


class FlightRoute(models.Model):
    """
    Directed domestic flight corridor connecting an origin and destination airport.
    Incorporates statistical weight for Laspeyres CPI index formulation.
    """
    origin = models.ForeignKey(
        Airport,
        on_delete=models.CASCADE,
        related_name="departing_routes",
        help_text="Departure airport",
    )
    destination = models.ForeignKey(
        Airport,
        on_delete=models.CASCADE,
        related_name="arriving_routes",
        help_text="Arrival airport",
    )
    passenger_traffic_weight = models.FloatField(
        default=1.0,
        help_text="Statistical weight (w_i) used in Laspeyres CPI basket index calculation",
    )
    base_benchmark_fare = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("4500.00"),
        help_text="Benchmark baseline fare (p_0) in INR for CPI price relatives",
    )

    class Meta:
        unique_together = ("origin", "destination")
        ordering = ["origin__iata_code", "destination__iata_code"]
        verbose_name = "Flight Route"
        verbose_name_plural = "Flight Routes"

    def __str__(self):
        return f"{self.origin.iata_code} -> {self.destination.iata_code}"


class FareObservation(models.Model):
    """
    Individual scraped fare quote snapshot across carriers and portals.
    """
    class Carrier(models.TextChoices):
        INDIGO = "INDIGO", "IndiGo"
        AIRINDIA = "AIRINDIA", "Air India"
        SPICEJET = "SPICEJET", "SpiceJet"
        AKASA = "AKASA", "Akasa Air"

    class SourcePortal(models.TextChoices):
        DIRECT = "DIRECT", "Direct Airline Portal"
        MAKEMYTRIP = "MAKEMYTRIP", "MakeMyTrip"
        EASEMYTRIP = "EASEMYTRIP", "EaseMyTrip"
        YATRA = "YATRA", "Yatra"

    route = models.ForeignKey(
        FlightRoute,
        on_delete=models.CASCADE,
        related_name="fares",
        help_text="Flight route for this observation",
    )
    carrier = models.CharField(
        max_length=20,
        choices=Carrier.choices,
        help_text="Airline operating the service",
    )
    source_portal = models.CharField(
        max_length=20,
        choices=SourcePortal.choices,
        help_text="Distribution channel or OTA portal where fare was observed",
    )
    observed_price_inr = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Observed one-way fare inclusive of baseline taxes in INR",
    )
    departure_date = models.DateField(
        help_text="Scheduled departure date for the fare quote",
    )
    advance_booking_days = models.PositiveIntegerField(
        help_text="Advance booking window in days (e.g., 1, 7, 14, 30 days out)",
    )
    scraped_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        help_text="Timestamp when the fare observation was scraped/recorded",
    )

    class Meta:
        ordering = ["-scraped_at"]
        indexes = [
            models.Index(fields=["route", "departure_date"]),
            models.Index(fields=["carrier", "scraped_at"]),
        ]
        verbose_name = "Fare Observation"
        verbose_name_plural = "Fare Observations"

    def __str__(self):
        return f"{self.route} | {self.carrier} | ₹{self.observed_price_inr} ({self.advance_booking_days}d out)"


class DailyCPIIndex(models.Model):
    """
    Aggregated daily Laspeyres price index and derived inflation metrics
    augmenting the national transport component of the Consumer Price Index.
    """
    calculation_date = models.DateField(
        unique=True,
        help_text="Date for which the daily Laspeyres index is computed",
    )
    laspeyres_index_value = models.FloatField(
        help_text="Base 100.0 Laspeyres airfare index value for the day",
    )
    inflation_rate_mom = models.FloatField(
        help_text="Month-over-month (MoM) inflation percentage change",
    )
    total_observations_analyzed = models.PositiveIntegerField(
        help_text="Total number of valid fare observations ingested in this computation",
    )
    recorded_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Timestamp when this daily metric record was compiled and stored",
    )

    class Meta:
        ordering = ["-calculation_date"]
        verbose_name = "Daily CPI Index"
        verbose_name_plural = "Daily CPI Indices"

    def __str__(self):
        return f"CPI [{self.calculation_date}]: {self.laspeyres_index_value:.2f} (MoM: {self.inflation_rate_mom:+.2f}%)"
