from datetime import timedelta
from decimal import Decimal
from typing import Any
import itertools

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from indexer.models import Airport, DailyCPIIndex, FlightRoute
from indexer.services import compute_daily_airfare_index, ingest_simulated_scraped_fares


# Benchmark configuration per bidirectional corridor pair
CORRIDOR_BENCHMARKS = {
    ("DEL", "BOM"): (2.8, Decimal("4800.00")),
    ("DEL", "BLR"): (2.4, Decimal("5400.00")),
    ("BOM", "BLR"): (2.1, Decimal("4200.00")),
    ("DEL", "CCU"): (1.8, Decimal("4900.00")),
    ("DEL", "HYD"): (1.6, Decimal("4500.00")),
    ("DEL", "MAA"): (1.7, Decimal("5200.00")),
    ("BOM", "HYD"): (1.4, Decimal("3600.00")),
    ("BOM", "MAA"): (1.5, Decimal("3900.00")),
    ("BOM", "CCU"): (1.6, Decimal("5500.00")),
    ("BLR", "HYD"): (1.3, Decimal("3100.00")),
    ("BLR", "MAA"): (1.2, Decimal("2900.00")),
    ("BLR", "CCU"): (1.5, Decimal("5300.00")),
    ("HYD", "MAA"): (1.1, Decimal("3200.00")),
    ("HYD", "CCU"): (1.3, Decimal("4700.00")),
    ("MAA", "CCU"): (1.2, Decimal("4800.00")),
}


def run_seed_data(seed_value: int = 42) -> None:
    """
    Comprehensive Seeder generating all 30 bidirectional airport pair permutations across 
    DEL, BOM, BLR, CCU, HYD, and MAA, populating fresh fare observations across carriers,
    and computing the Laspeyres airfare index.
    """
    airports_data = [
        {"iata_code": "DEL", "city_name": "New Delhi", "metro_tier": Airport.MetroTier.TIER_1},
        {"iata_code": "BOM", "city_name": "Mumbai", "metro_tier": Airport.MetroTier.TIER_1},
        {"iata_code": "BLR", "city_name": "Bengaluru", "metro_tier": Airport.MetroTier.TIER_1},
        {"iata_code": "CCU", "city_name": "Kolkata", "metro_tier": Airport.MetroTier.TIER_1},
        {"iata_code": "HYD", "city_name": "Hyderabad", "metro_tier": Airport.MetroTier.TIER_1},
        {"iata_code": "MAA", "city_name": "Chennai", "metro_tier": Airport.MetroTier.TIER_1},
    ]

    airport_map = {}
    with transaction.atomic():
        for data in airports_data:
            airport, _ = Airport.objects.update_or_create(
                iata_code=data["iata_code"],
                defaults={
                    "city_name": data["city_name"],
                    "metro_tier": data["metro_tier"],
                },
            )
            airport_map[airport.iata_code] = airport

        # Loop through all 30 permutations of origin -> destination (6 * 5 = 30 routes)
        codes = [a["iata_code"] for a in airports_data]
        created_routes = []

        for orig_code, dest_code in itertools.permutations(codes, 2):
            orig = airport_map[orig_code]
            dest = airport_map[dest_code]

            # Find matching benchmark pair
            pair_key = (orig_code, dest_code)
            reverse_key = (dest_code, orig_code)

            if pair_key in CORRIDOR_BENCHMARKS:
                weight, benchmark = CORRIDOR_BENCHMARKS[pair_key]
            elif reverse_key in CORRIDOR_BENCHMARKS:
                weight, benchmark = CORRIDOR_BENCHMARKS[reverse_key]
            else:
                weight, benchmark = (1.2, Decimal("4500.00"))

            route, _ = FlightRoute.objects.update_or_create(
                origin=orig,
                destination=dest,
                defaults={
                    "passenger_traffic_weight": weight,
                    "base_benchmark_fare": benchmark,
                },
            )
            created_routes.append(route)

        # Seed historical DailyCPIIndex entries for past 3 days
        today = timezone.localdate()
        historical_indices = [
            (today - timedelta(days=3), 98.50, -0.40, 120),
            (today - timedelta(days=2), 99.20, 0.71, 120),
            (today - timedelta(days=1), 100.10, 0.91, 120),
        ]

        for calc_date, idx_val, mom_val, obs_count in historical_indices:
            DailyCPIIndex.objects.update_or_create(
                calculation_date=calc_date,
                defaults={
                    "laspeyres_index_value": idx_val,
                    "inflation_rate_mom": mom_val,
                    "total_observations_analyzed": obs_count,
                },
            )

    # Ingest multi-carrier fare observations across all 30 routes
    ingest_simulated_scraped_fares(seed=seed_value, routes=created_routes)
    compute_daily_airfare_index(calculation_date=today)


class Command(BaseCommand):
    help = (
        "Seeds comprehensive bidirectional Indian trunk corridors (30 routes across DEL, BOM, BLR, CCU, HYD, MAA), "
        "populates fare observations across all carriers, and computes initial CPI index."
    )

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            "--seed",
            type=int,
            default=42,
            help="Random seed for reproducible simulated pricing ingestion.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        self.stdout.write(self.style.NOTICE("Executing comprehensive 30-route bidirectional VayuIndex seeder..."))
        run_seed_data(seed_value=options["seed"])
        self.stdout.write(self.style.SUCCESS("Successfully seeded 30 directed routes and fare quotes across all metro hubs!"))
