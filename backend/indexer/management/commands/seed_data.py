import math
import itertools
from datetime import timedelta
from decimal import Decimal
from typing import Any

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from indexer.models import Airport, DailyCPIIndex, FlightRoute
from indexer.services import compute_daily_airfare_index, ingest_simulated_scraped_fares


def calculate_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Computes Haversine distance in kilometers between two lat/lng coordinates."""
    if not (lat1 and lon1 and lat2 and lon2):
        return 800.0
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2.0) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return R * c


ALL_INDIAN_AIRPORTS = [
    # Tier 1 Metros (6)
    {"iata_code": "DEL", "city_name": "New Delhi", "state_name": "Delhi", "metro_tier": Airport.MetroTier.TIER_1, "latitude": 28.5562, "longitude": 77.1000},
    {"iata_code": "BOM", "city_name": "Mumbai", "state_name": "Maharashtra", "metro_tier": Airport.MetroTier.TIER_1, "latitude": 19.0896, "longitude": 72.8656},
    {"iata_code": "BLR", "city_name": "Bengaluru", "state_name": "Karnataka", "metro_tier": Airport.MetroTier.TIER_1, "latitude": 13.1986, "longitude": 77.7066},
    {"iata_code": "CCU", "city_name": "Kolkata", "state_name": "West Bengal", "metro_tier": Airport.MetroTier.TIER_1, "latitude": 22.6520, "longitude": 88.4463},
    {"iata_code": "HYD", "city_name": "Hyderabad", "state_name": "Telangana", "metro_tier": Airport.MetroTier.TIER_1, "latitude": 17.2403, "longitude": 78.4294},
    {"iata_code": "MAA", "city_name": "Chennai", "state_name": "Tamil Nadu", "metro_tier": Airport.MetroTier.TIER_1, "latitude": 12.9941, "longitude": 80.1709},

    # Tier 2 Commercial Hubs (10)
    {"iata_code": "PNQ", "city_name": "Pune", "state_name": "Maharashtra", "metro_tier": Airport.MetroTier.TIER_2, "latitude": 18.5822, "longitude": 73.9197},
    {"iata_code": "AMD", "city_name": "Ahmedabad", "state_name": "Gujarat", "metro_tier": Airport.MetroTier.TIER_2, "latitude": 23.0772, "longitude": 72.6347},
    {"iata_code": "COK", "city_name": "Kochi", "state_name": "Kerala", "metro_tier": Airport.MetroTier.TIER_2, "latitude": 10.1520, "longitude": 76.4019},
    {"iata_code": "GOI", "city_name": "Goa (Dabolim)", "state_name": "Goa", "metro_tier": Airport.MetroTier.TIER_2, "latitude": 15.3808, "longitude": 73.8314},
    {"iata_code": "JAI", "city_name": "Jaipur", "state_name": "Rajasthan", "metro_tier": Airport.MetroTier.TIER_2, "latitude": 26.8242, "longitude": 75.8122},
    {"iata_code": "LKO", "city_name": "Lucknow", "state_name": "Uttar Pradesh", "metro_tier": Airport.MetroTier.TIER_2, "latitude": 26.7606, "longitude": 80.8893},
    {"iata_code": "GAU", "city_name": "Guwahati", "state_name": "Assam", "metro_tier": Airport.MetroTier.TIER_2, "latitude": 26.1061, "longitude": 91.5859},
    {"iata_code": "PAT", "city_name": "Patna", "state_name": "Bihar", "metro_tier": Airport.MetroTier.TIER_2, "latitude": 25.5913, "longitude": 85.0880},
    {"iata_code": "BBI", "city_name": "Bhubaneswar", "state_name": "Odisha", "metro_tier": Airport.MetroTier.TIER_2, "latitude": 20.2444, "longitude": 85.8178},
    {"iata_code": "TRV", "city_name": "Thiruvananthapuram", "state_name": "Kerala", "metro_tier": Airport.MetroTier.TIER_2, "latitude": 8.4821, "longitude": 76.9200},

    # Tier 3 Regional / UDAN (8)
    {"iata_code": "IXB", "city_name": "Bagdogra / Siliguri", "state_name": "West Bengal", "metro_tier": Airport.MetroTier.TIER_3, "latitude": 26.6812, "longitude": 88.3286},
    {"iata_code": "SXR", "city_name": "Srinagar", "state_name": "Jammu & Kashmir", "metro_tier": Airport.MetroTier.TIER_3, "latitude": 33.9871, "longitude": 74.7741},
    {"iata_code": "IXR", "city_name": "Ranchi", "state_name": "Jharkhand", "metro_tier": Airport.MetroTier.TIER_3, "latitude": 23.3143, "longitude": 85.3217},
    {"iata_code": "IXZ", "city_name": "Port Blair", "state_name": "Andaman & Nicobar", "metro_tier": Airport.MetroTier.TIER_3, "latitude": 11.6412, "longitude": 92.7297},
    {"iata_code": "VNS", "city_name": "Varanasi", "state_name": "Uttar Pradesh", "metro_tier": Airport.MetroTier.TIER_3, "latitude": 25.4523, "longitude": 82.8592},
    {"iata_code": "DED", "city_name": "Dehradun", "state_name": "Uttarakhand", "metro_tier": Airport.MetroTier.TIER_3, "latitude": 30.1897, "longitude": 78.1803},
    {"iata_code": "IXE", "city_name": "Mangaluru", "state_name": "Karnataka", "metro_tier": Airport.MetroTier.TIER_3, "latitude": 12.9613, "longitude": 74.8900},
    {"iata_code": "UDR", "city_name": "Udaipur", "state_name": "Rajasthan", "metro_tier": Airport.MetroTier.TIER_3, "latitude": 24.6177, "longitude": 73.8961},
]

# Explicit weights for key trunk & feeder pairs
EXPLICIT_WEIGHTS = {
    ("DEL", "BOM"): 2.8, ("DEL", "BLR"): 2.4, ("BOM", "BLR"): 2.2,
    ("DEL", "CCU"): 2.0, ("DEL", "HYD"): 1.8, ("DEL", "MAA"): 1.8,
    ("BOM", "HYD"): 1.6, ("BOM", "MAA"): 1.6, ("BOM", "CCU"): 1.7,
    ("BLR", "HYD"): 1.4, ("BLR", "MAA"): 1.3, ("BLR", "CCU"): 1.6,
    ("HYD", "MAA"): 1.2, ("HYD", "CCU"): 1.4, ("MAA", "CCU"): 1.3,
}


def run_seed_data(seed_value: int = 42) -> None:
    """
    Comprehensive National Seeder across 24 Indian Airports (T1, T2, T3).
    Generates bidirectional routes for all T1-T1 pairs, primary feeder T1-T2 routes,
    and strategic regional T3 routes, applying distance-based baseline benchmarks and
    traffic weights.
    """
    airport_map = {}
    with transaction.atomic():
        for data in ALL_INDIAN_AIRPORTS:
            airport, _ = Airport.objects.update_or_create(
                iata_code=data["iata_code"],
                defaults={
                    "city_name": data["city_name"],
                    "state_name": data["state_name"],
                    "metro_tier": data["metro_tier"],
                    "latitude": data["latitude"],
                    "longitude": data["longitude"],
                },
            )
            airport_map[airport.iata_code] = airport

        t1_codes = [a["iata_code"] for a in ALL_INDIAN_AIRPORTS if a["metro_tier"] == Airport.MetroTier.TIER_1]
        t2_codes = [a["iata_code"] for a in ALL_INDIAN_AIRPORTS if a["metro_tier"] == Airport.MetroTier.TIER_2]
        t3_codes = [a["iata_code"] for a in ALL_INDIAN_AIRPORTS if a["metro_tier"] == Airport.MetroTier.TIER_3]

        # Route pairs to generate:
        # 1. All T1 <-> T1 pairs
        # 2. Major Metros (DEL, BOM, BLR, CCU) to all T2 airports
        # 3. Key Metros (DEL, CCU, BLR, MAA, BOM) to strategic T3 airports
        pairs_to_generate = set()

        for orig, dest in itertools.permutations(t1_codes, 2):
            pairs_to_generate.add((orig, dest))

        primary_hubs = ["DEL", "BOM", "BLR", "CCU", "HYD"]
        for hub in primary_hubs:
            for t2 in t2_codes:
                pairs_to_generate.add((hub, t2))
                pairs_to_generate.add((t2, hub))

        regional_pairs = [
            ("DEL", "SXR"), ("SXR", "DEL"),
            ("CCU", "IXB"), ("IXB", "CCU"),
            ("BLR", "IXE"), ("IXE", "BLR"),
            ("DEL", "IXZ"), ("IXZ", "DEL"),
            ("MAA", "IXZ"), ("IXZ", "MAA"),
            ("DEL", "VNS"), ("VNS", "DEL"),
            ("DEL", "DED"), ("DED", "DEL"),
            ("BOM", "UDR"), ("UDR", "BOM"),
            ("CCU", "IXR"), ("IXR", "CCU"),
            ("DEL", "IXR"), ("IXR", "DEL"),
            ("DEL", "PNQ"), ("PNQ", "DEL"),
            ("DEL", "GAU"), ("GAU", "DEL"),
            ("DEL", "PAT"), ("PAT", "DEL"),
        ]
        for p in regional_pairs:
            pairs_to_generate.add(p)

        created_routes = []
        for orig_code, dest_code in pairs_to_generate:
            orig = airport_map[orig_code]
            dest = airport_map[dest_code]

            dist_km = calculate_distance_km(orig.latitude, orig.longitude, dest.latitude, dest.longitude)
            # Distance-based baseline fare: Base ₹2,800 + (distance_km * ₹1.8/km)
            base_fare_val = round(2800.0 + (dist_km * 1.8), 2)
            benchmark_fare = Decimal(str(max(base_fare_val, 2200.0)))

            # Determine traffic weight
            pair_key = (orig_code, dest_code)
            reverse_key = (dest_code, orig_code)

            if pair_key in EXPLICIT_WEIGHTS:
                weight = EXPLICIT_WEIGHTS[pair_key]
            elif reverse_key in EXPLICIT_WEIGHTS:
                weight = EXPLICIT_WEIGHTS[reverse_key]
            elif orig.metro_tier == Airport.MetroTier.TIER_1 and dest.metro_tier == Airport.MetroTier.TIER_1:
                weight = 1.8
            elif orig.metro_tier == Airport.MetroTier.TIER_1 or dest.metro_tier == Airport.MetroTier.TIER_1:
                weight = 1.3
            else:
                weight = 0.7

            route, _ = FlightRoute.objects.update_or_create(
                origin=orig,
                destination=dest,
                defaults={
                    "passenger_traffic_weight": weight,
                    "base_benchmark_fare": benchmark_fare,
                },
            )
            created_routes.append(route)

        # Seed historical DailyCPIIndex entries for past 3 days
        today = timezone.localdate()
        historical_indices = [
            (today - timedelta(days=3), 98.50, 98.20, 99.10, -0.40, 350),
            (today - timedelta(days=2), 99.20, 99.00, 99.70, 0.71, 350),
            (today - timedelta(days=1), 100.10, 100.00, 100.30, 0.91, 350),
        ]

        for calc_date, idx_val, m_sub, r_sub, mom_val, obs_count in historical_indices:
            DailyCPIIndex.objects.update_or_create(
                calculation_date=calc_date,
                defaults={
                    "laspeyres_index_value": idx_val,
                    "metro_sub_index": m_sub,
                    "regional_sub_index": r_sub,
                    "inflation_rate_mom": mom_val,
                    "total_observations_analyzed": obs_count,
                },
            )

    # Ingest multi-carrier fare observations across all created routes
    ingest_simulated_scraped_fares(seed=seed_value, routes=created_routes)
    compute_daily_airfare_index(calculation_date=today)


class Command(BaseCommand):
    help = (
        "Seeds comprehensive All-India multi-tier flight routes across 24 airports (T1, T2, T3), "
        "calculates distance-based benchmarks, populates fare observations, and computes Laspeyres CPI index."
    )

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            "--seed",
            type=int,
            default=42,
            help="Random seed for reproducible simulated pricing ingestion.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        self.stdout.write(self.style.NOTICE("Executing All-India multi-tier VayuIndex seeder across 24 airports..."))
        run_seed_data(seed_value=options["seed"])
        self.stdout.write(self.style.SUCCESS("Successfully seeded multi-tier routes and fare quotes across T1, T2, and T3 airports!"))
