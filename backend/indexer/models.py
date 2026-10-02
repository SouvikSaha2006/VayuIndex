from django.db import models


class Route(models.Model):
    """Domestic Indian flight route (e.g., DEL -> BOM, BLR -> CCU)."""
    origin = models.CharField(max_length=10, help_text="Origin IATA code (e.g. DEL)")
    destination = models.CharField(max_length=10, help_text="Destination IATA code (e.g. BOM)")
    origin_city = models.CharField(max_length=100)
    destination_city = models.CharField(max_length=100)
    distance_km = models.PositiveIntegerField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("origin", "destination")
        ordering = ["origin", "destination"]

    def __str__(self):
        return f"{self.origin} -> {self.destination}"


class AirfareObservation(models.Model):
    """Daily or hourly fare quote snapshot across carriers."""
    route = models.ForeignKey(Route, on_delete=models.CASCADE, related_name="fare_observations")
    carrier = models.CharField(max_length=50, help_text="Carrier name or code (e.g., Indigo, Air India)")
    departure_date = models.DateField()
    days_to_departure = models.PositiveSmallIntegerField(help_text="Advance booking window in days")
    fare_inr = models.DecimalField(max_digits=10, decimal_places=2, help_text="Fare in INR")
    captured_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["route", "departure_date"]),
            models.Index(fields=["captured_at"]),
        ]
        ordering = ["-captured_at"]

    def __str__(self):
        return f"{self.route} [{self.carrier}] INR {self.fare_inr} ({self.days_to_departure}d lead)"


class CPIAugmentationIndex(models.Model):
    """Computed airfare volatility index and its augmented CPI impact weight."""
    month_year = models.DateField(help_text="First date of observation month")
    base_cpi_transport = models.DecimalField(max_digits=8, decimal_places=3, null=True, blank=True)
    airfare_volatility_index = models.DecimalField(max_digits=8, decimal_places=3)
    augmented_cpi_value = models.DecimalField(max_digits=8, decimal_places=3)
    variance_pct = models.DecimalField(max_digits=6, decimal_places=2)
    calculated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-month_year"]

    def __str__(self):
        return f"VayuIndex {self.month_year.strftime('%b %Y')}: Aug CPI {self.augmented_cpi_value}"
