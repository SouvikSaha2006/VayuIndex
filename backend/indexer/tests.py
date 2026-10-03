from datetime import date, timedelta
from decimal import Decimal
from io import StringIO
import statistics

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from indexer.models import Airport, DailyCPIIndex, FareObservation, FlightRoute
from indexer.services import compute_daily_airfare_index, ingest_simulated_scraped_fares


class AirportAndFlightRouteModelTests(TestCase):
    def setUp(self):
        self.del_apt = Airport.objects.create(
            iata_code="DEL",
            city_name="Delhi",
            metro_tier=Airport.MetroTier.TIER_1,
        )
        self.bom_apt = Airport.objects.create(
            iata_code="BOM",
            city_name="Mumbai",
            metro_tier=Airport.MetroTier.TIER_1,
        )

    def test_airport_str_and_clean(self):
        self.assertEqual(str(self.del_apt), "DEL (Delhi)")
        apt_lower = Airport.objects.create(iata_code="blr", city_name="Bengaluru")
        self.assertEqual(apt_lower.iata_code, "BLR")

    def test_flight_route_creation(self):
        route = FlightRoute.objects.create(
            origin=self.del_apt,
            destination=self.bom_apt,
            passenger_traffic_weight=1.0,
            base_benchmark_fare=Decimal("5000.00"),
        )
        self.assertEqual(str(route), "DEL -> BOM")
        self.assertEqual(route.base_benchmark_fare, Decimal("5000.00"))


class LaspeyresIndexCalculationTests(TestCase):
    def setUp(self):
        self.del_apt = Airport.objects.create(iata_code="DEL", city_name="Delhi")
        self.bom_apt = Airport.objects.create(iata_code="BOM", city_name="Mumbai")
        self.blr_apt = Airport.objects.create(iata_code="BLR", city_name="Bengaluru")

        # Route 1: Base fare = 5000, Weight = 2.0
        self.route1 = FlightRoute.objects.create(
            origin=self.del_apt,
            destination=self.bom_apt,
            passenger_traffic_weight=2.0,
            base_benchmark_fare=Decimal("5000.00"),
        )

        # Route 2: Base fare = 4000, Weight = 1.0
        self.route2 = FlightRoute.objects.create(
            origin=self.bom_apt,
            destination=self.blr_apt,
            passenger_traffic_weight=1.0,
            base_benchmark_fare=Decimal("4000.00"),
        )

    def test_mathematical_laspeyres_exact_calculation(self):
        """
        Verify exact mathematical index formulation:
        Route 1 (W_1 = 2.0, P_{1,0} = 5000):
            Fares: [5400, 5600, 6000] -> Median P_{1,t} = 5600
        Route 2 (W_2 = 1.0, P_{2,0} = 4000):
            Fares: [4200, 4400, 4600] -> Median P_{2,t} = 4400

        Weighted Base Sum = (5000 * 2.0) + (4000 * 1.0) = 10000 + 4000 = 14000
        Weighted Current Sum = (5600 * 2.0) + (4400 * 1.0) = 11200 + 4400 = 15600
        Expected Laspeyres Index = (15600 / 14000) * 100 = 111.42857... -> 111.43
        """
        today = timezone.localdate()

        # Route 1 observations
        for price in [5400, 5600, 6000]:
            FareObservation.objects.create(
                route=self.route1,
                carrier=FareObservation.Carrier.INDIGO,
                source_portal=FareObservation.SourcePortal.DIRECT,
                observed_price_inr=Decimal(str(price)),
                departure_date=today + timedelta(days=7),
                advance_booking_days=7,
            )

        # Route 2 observations
        for price in [4200, 4400, 4600]:
            FareObservation.objects.create(
                route=self.route2,
                carrier=FareObservation.Carrier.AIRINDIA,
                source_portal=FareObservation.SourcePortal.DIRECT,
                observed_price_inr=Decimal(str(price)),
                departure_date=today + timedelta(days=14),
                advance_booking_days=14,
            )

        index_record = compute_daily_airfare_index(calculation_date=today, use_median=True)

        self.assertEqual(index_record.calculation_date, today)
        self.assertEqual(index_record.total_observations_analyzed, 6)
        self.assertAlmostEqual(index_record.laspeyres_index_value, 111.43, places=2)
        # Initial record has no predecessor, so MoM is 0.0%
        self.assertEqual(index_record.inflation_rate_mom, 0.0)

    def test_mom_inflation_rate_calculation(self):
        """
        Verify MoM inflation rate relative to preceding record:
        Preceding Day: Index = 100.00
        Current Day: Index = 105.50
        Expected MoM = ((105.50 - 100.00) / 100.00) * 100 = +5.50%
        """
        yesterday = timezone.localdate() - timedelta(days=1)
        today = timezone.localdate()

        # Seed preceding record
        DailyCPIIndex.objects.create(
            calculation_date=yesterday,
            laspeyres_index_value=100.0,
            inflation_rate_mom=0.0,
            total_observations_analyzed=10,
        )

        # Route 1: 5275 (5.5% higher than 5000), Route 2: 4220 (5.5% higher than 4000)
        FareObservation.objects.create(
            route=self.route1,
            carrier=FareObservation.Carrier.INDIGO,
            source_portal=FareObservation.SourcePortal.DIRECT,
            observed_price_inr=Decimal("5275.00"),
            departure_date=today + timedelta(days=7),
            advance_booking_days=7,
        )
        FareObservation.objects.create(
            route=self.route2,
            carrier=FareObservation.Carrier.AIRINDIA,
            source_portal=FareObservation.SourcePortal.DIRECT,
            observed_price_inr=Decimal("4220.00"),
            departure_date=today + timedelta(days=7),
            advance_booking_days=7,
        )

        index_record = compute_daily_airfare_index(calculation_date=today)
        self.assertAlmostEqual(index_record.laspeyres_index_value, 105.50, places=2)
        self.assertAlmostEqual(index_record.inflation_rate_mom, 5.50, places=2)

    def test_upsert_idempotency(self):
        """Computing twice on the same day should update rather than duplicate."""
        today = timezone.localdate()
        rec1 = compute_daily_airfare_index(calculation_date=today)
        count_initial = DailyCPIIndex.objects.count()

        # Add more observations and recalculate
        FareObservation.objects.create(
            route=self.route1,
            carrier=FareObservation.Carrier.INDIGO,
            source_portal=FareObservation.SourcePortal.DIRECT,
            observed_price_inr=Decimal("6000.00"),
            departure_date=today + timedelta(days=7),
            advance_booking_days=7,
        )
        rec2 = compute_daily_airfare_index(calculation_date=today)
        count_final = DailyCPIIndex.objects.count()

        self.assertEqual(count_initial, count_final)
        self.assertEqual(rec1.id, rec2.id)


class SimulatedFareIngestionTests(TestCase):
    def setUp(self):
        self.del_apt = Airport.objects.create(iata_code="DEL", city_name="Delhi")
        self.bom_apt = Airport.objects.create(iata_code="BOM", city_name="Mumbai")
        self.route = FlightRoute.objects.create(
            origin=self.del_apt,
            destination=self.bom_apt,
            passenger_traffic_weight=1.0,
            base_benchmark_fare=Decimal("5000.00"),
        )

    def test_ingestion_and_carrier_bands(self):
        summary = ingest_simulated_scraped_fares(seed=123)

        self.assertEqual(summary["status"], "success")
        self.assertGreater(summary["record_count"], 0)
        self.assertGreater(summary["updated_index_value"], 0.0)

        # Check all 4 target carriers are present
        observed_carriers = set(FareObservation.objects.values_list("carrier", flat=True))
        expected_carriers = {
            FareObservation.Carrier.INDIGO,
            FareObservation.Carrier.AIRINDIA,
            FareObservation.Carrier.SPICEJET,
            FareObservation.Carrier.AKASA,
        }
        self.assertEqual(observed_carriers, expected_carriers)

        # Check all 3 advance booking bands (7, 14, 21 days) are present
        observed_bands = set(FareObservation.objects.values_list("advance_booking_days", flat=True))
        self.assertEqual(observed_bands, {7, 14, 21})

        # Ensure index was calculated and upserted
        today = timezone.localdate()
        self.assertTrue(DailyCPIIndex.objects.filter(calculation_date=today).exists())


class SeedRoutesCommandTests(TestCase):
    def test_seed_routes_execution(self):
        out = StringIO()
        call_command("seed_routes", seed=42, stdout=out)
        output = out.getvalue()

        self.assertIn("Successfully seeded 6 major metro airports", output)
        self.assertIn("Successfully configured 30 directed trunk flight routes", output)
        self.assertIn("Laspeyres Price Index (t)", output)

        # Verify airports in database
        self.assertEqual(Airport.objects.count(), 6)
        expected_codes = {"DEL", "BOM", "BLR", "CCU", "HYD", "MAA"}
        self.assertEqual(set(Airport.objects.values_list("iata_code", flat=True)), expected_codes)

        # Verify 30 directed routes in database
        self.assertEqual(FlightRoute.objects.count(), 30)

        # Verify DailyCPIIndex is created
        today = timezone.localdate()
        self.assertTrue(DailyCPIIndex.objects.filter(calculation_date=today).exists())

    def test_seed_routes_no_fares_flag(self):
        out = StringIO()
        call_command("seed_routes", "--no-fares", stdout=out)
        output = out.getvalue()

        self.assertIn("Successfully seeded 6 major metro airports", output)
        self.assertIn("Skipping simulated fare ingestion", output)
        self.assertEqual(FareObservation.objects.count(), 0)


class AirportAPITests(APITestCase):
    def setUp(self):
        self.del_apt = Airport.objects.create(iata_code="DEL", city_name="Delhi")
        self.bom_apt = Airport.objects.create(iata_code="BOM", city_name="Mumbai")

    def test_list_airports(self):
        response = self.client.get("/api/airports/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Handles both paginated and non-paginated responses
        results = response.data.get("results", response.data)
        self.assertEqual(len(results), 2)
        iata_codes = [a["iata_code"] for a in results]
        self.assertIn("DEL", iata_codes)
        self.assertIn("BOM", iata_codes)

    def test_create_airport(self):
        payload = {
            "iata_code": "BLR",
            "city_name": "Bengaluru",
            "metro_tier": Airport.MetroTier.TIER_1,
        }
        response = self.client.post("/api/airports/", payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Airport.objects.count(), 3)
        self.assertEqual(response.data["iata_code"], "BLR")


class FlightRouteAPITests(APITestCase):
    def setUp(self):
        self.del_apt = Airport.objects.create(iata_code="DEL", city_name="Delhi")
        self.bom_apt = Airport.objects.create(iata_code="BOM", city_name="Mumbai")
        self.blr_apt = Airport.objects.create(iata_code="BLR", city_name="Bengaluru")

        self.route1 = FlightRoute.objects.create(
            origin=self.del_apt,
            destination=self.bom_apt,
            passenger_traffic_weight=1.5,
            base_benchmark_fare=Decimal("4500.00"),
        )
        self.route2 = FlightRoute.objects.create(
            origin=self.del_apt,
            destination=self.blr_apt,
            passenger_traffic_weight=1.0,
            base_benchmark_fare=Decimal("5000.00"),
        )

        today = timezone.localdate()
        # Seed fares for route 1: [5000, 6000] -> Avg = 5500.00
        FareObservation.objects.create(
            route=self.route1,
            carrier=FareObservation.Carrier.INDIGO,
            source_portal=FareObservation.SourcePortal.DIRECT,
            observed_price_inr=Decimal("5000.00"),
            departure_date=today + timedelta(days=7),
            advance_booking_days=7,
        )
        FareObservation.objects.create(
            route=self.route1,
            carrier=FareObservation.Carrier.AIRINDIA,
            source_portal=FareObservation.SourcePortal.MAKEMYTRIP,
            observed_price_inr=Decimal("6000.00"),
            departure_date=today + timedelta(days=7),
            advance_booking_days=7,
        )

    def test_list_routes_dynamic_fields(self):
        response = self.client.get("/api/routes/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data.get("results", response.data)
        self.assertEqual(len(results), 2)

        # Route 1: DEL -> BOM
        route1_data = next(r for r in results if r["id"] == self.route1.id)
        self.assertEqual(route1_data["origin_code"], "DEL")
        self.assertEqual(route1_data["origin_city"], "Delhi")
        self.assertEqual(route1_data["destination_code"], "BOM")
        self.assertEqual(route1_data["destination_city"], "Mumbai")
        self.assertAlmostEqual(route1_data["current_avg_fare"], 5500.00, places=2)

        # Route 2: DEL -> BLR (no observations, falls back to base_benchmark_fare)
        route2_data = next(r for r in results if r["id"] == self.route2.id)
        self.assertEqual(route2_data["origin_code"], "DEL")
        self.assertEqual(route2_data["destination_code"], "BLR")
        self.assertAlmostEqual(route2_data["current_avg_fare"], 5000.00, places=2)


class FareObservationAPITests(APITestCase):
    def setUp(self):
        self.del_apt = Airport.objects.create(iata_code="DEL", city_name="Delhi")
        self.bom_apt = Airport.objects.create(iata_code="BOM", city_name="Mumbai")
        self.route = FlightRoute.objects.create(
            origin=self.del_apt,
            destination=self.bom_apt,
            passenger_traffic_weight=1.0,
            base_benchmark_fare=Decimal("4500.00"),
        )
        self.other_route = FlightRoute.objects.create(
            origin=self.bom_apt,
            destination=self.del_apt,
            passenger_traffic_weight=1.0,
            base_benchmark_fare=Decimal("4500.00"),
        )

        today = timezone.localdate()
        self.obs1 = FareObservation.objects.create(
            route=self.route,
            carrier=FareObservation.Carrier.INDIGO,
            source_portal=FareObservation.SourcePortal.DIRECT,
            observed_price_inr=Decimal("5400.00"),
            departure_date=today + timedelta(days=7),
            advance_booking_days=7,
        )
        self.obs2 = FareObservation.objects.create(
            route=self.other_route,
            carrier=FareObservation.Carrier.AIRINDIA,
            source_portal=FareObservation.SourcePortal.MAKEMYTRIP,
            observed_price_inr=Decimal("6200.50"),
            departure_date=today + timedelta(days=14),
            advance_booking_days=14,
        )

    def test_list_fares_representation_and_currency(self):
        response = self.client.get("/api/fares/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data.get("results", response.data)
        self.assertEqual(len(results), 2)

        item = next(x for x in results if x["id"] == self.obs1.id)
        self.assertIn("DEL -> BOM", item["route_str"])
        self.assertIn("₹5,400.00", item["formatted_price"])
        self.assertIn("₹5,400.00", item["formatted_currency"])

    def test_filter_fares_by_carrier(self):
        # Case insensitive carrier filter
        response = self.client.get("/api/fares/?carrier=indigo")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data.get("results", response.data)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["carrier"], "INDIGO")

    def test_filter_fares_by_route(self):
        response = self.client.get(f"/api/fares/?route={self.route.id}")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data.get("results", response.data)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["id"], self.obs1.id)

    def test_trigger_ingestion_action(self):
        initial_count = FareObservation.objects.count()
        response = self.client.post(
            "/api/fares/trigger-ingestion/",
            {"seed": 99, "use_median": True},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "success")
        self.assertGreater(response.data["record_count"], 0)
        self.assertGreater(FareObservation.objects.count(), initial_count)
        self.assertIn("updated_index_value", response.data)


class CPIIndexAPITests(APITestCase):
    def setUp(self):
        today = timezone.localdate()
        self.rec1 = DailyCPIIndex.objects.create(
            calculation_date=today - timedelta(days=2),
            laspeyres_index_value=100.0,
            inflation_rate_mom=0.0,
            total_observations_analyzed=10,
        )
        self.rec2 = DailyCPIIndex.objects.create(
            calculation_date=today - timedelta(days=1),
            laspeyres_index_value=103.5,
            inflation_rate_mom=3.5,
            total_observations_analyzed=15,
        )
        self.rec3 = DailyCPIIndex.objects.create(
            calculation_date=today,
            laspeyres_index_value=107.0,
            inflation_rate_mom=3.38,
            total_observations_analyzed=20,
        )

    def test_list_cpi_indices_descending_order(self):
        response = self.client.get("/api/cpi-indices/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data.get("results", response.data)
        self.assertEqual(len(results), 3)

        dates = [r["calculation_date"] for r in results]
        self.assertEqual(
            dates,
            [
                self.rec3.calculation_date.isoformat(),
                self.rec2.calculation_date.isoformat(),
                self.rec1.calculation_date.isoformat(),
            ],
        )

    def test_latest_action(self):
        response = self.client.get("/api/cpi-indices/latest/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["calculation_date"], self.rec3.calculation_date.isoformat())
        self.assertAlmostEqual(response.data["laspeyres_index_value"], 107.0, places=1)

    def test_latest_action_when_empty(self):
        DailyCPIIndex.objects.all().delete()
        response = self.client.get("/api/cpi-indices/latest/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class APIRootDiscoveryTests(APITestCase):
    def test_root_health_check(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["status"], "healthy")

    def test_api_status_view(self):
        response = self.client.get("/api/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "operational")
        self.assertIn("endpoints", response.data)
        self.assertIn("routes", response.data["endpoints"])
        self.assertIn("cpi_indices_latest", response.data["endpoints"])


