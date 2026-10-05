"""
VayuMitra (वायु मित्र) - Official Government-style AI Assistant Engine.

Handles automated query parsing and multi-turn knowledge retrieval for:
1. Domestic flight corridor benchmark pricing and carrier fare comparison.
2. National Laspeyres CPI index and month-over-month inflation trends.
3. Ministry of Civil Aviation (AirSewa) and DGCA passenger grievance helplines.
4. WhatsApp webhook integration (Twilio TwiML).
"""

from datetime import datetime
from decimal import Decimal
import logging
import re
import statistics
from typing import Any, Dict, List, Optional, Tuple

from django.db.models import Avg, Min, Q
from django.utils import timezone

from .models import Airport, DailyCPIIndex, FareObservation, FlightRoute

logger = logging.getLogger(__name__)

# Common Indian airport aliases to 3-letter IATA code mapping
CITY_TO_IATA: Dict[str, str] = {
    "DELHI": "DEL",
    "NEW DELHI": "DEL",
    "MUMBAI": "BOM",
    "BOMBAY": "BOM",
    "BENGALURU": "BLR",
    "BANGALORE": "BLR",
    "KOLKATA": "CCU",
    "CALCUTTA": "CCU",
    "CHENNAI": "MAA",
    "MADRAS": "MAA",
    "HYDERABAD": "HYD",
    "GOA": "GOI",
    "DABOLIM": "GOI",
    "MOPA": "GOX",
    "AHMEDABAD": "AMD",
    "PUNE": "PNQ",
    "JAIPUR": "JAI",
    "KOCHI": "COK",
    "COCHIN": "COK",
    "GUWAHATI": "GAU",
    "LEH": "IXL",
    "LADAKH": "IXL",
    "PORT BLAIR": "IXZ",
    "SRINAGAR": "SXR",
    "VARANASI": "VNS",
    "BANARAS": "VNS",
    "PATNA": "PAT",
    "LUCKNOW": "LKO",
    "AMRITSAR": "ATQ",
    "BHOPAL": "BHO",
    "INDORE": "IDR",
    "CHANDIGARH": "IXC",
    "COIMBATORE": "CJB",
    "MANGALORE": "IXE",
    "TRIVANDRUM": "TRV",
    "THIRUVANANTHAPURAM": "TRV",
}


def _extract_corridor_codes(query: str) -> Optional[Tuple[str, str]]:
    """
    Extracts origin and destination airport IATA codes from natural language inputs.
    Examples:
        - "DEL to BOM" -> ("DEL", "BOM")
        - "price from CCU to DEL" -> ("CCU", "DEL")
        - "flight Delhi to Mumbai" -> ("DEL", "BOM")
        - "BLR - HYD" -> ("BLR", "HYD")
    """
    cleaned = query.strip()

    # 1. Direct 3-letter IATA regex match (e.g. "DEL to BOM", "DEL-BOM", "DEL -> BOM")
    iata_pattern = re.compile(
        r"\b([a-zA-Z]{3})\s*(?:to|->|--|-|arr|dep|\/)\s*([a-zA-Z]{3})\b",
        re.IGNORECASE,
    )
    match = iata_pattern.search(cleaned)
    if match:
        orig = match.group(1).upper()
        dest = match.group(2).upper()
        # Verify both look like possible airports
        if orig != dest:
            return orig, dest

    # 2. Check for city name tokens (e.g. "Delhi to Mumbai")
    city_pattern = re.compile(
        r"([a-zA-Z\s]{3,20})\s+(?:to|->|--|-)\s+([a-zA-Z\s]{3,20})",
        re.IGNORECASE,
    )
    c_match = city_pattern.search(cleaned)
    if c_match:
        c1 = c_match.group(1).strip().upper()
        c2 = c_match.group(2).strip().upper()

        code1 = CITY_TO_IATA.get(c1)
        code2 = CITY_TO_IATA.get(c2)

        # Fallback to DB search
        if not code1:
            apt1 = Airport.objects.filter(Q(iata_code__iexact=c1) | Q(city_name__icontains=c1)).first()
            if apt1:
                code1 = apt1.iata_code

        if not code2:
            apt2 = Airport.objects.filter(Q(iata_code__iexact=c2) | Q(city_name__icontains=c2)).first()
            if apt2:
                code2 = apt2.iata_code

        if code1 and code2 and code1 != code2:
            return code1, code2

    return None


def _format_route_response(origin_code: str, dest_code: str) -> Dict[str, Any]:
    """
    Fetches real-time corridor fare metrics and crafts an official government briefing.
    """
    route = (
        FlightRoute.objects.select_related("origin", "destination")
        .filter(origin__iata_code__iexact=origin_code, destination__iata_code__iexact=dest_code)
        .first()
    )

    # Check reverse if not found
    is_reversed = False
    if not route:
        rev_route = (
            FlightRoute.objects.select_related("origin", "destination")
            .filter(origin__iata_code__iexact=dest_code, destination__iata_code__iexact=origin_code)
            .first()
        )
        if rev_route:
            route = rev_route
            is_reversed = True

    if not route:
        # Check if airports exist
        apt1 = Airport.objects.filter(iata_code__iexact=origin_code).first()
        apt2 = Airport.objects.filter(iata_code__iexact=dest_code).first()

        if apt1 and apt2:
            reply = (
                f"✈️ *Corridor Inquiry: {apt1.city_name} ({origin_code}) ➔ {apt2.city_name} ({dest_code})*\n\n"
                f"Both airports are recognized in the Indian Civil Aviation registry, but no direct scheduled trunk corridor "
                f"is actively indexed in today's Laspeyres basket.\n\n"
                f"• {apt1.city_name}: {apt1.get_metro_tier_display()}\n"
                f"• {apt2.city_name}: {apt2.get_metro_tier_display()}\n\n"
                f"💡 *Suggestion:* Check connecting metro hubs (e.g., DEL or BOM) or search via the Route Price Finder."
            )
        else:
            reply = (
                f"⚠️ *Corridor Not Recognized:* Could not locate flight records for `{origin_code} ➔ {dest_code}`.\n\n"
                f"Please ensure valid 3-letter IATA codes (e.g., DEL, BOM, BLR, CCU, HYD, MAA, IXL) or major city names."
            )
        return {
            "reply": reply,
            "suggested_chips": ["DEL to BOM", "Current CPI Index", "Govt Helplines"],
        }

    # Retrieve fare observations
    fares_qs = FareObservation.objects.filter(route=route).order_by("-scraped_at")
    base_benchmark = float(route.base_benchmark_fare)

    if fares_qs.exists():
        prices = [float(f.observed_price_inr) for f in fares_qs[:20]]
        avg_fare = round(statistics.mean(prices), 0)
        min_fare = round(min(prices), 0)

        # Find carrier with lowest quote
        lowest_obs = fares_qs.order_by("observed_price_inr").first()
        lowest_carrier = lowest_obs.get_carrier_display() if lowest_obs else "Domestic Carrier"
        lowest_price = float(lowest_obs.observed_price_inr) if lowest_obs else min_fare
        lowest_advance = lowest_obs.advance_booking_days if lowest_obs else 7
    else:
        avg_fare = base_benchmark
        min_fare = base_benchmark
        lowest_carrier = "IndiGo"
        lowest_price = base_benchmark
        lowest_advance = 14

    dev_pct = round(((avg_fare - base_benchmark) / base_benchmark) * 100, 1)
    dev_str = f"+{dev_pct}%" if dev_pct > 0 else f"{dev_pct}%"

    direction_note = " (Reverse corridor benchmark applied)" if is_reversed else ""
    tier_note = (
        "Tier 3 UDAN Regional Corridor"
        if ("T3" in (route.origin.metro_tier, route.destination.metro_tier))
        else ("Tier 2 Feeder Sector" if ("T2" in (route.origin.metro_tier, route.destination.metro_tier)) else "Tier 1 Metro Corridor")
    )

    # Volatility Status
    if dev_pct > 20.0:
        volatility_status = "🔴 *High Volatility Surge* (Exceeds +20% DGCA surveillance threshold)"
    elif dev_pct < -5.0:
        volatility_status = "🟢 *Discounted Capacity* (Below base benchmark)"
    else:
        volatility_status = "🟡 *Stable Yield Band* (Normal statutory variance)"

    reply = (
        f"✈️ *VayuIndex Official Corridor Surveillance Report*{direction_note}\n\n"
        f"📍 *Sector:* {route.origin.city_name} ({route.origin.iata_code}) ➔ {route.destination.city_name} ({route.destination.iata_code})\n"
        f"🏷️ *Classification:* {tier_note} | *Weight:* {route.passenger_traffic_weight}\n\n"
        f"📊 *Pricing Metrics:*\n"
        f"• *Observed Market Average:* ₹{avg_fare:,.0f}\n"
        f"• *Baseline Benchmark (p₀):* ₹{base_benchmark:,.0f}\n"
        f"• *Price Relatives Deviation:* {dev_str}\n"
        f"• *Lowest Available Quote:* ₹{lowest_price:,.0f} via *{lowest_carrier}* (~{lowest_advance}d advance window)\n\n"
        f"⚖️ *Regulatory Surveillance:* {volatility_status}\n\n"
        f"_Data source: Algorithmic fare ingestion aligned with MoSPI CPI methodology._"
    )

    alt_chips = ["Current CPI Index", "Govt Helplines"]
    if route.origin.iata_code != "BOM":
        alt_chips.append("BOM to DEL")
    else:
        alt_chips.append("BLR to HYD")

    return {
        "reply": reply,
        "suggested_chips": alt_chips,
    }


def _format_cpi_response() -> Dict[str, Any]:
    """
    Returns latest National Laspeyres CPI Airfare Index and derived inflation metrics.
    """
    latest = DailyCPIIndex.objects.order_by("-calculation_date").first()

    if latest:
        idx_val = latest.laspeyres_index_value
        mom_val = latest.inflation_rate_mom
        metro_val = getattr(latest, "metro_sub_index", idx_val)
        regional_val = getattr(latest, "regional_sub_index", idx_val)
        calc_date = latest.calculation_date.strftime("%d %B %Y")
        obs_count = latest.total_observations_analyzed or FareObservation.objects.count()
    else:
        idx_val = 100.00
        mom_val = 0.00
        metro_val = 100.00
        regional_val = 100.00
        calc_date = timezone.localdate().strftime("%d %B %Y")
        obs_count = FareObservation.objects.count()

    mom_str = f"+{mom_val:.2f}%" if mom_val > 0 else f"{mom_val:.2f}%"

    if mom_val > 3.0:
        pressure_status = "🔴 *Surging Inflationary Pressure* (Elevated festive or fuel pass-through)"
    elif mom_val < -1.0:
        pressure_status = "🟢 *Deflating / Yield Correction Phase* (Carrier discounting on major trunks)"
    else:
        pressure_status = "🟡 *Stable / Nominal Movement* (Within target monetary trajectory)"

    reply = (
        f"📊 *National Airfare Volatility Index & CPI Augmentation Report*\n"
        f"🗓️ *Reference Date:* {calc_date}\n\n"
        f"• *Current Laspeyres Airfare Index:* *{idx_val:.2f}* (Base 100.0)\n"
        f"• *Month-over-Month (MoM) Inflation Rate:* *{mom_str}*\n"
        f"• *Tier-1 Metro Corridors Sub-Index:* {metro_val:.2f}\n"
        f"• *Tier-2/3 Regional UDAN Sub-Index:* {regional_val:.2f}\n"
        f"• *Statistical Market Sample:* {obs_count:,} fare quotes analyzed\n\n"
        f"📈 *Macroeconomic Assessment:* {pressure_status}\n\n"
        f"_This high-frequency index augments the Transport & Communication sub-group "
        f"of the Consumer Price Index (CPI-Rural/Urban) published by MoSPI._"
    )

    return {
        "reply": reply,
        "suggested_chips": ["DEL to BOM", "Policy Sandbox", "Govt Helplines"],
    }


def _format_helpline_response() -> Dict[str, Any]:
    """
    Returns official government civil aviation contact points and DGCA passenger rights.
    """
    reply = (
        f"🏛️ *Official Civil Aviation & Passenger Grievance Helplines*\n\n"
        f"1. *Ministry of Civil Aviation (AirSewa Portal)*\n"
        f"   • *Toll-Free Helpline:* 1800-11-3006\n"
        f"   • *Web Portal:* https://airsewa.gov.in\n"
        f"   • *Scope:* Flight delays, lost baggage, refund delays, ticketing grievances\n\n"
        f"2. *DGCA Passenger Rights & Safety Cell*\n"
        f"   • *Helpline:* 011-24622495 / 011-24610368\n"
        f"   • *Regulatory Charter:* DGCA CAR Section 3, Series M, Part IV\n"
        f"   • *Statutory Provisions:* Mandates meals/refreshments for >2hr delays, "
        f"alternate flights or up to ₹10,000 compensation for cancelled flights without 24hr notice.\n\n"
        f"3. *National Consumer Helpline (NCH - Ministry of Consumer Affairs)*\n"
        f"   • *National Toll-Free:* 1915\n"
        f"   • *SMS Support:* 8800001915\n"
        f"   • *Portal:* https://consumerhelpline.gov.in\n\n"
        f"💡 *Tip:* To report arbitrary dynamic fare gouging, file a petition with both AirSewa and the DGCA Consumer Protection Cell."
    )
    return {
        "reply": reply,
        "suggested_chips": ["Current CPI Index", "DEL to BOM", "AirSewa Info"],
    }


def _format_default_menu_response(user_name: Optional[str] = None) -> Dict[str, Any]:
    """
    Default welcome prompt and guidance menu.
    """
    salutation = f"Namaste {user_name}! 🙏" if user_name else "Namaste! 🙏"
    reply = (
        f"{salutation} I am *VayuMitra* (वायु मित्र) — your official AI Public Assistant for "
        f"the *VayuIndex* National Airfare Volatility & CPI Augmentation Portal.\n\n"
        f"I can assist you with real-time civil aviation economics and passenger support:\n\n"
        f"1. ✈️ *Corridor Pricing:* Ask *'Price DEL to BOM'* or *'flights CCU to DEL'* for benchmark fare and carrier comparisons.\n"
        f"2. 📊 *Inflation & CPI:* Ask *'Current CPI Index'* or *'inflation'* for daily Laspeyres price metrics.\n"
        f"3. 🏛️ *Passenger Grievances:* Ask *'Helpline'*, *'AirSewa'*, or *'DGCA rules'* for passenger rights and dispute resolution numbers.\n"
        f"4. 🧪 *Shock Sandbox:* Ask *'Simulate shock'* to explore macroeconomic fuel & UDAN surge scenarios.\n\n"
        f"How may I assist your journey or policy research today?"
    )
    return {
        "reply": reply,
        "suggested_chips": ["DEL to BOM", "Current CPI Index", "Govt Helplines", "BLR to DEL"],
    }


def process_vayumitra_query(message: str, user_name: Optional[str] = None) -> Dict[str, Any]:
    """
    Main conversational dispatcher for VayuMitra.
    Parses intent from query text and returns response dict.
    """
    if not message or not isinstance(message, str):
        result = _format_default_menu_response(user_name)
        result["timestamp"] = timezone.now().isoformat()
        return result

    raw = message.strip()
    lower = raw.lower()

    # 1. Route Inquiry Intent (Check if origin and destination can be extracted)
    corridor = _extract_corridor_codes(raw)
    if corridor:
        orig, dest = corridor
        result = _format_route_response(orig, dest)
        result["timestamp"] = timezone.now().isoformat()
        return result

    # 2. CPI / Inflation / Index Intent
    if any(k in lower for k in ["cpi", "index", "inflation", "laspeyres", "rate", "rates", "macro", "deflation"]):
        result = _format_cpi_response()
        result["timestamp"] = timezone.now().isoformat()
        return result

    # 3. Helpline / AirSewa / DGCA / Grievance / Refund Intent
    if any(k in lower for k in [
        "helpline", "help", "complaint", "refund", "dgca", "airsewa", "rights",
        "delay", "cancellation", "compensat", "grievance", "consumer", "phone", "contact"
    ]):
        result = _format_helpline_response()
        result["timestamp"] = timezone.now().isoformat()
        return result

    # 4. Sandbox / Simulation Intent
    if any(k in lower for k in ["sandbox", "simulate", "shock", "fuel", "jet fuel", "monte carlo"]):
        reply = (
            f"🧪 *Macroeconomic Inflation Shock Simulation Sandbox*\n\n"
            f"You can stress-test the national airfare basket against:\n"
            f"• *Aviation Turbine Fuel (ATF) Shocks* (-20% to +50%)\n"
            f"• *Regional UDAN Festive Surges* (0% to +60%)\n"
            f"• *Fleet Capacity Groundings* (0% to +30%)\n\n"
            f"👉 Access the interactive deck at: */sandbox* in the portal or ask me for specific corridors!"
        )
        return {
            "reply": reply,
            "suggested_chips": ["Current CPI Index", "DEL to BOM", "Govt Helplines"],
            "timestamp": timezone.now().isoformat(),
        }

    # 5. Fallback Default Menu
    result = _format_default_menu_response(user_name)
    result["timestamp"] = timezone.now().isoformat()
    return result
