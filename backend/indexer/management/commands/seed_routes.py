from decimal import Decimal
from django.core.management.base import BaseCommand
from django.db import transaction

from indexer.models import Airport, FlightRoute
from indexer.services import ingest_simulated_scraped_fares


class Command(BaseCommand):
    help = (
        "Seeds major Indian trunk airport hubs (DEL, BOM, BLR, CCU, HYD, MAA), "
        "establishes directed corridors with benchmark fares and passenger traffic weights, "
        "and runs the initial Laspeyres price index computation."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--no-fares",
            action="store_true",
            help="Seed airports and routes without ingesting simulated fares or calculating index.",
        )
        parser.add_argument(
            "--seed",
            type=int,
            default=42,
            help="Random seed for reproducible simulated pricing ingestion.",
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Initializing VayuIndex Route Seeding Engine..."))

        # 1. Major Indian Metro Airports (Tier 1 Hubs)
        airports_data = [
            {"iata_code": "DEL", "city_name": "Delhi", "metro_tier": Airport.MetroTier.TIER_1},
            {"iata_code": "BOM", "city_name": "Mumbai", "metro_tier": Airport.MetroTier.TIER_1},
            {"iata_code": "BLR", "city_name": "Bengaluru", "metro_tier": Airport.MetroTier.TIER_1},
            {"iata_code": "CCU", "city_name": "Kolkata", "metro_tier": Airport.MetroTier.TIER_1},
            {"iata_code": "HYD", "city_name": "Hyderabad", "metro_tier": Airport.MetroTier.TIER_1},
            {"iata_code": "MAA", "city_name": "Chennai", "metro_tier": Airport.MetroTier.TIER_1},
        ]

        # 2. Major Indian Trunk Corridors with DGCA-aligned traffic weights and base benchmark fares
        corridors = [
            ("DEL", "BOM", 1.00, Decimal("5200.00")),
            ("DEL", "BLR", 0.85, Decimal("5800.00")),
            ("BOM", "BLR", 0.75, Decimal("4200.00")),
            ("DEL", "HYD", 0.70, Decimal("4800.00")),
            ("DEL", "CCU", 0.65, Decimal("5100.00")),
            ("DEL", "MAA", 0.60, Decimal("5500.00")),
            ("BOM", "HYD", 0.55, Decimal("3800.00")),
            ("BOM", "MAA", 0.50, Decimal("4500.00")),
            ("BOM", "CCU", 0.45, Decimal("5600.00")),
            ("BLR", "HYD", 0.45, Decimal("3200.00")),
            ("BLR", "MAA", 0.40, Decimal("2800.00")),
            ("BLR", "CCU", 0.40, Decimal("5400.00")),
            ("HYD", "MAA", 0.35, Decimal("3200.00")),
            ("CCU", "HYD", 0.35, Decimal("4600.00")),
            ("CCU", "MAA", 0.30, Decimal("4900.00")),
        ]

        with transaction.atomic():
            airport_map = {}
            for data in airports_data:
                airport, created = Airport.objects.update_or_create(
                    iata_code=data["iata_code"],
                    defaults={
                        "city_name": data["city_name"],
                        "metro_tier": data["metro_tier"],
                    },
                )
                airport_map[airport.iata_code] = airport

            self.stdout.write(
                self.style.SUCCESS(f"Successfully seeded {len(airport_map)} major metro airports.")
            )

            # Seed bidirectional routes (A -> B and B -> A)
            routes_created = 0
            for orig_code, dest_code, weight, base_fare in corridors:
                orig = airport_map[orig_code]
                dest = airport_map[dest_code]

                # Outbound route
                FlightRoute.objects.update_or_create(
                    origin=orig,
                    destination=dest,
                    defaults={
                        "passenger_traffic_weight": weight,
                        "base_benchmark_fare": base_fare,
                    },
                )
                routes_created += 1

                # Inbound return route
                FlightRoute.objects.update_or_create(
                    origin=dest,
                    destination=orig,
                    defaults={
                        "passenger_traffic_weight": weight,
                        "base_benchmark_fare": base_fare,
                    },
                )
                routes_created += 1

            self.stdout.write(
                self.style.SUCCESS(
                    f"Successfully configured {routes_created} directed trunk flight routes "
                    f"across {len(corridors)} bidirectional metro corridors."
                )
            )

        if options["no_fares"]:
            self.stdout.write(
                self.style.WARNING("Skipping simulated fare ingestion and initial index calculation (--no-fares).")
            )
            return

        self.stdout.write("Ingesting initial simulated multi-carrier scraped fares...")
        summary = ingest_simulated_scraped_fares(seed=options["seed"])

        self.stdout.write(self.style.SUCCESS("=" * 64))
        self.stdout.write(self.style.SUCCESS("   VAYUINDEX INITIAL AIRFARE CPI INDEX SUMMARY"))
        self.stdout.write(self.style.SUCCESS("=" * 64))
        self.stdout.write(f"  Calculation Date           : {summary['calculation_date']}")
        self.stdout.write(f"  Total Fare Quotes Ingested : {summary['record_count']}")
        self.stdout.write(f"  Observations Analyzed      : {summary['total_observations_analyzed']}")
        self.stdout.write(f"  Laspeyres Price Index (t)  : {summary['updated_index_value']:.2f} (Base: 100.00)")
        self.stdout.write(f"  Month-over-Month (MoM) Chg : {summary['inflation_rate_mom']:+.2f}%")
        self.stdout.write(self.style.SUCCESS("=" * 64))
