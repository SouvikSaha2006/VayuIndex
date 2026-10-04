import logging
import random
import statistics
from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, Iterable, List, Optional

from django.db import transaction
from django.db.models import Avg, Count
from django.utils import timezone

from .models import DailyCPIIndex, FareObservation, FlightRoute

logger = logging.getLogger(__name__)


# Realistic carrier pricing multipliers relative to base benchmark fare:
# - Air India: Full-service premium (complimentary meals, baggage allowance, flexibility)
# - IndiGo: Market leader with massive network frequency, baseline benchmark
# - SpiceJet: Budget carrier dynamic low-cost pricing
# - Akasa Air: Agile challenger with aggressive penetration pricing
CARRIER_PRICE_MULTIPLIERS = {
    FareObservation.Carrier.AIRINDIA: 1.12,
    FareObservation.Carrier.INDIGO: 1.02,
    FareObservation.Carrier.SPICEJET: 0.95,
    FareObservation.Carrier.AKASA: 0.91,
}

# Dynamic yield management curve across advance booking horizons:
# - 3 days out: Close-in emergency surge / high yield
# - 7 days out: Close-in booking surge / restricted inventory buckets
# - 14 days out: Baseline demand window
# - 21 days out: Early bird inventory release / lower fares
ADVANCE_BOOKING_MULTIPLIERS = {
    3: 1.45,
    7: 1.28,
    14: 1.02,
    21: 0.88,
}

# Minor distribution channel variance / convenience fee differentials:
PORTAL_PRICE_MULTIPLIERS = {
    FareObservation.SourcePortal.DIRECT: 1.000,
    FareObservation.SourcePortal.MAKEMYTRIP: 1.018,
    FareObservation.SourcePortal.EASEMYTRIP: 0.992,
    FareObservation.SourcePortal.YATRA: 1.008,
}


def compute_daily_airfare_index(
    calculation_date: Optional[date] = None,
    use_median: bool = True,
) -> DailyCPIIndex:
    """
    Computes the daily Laspeyres Airfare Price Index across all active domestic routes:

        Index_t = [ Sum(P_{i,t} * W_i) / Sum(P_{i,0} * W_i) ] * 100

    Where:
        - P_{i,t} is the median (or mean) observed fare for route i on date t.
        - P_{i,0} is the base benchmark fare for route i.
        - W_i is the passenger traffic weight for route i.

    Also calculates the Month-over-Month (MoM) inflation rate relative to the
    immediately preceding CPI index record.

    Upserts into DailyCPIIndex for the calculation date and returns the updated instance.

    Args:
        calculation_date: Date for which the index is computed (defaults to today).
        use_median: If True, uses the median fare for P_{i,t}. If False, uses the mean fare.

    Returns:
        The updated or newly created DailyCPIIndex instance.
    """
    if calculation_date is None:
        calculation_date = timezone.localdate()

    routes = list(FlightRoute.objects.select_related("origin", "destination").all())
    if not routes:
        logger.warning("No flight routes defined. Cannot compute Laspeyres index.")
        index_record, _ = DailyCPIIndex.objects.update_or_create(
            calculation_date=calculation_date,
            defaults={
                "laspeyres_index_value": 100.0,
                "inflation_rate_mom": 0.0,
                "total_observations_analyzed": 0,
            },
        )
        return index_record

    # Retrieve all fare observations captured on calculation_date
    obs_qs = FareObservation.objects.filter(scraped_at__date=calculation_date)
    total_obs_count = obs_qs.count()

    # Aggregate fares per route
    route_fare_map: Dict[int, List[float]] = defaultdict(list)
    for route_id, price in obs_qs.values_list("route_id", "observed_price_inr"):
        route_fare_map[route_id].append(float(price))

    weighted_current_sum = 0.0
    weighted_base_sum = 0.0

    for route in routes:
        weight = float(route.passenger_traffic_weight)
        base_fare = float(route.base_benchmark_fare)

        # Determine route observed price P_{i,t}
        fares = route_fare_map.get(route.id, [])
        if fares:
            if use_median:
                p_it = float(statistics.median(fares))
            else:
                p_it = float(statistics.mean(fares))
        else:
            # Impute using base benchmark fare if no fresh observations today
            p_it = base_fare

        weighted_current_sum += p_it * weight
        weighted_base_sum += base_fare * weight

    # Laspeyres Price Index computation
    if weighted_base_sum > 0:
        laspeyres_index = (weighted_current_sum / weighted_base_sum) * 100.0
    else:
        laspeyres_index = 100.0

    # Month-over-Month (MoM) inflation rate relative to preceding record
    preceding_record = (
        DailyCPIIndex.objects.filter(calculation_date__lt=calculation_date)
        .order_by("-calculation_date")
        .first()
    )

    if preceding_record and preceding_record.laspeyres_index_value > 0:
        inflation_rate_mom = (
            (laspeyres_index - preceding_record.laspeyres_index_value)
            / preceding_record.laspeyres_index_value
        ) * 100.0
    else:
        inflation_rate_mom = 0.0

    # Upsert into DailyCPIIndex
    daily_index, created = DailyCPIIndex.objects.update_or_create(
        calculation_date=calculation_date,
        defaults={
            "laspeyres_index_value": round(laspeyres_index, 2),
            "inflation_rate_mom": round(inflation_rate_mom, 2),
            "total_observations_analyzed": total_obs_count,
        },
    )

    action = "Created" if created else "Updated"
    logger.info(
        f"{action} DailyCPIIndex [{calculation_date}]: "
        f"Index={daily_index.laspeyres_index_value:.2f}, "
        f"MoM={daily_index.inflation_rate_mom:+.2f}%, "
        f"Obs={daily_index.total_observations_analyzed}"
    )

    return daily_index


def ingest_simulated_scraped_fares(
    target_date: Optional[date] = None,
    routes: Optional[Iterable[FlightRoute]] = None,
    use_median: bool = True,
    seed: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Simulates and ingests a fresh batch of observed airfares across defined routes
    for IndiGo, Air India, SpiceJet, and Akasa with advance booking bands (7, 14, 21 days).

    Immediately invokes compute_daily_airfare_index() after ingestion to update the index.

    Args:
        target_date: Observation/scraping date (defaults to today).
        routes: Optional subset of FlightRoute instances; defaults to all active routes.
        use_median: Metric formulation for the index aggregator.
        seed: Optional random seed for deterministic simulation.

    Returns:
        Summary dictionary containing:
            - record_count: Number of fare observation records ingested
            - records_ingested: Alias for record_count
            - updated_index_value: Latest computed Laspeyres index
            - index_value: Alias for updated_index_value
            - inflation_rate_mom: Derived Month-over-Month percentage change
            - calculation_date: ISO formatted calculation date
            - total_observations_analyzed: Total observations used in index computation
            - status: Operational status string
    """
    if seed is not None:
        random.seed(seed)

    if target_date is None:
        target_date = timezone.localdate()

    if routes is None:
        routes = list(FlightRoute.objects.select_related("origin", "destination").all())
    else:
        routes = list(routes)

    if not routes:
        logger.warning("No routes available for simulated fare ingestion.")
        daily_index = compute_daily_airfare_index(calculation_date=target_date, use_median=use_median)
        return {
            "status": "warning",
            "message": "No routes available",
            "record_count": 0,
            "records_ingested": 0,
            "index_value": daily_index.laspeyres_index_value,
            "updated_index_value": daily_index.laspeyres_index_value,
            "inflation_rate_mom": daily_index.inflation_rate_mom,
            "calculation_date": target_date.isoformat(),
            "total_observations_analyzed": daily_index.total_observations_analyzed,
        }

    carriers = [
        FareObservation.Carrier.INDIGO,
        FareObservation.Carrier.AIRINDIA,
        FareObservation.Carrier.SPICEJET,
        FareObservation.Carrier.AKASA,
    ]
    advance_bands = [3, 7, 14, 21]
    portals = [
        FareObservation.SourcePortal.DIRECT,
        FareObservation.SourcePortal.MAKEMYTRIP,
        FareObservation.SourcePortal.EASEMYTRIP,
        FareObservation.SourcePortal.YATRA,
    ]

    now_dt = timezone.now()
    if target_date != timezone.localdate():
        # Set scraped timestamp matching target_date for historical/backtest simulation
        scraped_dt = timezone.make_aware(
            datetime.combine(target_date, datetime.min.time()) + timedelta(hours=10)
        )
    else:
        scraped_dt = now_dt

    fare_records: List[FareObservation] = []

    for route in routes:
        base_benchmark = float(route.base_benchmark_fare)

        for carrier in carriers:
            carrier_mult = CARRIER_PRICE_MULTIPLIERS.get(carrier, 1.0)

            for band in advance_bands:
                band_mult = ADVANCE_BOOKING_MULTIPLIERS.get(band, 1.0)
                departure_date = target_date + timedelta(days=band)

                # Generate observations across portals for market depth
                # Select direct portal plus at least one major OTA
                selected_portals = [
                    FareObservation.SourcePortal.DIRECT,
                    random.choice([
                        FareObservation.SourcePortal.MAKEMYTRIP,
                        FareObservation.SourcePortal.EASEMYTRIP,
                        FareObservation.SourcePortal.YATRA,
                    ]),
                ]

                for portal in selected_portals:
                    portal_mult = PORTAL_PRICE_MULTIPLIERS.get(portal, 1.0)

                    # Dynamic stochastic noise (+/- 3.5%) reflecting seat load factor and intraday yield
                    noise = random.uniform(-0.035, 0.035)

                    raw_price = base_benchmark * carrier_mult * band_mult * portal_mult * (1.0 + noise)
                    # Enforce realistic Indian aviation price floor (₹1,500.00)
                    clamped_price = max(raw_price, 1500.00)
                    price_inr = Decimal(str(round(clamped_price, 2)))

                    obs = FareObservation(
                        route=route,
                        carrier=carrier,
                        source_portal=portal,
                        observed_price_inr=price_inr,
                        departure_date=departure_date,
                        advance_booking_days=band,
                    )
                    # Manually set scraped_at so bulk_create correctly assigns the timestamp
                    obs.scraped_at = scraped_dt
                    fare_records.append(obs)

    # Bulk insert all observations within a transaction
    with transaction.atomic():
        FareObservation.objects.bulk_create(fare_records, batch_size=1000)

    logger.info(f"Ingested {len(fare_records)} simulated fare observations for {target_date}.")

    # Immediately invoke index calculation
    daily_index = compute_daily_airfare_index(
        calculation_date=target_date,
        use_median=use_median,
    )

    return {
        "status": "success",
        "record_count": len(fare_records),
        "records_ingested": len(fare_records),
        "updated_index_value": daily_index.laspeyres_index_value,
        "index_value": daily_index.laspeyres_index_value,
        "inflation_rate_mom": daily_index.inflation_rate_mom,
        "calculation_date": target_date.isoformat(),
        "total_observations_analyzed": daily_index.total_observations_analyzed,
    }
