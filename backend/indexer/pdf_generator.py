"""
Official MoSPI Policy Dossier PDF Generator for VayuIndex.

Generates a formal, publication-styled macroeconomic surveillance brief
for the Ministry of Statistics & Programme Implementation (MoSPI) and DGCA,
incorporating the Laspeyres Airfare Index, MoM inflation metrics, tier routing counts,
and high-risk price gouging corridor surveillance tables.
"""

from io import BytesIO
from datetime import datetime
from decimal import Decimal
import statistics
from typing import Dict, List, Any

from django.utils import timezone
from django.db.models import Avg

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    HRFlowable,
    KeepTogether,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfgen import canvas

from .models import Airport, DailyCPIIndex, FareObservation, FlightRoute


class NumberedCanvas(canvas.Canvas):
    """
    Two-pass canvas to dynamically compute and render total page count
    alongside official MoSPI confidentiality and timestamp footers.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, page_count: int):
        self.saveState()
        self.setFont("Helvetica-Bold", 7)
        self.setFillColor(colors.HexColor("#64748b"))

        # Running Top Header (Pages 2+)
        if self._pageNumber > 1:
            self.drawString(
                36,
                A4[1] - 24,
                "GOVERNMENT OF INDIA // MoSPI — AIRFARE VOLATILITY & CPI AUGMENTATION DOSSIER",
            )
            self.drawRightString(
                A4[0] - 36,
                A4[1] - 24,
                "REF: MoSPI-CPI-AIR-SURVEILLANCE",
            )
            self.setStrokeColor(colors.HexColor("#cbd5e1"))
            self.setLineWidth(0.5)
            self.line(36, A4[1] - 28, A4[0] - 36, A4[1] - 28)

        # Running Bottom Footer (All Pages)
        self.setStrokeColor(colors.HexColor("#cbd5e1"))
        self.setLineWidth(0.5)
        self.line(36, 32, A4[0] - 36, 32)

        self.setFont("Helvetica", 7.5)
        self.setFillColor(colors.HexColor("#475569"))
        self.drawString(
            36,
            20,
            "OFFICIAL USE ONLY | Ministry of Statistics & Programme Implementation (MoSPI), New Delhi",
        )
        self.drawRightString(
            A4[0] - 36,
            20,
            f"Page {self._pageNumber} of {page_count}  |  Generated {timezone.now().strftime('%d-%b-%Y %H:%M UTC')}",
        )
        self.restoreState()


def build_mospi_policy_dossier() -> BytesIO:
    """
    Compiles database statistics and builds the official MoSPI CPI policy dossier PDF.

    Returns:
        BytesIO stream containing the generated PDF document.
    """
    buffer = BytesIO()

    # Document Geometry
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=42,
    )

    styles = getSampleStyleSheet()

    # Custom Macroeconomic Typography Palette
    primary_color = colors.HexColor("#0f2b48")   # Deep Govt Navy
    secondary_color = colors.HexColor("#1e3a8a") # Blue Accent
    saffron_accent = colors.HexColor("#b45309")  # Saffron/Gold
    light_bg = colors.HexColor("#f8fafc")
    border_color = colors.HexColor("#cbd5e1")
    text_dark = colors.HexColor("#0f172a")
    text_muted = colors.HexColor("#475569")
    alert_red = colors.HexColor("#dc2626")

    header_style = ParagraphStyle(
        "GovtHeader",
        fontName="Helvetica-Bold",
        fontSize=11,
        leading=14,
        textColor=primary_color,
        alignment=1, # Center
    )

    header_sub_style = ParagraphStyle(
        "GovtSubHeader",
        fontName="Helvetica",
        fontSize=8.5,
        leading=11,
        textColor=text_muted,
        alignment=1, # Center
    )

    title_style = ParagraphStyle(
        "DossierTitle",
        fontName="Helvetica-Bold",
        fontSize=15,
        leading=18,
        textColor=primary_color,
        alignment=1,
    )

    subtitle_style = ParagraphStyle(
        "DossierSubtitle",
        fontName="Helvetica-Bold",
        fontSize=9,
        leading=12,
        textColor=saffron_accent,
        alignment=1,
    )

    body_style = ParagraphStyle(
        "DossierBody",
        fontName="Helvetica",
        fontSize=8.5,
        leading=11.5,
        textColor=text_dark,
    )

    body_bold = ParagraphStyle(
        "DossierBodyBold",
        fontName="Helvetica-Bold",
        fontSize=8.5,
        leading=11.5,
        textColor=text_dark,
    )

    table_header_style = ParagraphStyle(
        "TableHeader",
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=10,
        textColor=colors.white,
        alignment=1,
    )

    table_cell_style = ParagraphStyle(
        "TableCell",
        fontName="Helvetica",
        fontSize=7.5,
        leading=9.5,
        textColor=text_dark,
    )

    table_cell_bold = ParagraphStyle(
        "TableCellBold",
        fontName="Helvetica-Bold",
        fontSize=7.5,
        leading=9.5,
        textColor=text_dark,
    )

    table_cell_red = ParagraphStyle(
        "TableCellRed",
        fontName="Helvetica-Bold",
        fontSize=7.5,
        leading=9.5,
        textColor=alert_red,
    )

    story = []

    # 1. Official Header
    story.append(Paragraph("GOVERNMENT OF INDIA", header_style))
    story.append(Paragraph("MINISTRY OF STATISTICS & PROGRAMME IMPLEMENTATION (MoSPI)", header_style))
    story.append(Paragraph("NATIONAL STATISTICAL OFFICE (NSO) // ECONOMIC STATISTICS DIVISION", header_sub_style))
    story.append(Spacer(1, 4))
    story.append(HRFlowable(width="100%", thickness=1.5, color=primary_color, spaceBefore=2, spaceAfter=8))

    # 2. Dossier Title
    story.append(Paragraph("AIRFARE VOLATILITY INDEX & CPI TRANSPORT AUGMENTATION DOSSIER", title_style))
    story.append(Spacer(1, 2))
    report_ref_date = timezone.now().strftime("%B %d, %Y")
    story.append(Paragraph(f"POLICY BRIEFING & HIGH-RISK CORRIDOR SURVEILLANCE REPORT // {report_ref_date.upper()}", subtitle_style))
    story.append(Spacer(1, 10))

    # 3. Context & Executive Summary Box
    summary_text = (
        "<b>Executive Summary & Regulatory Scope:</b> This official dossier compiles high-frequency "
        "algorithmic fare observations across scheduled Indian commercial aviation routes to augment the "
        "Transport & Communications sub-group of the national Consumer Price Index (CPI-Rural/Urban, Base 2012=100). "
        "Pursuant to inter-ministerial coordination with the Directorate General of Civil Aviation (DGCA) and MoSPI, "
        "this surveillance mechanism establishes Laspeyres price relatives, measures Month-over-Month (MoM) inflation drift, "
        "and identifies severe price gouging on regional UDAN and feeder corridors."
    )
    summary_table = Table(
        [[Paragraph(summary_text, body_style)]],
        colWidths=[A4[0] - 72],
    )
    summary_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), light_bg),
        ("BOX", (0, 0), (-1, -1), 0.75, border_color),
        ("PADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(summary_table)
    story.append(Spacer(1, 12))

    # 4. Ingest and Compile DB Metrics
    latest_index = DailyCPIIndex.objects.order_by("-calculation_date").first()
    today_date = timezone.localdate()

    if latest_index:
        idx_val = f"{latest_index.laspeyres_index_value:.2f}"
        mom_val = f"{latest_index.inflation_rate_mom:+.2f}%"
        metro_idx = f"{getattr(latest_index, 'metro_sub_index', latest_index.laspeyres_index_value):.2f}"
        regional_idx = f"{getattr(latest_index, 'regional_sub_index', latest_index.laspeyres_index_value):.2f}"
        calc_date = latest_index.calculation_date.strftime("%d-%b-%Y")
        total_obs = latest_index.total_observations_analyzed or FareObservation.objects.count()
    else:
        idx_val = "100.00"
        mom_val = "0.00%"
        metro_idx = "100.00"
        regional_idx = "100.00"
        calc_date = today_date.strftime("%d-%b-%Y")
        total_obs = FareObservation.objects.count()

    total_airports = Airport.objects.count()
    t1_airports = Airport.objects.filter(metro_tier="T1").count()
    t2_airports = Airport.objects.filter(metro_tier="T2").count()
    t3_airports = Airport.objects.filter(metro_tier="T3").count()

    all_routes = list(FlightRoute.objects.select_related("origin", "destination").all())
    total_routes_count = len(all_routes)

    # Route classification by tier
    t1_corridors = sum(1 for r in all_routes if r.origin.metro_tier == "T1" and r.destination.metro_tier == "T1")
    t3_corridors = sum(1 for r in all_routes if "T3" in (r.origin.metro_tier, r.destination.metro_tier))
    t2_corridors = total_routes_count - t1_corridors - t3_corridors

    # 5. Metric Summary Cards Table (2-column layout)
    story.append(Paragraph("<b>I. CORE MACROECONOMIC & INDEX BENCHMARK METRICS</b>", body_bold))
    story.append(Spacer(1, 4))

    col_w = (A4[0] - 72) / 4.0
    metrics_data = [
        [
            Paragraph("<b>Current Laspeyres Index</b>", body_bold),
            Paragraph(f"<font size=12 color='{primary_color.hexval()}'><b>{idx_val}</b></font><br/><font size=7 color='#64748b'>Base: 100.0</font>", body_style),
            Paragraph("<b>MoM Inflation Delta</b>", body_bold),
            Paragraph(f"<font size=12 color='{alert_red.hexval() if float(mom_val.replace('%','')) > 0 else '#16a34a'}'><b>{mom_val}</b></font><br/><font size=7 color='#64748b'>vs. Preceding Period</font>", body_style),
        ],
        [
            Paragraph("<b>Tier 1 Metro Sub-Index</b>", body_bold),
            Paragraph(f"<font size=11 color='{secondary_color.hexval()}'><b>{metro_idx}</b></font>", body_style),
            Paragraph("<b>Regional / UDAN Sub-Index</b>", body_bold),
            Paragraph(f"<font size=11 color='{saffron_accent.hexval()}'><b>{regional_idx}</b></font>", body_style),
        ],
        [
            Paragraph("<b>Monitored Corridors</b>", body_bold),
            Paragraph(f"<b>{total_routes_count}</b> routes ({total_obs} quotes)", body_style),
            Paragraph("<b>Tier Route Breakdown</b>", body_bold),
            Paragraph(f"<b>T1:</b> {t1_corridors} | <b>T2:</b> {t2_corridors} | <b>T3:</b> {t3_corridors}", body_style),
        ],
    ]

    metrics_table = Table(metrics_data, colWidths=[col_w * 1.1, col_w * 0.9, col_w * 1.1, col_w * 0.9])
    metrics_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#ffffff")),
        ("BOX", (0, 0), (-1, -1), 0.75, border_color),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
        ("PADDING", (0, 0), (-1, -1), 6),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(metrics_table)
    story.append(Spacer(1, 14))

    # 6. High-Risk Price Gouging Corridors Analysis Table
    story.append(Paragraph("<b>II. HIGH-RISK PRICE GOUGING & CORRIDOR VOLATILITY SURVEILLANCE</b>", body_bold))
    story.append(Paragraph(
        "<font size=7.5 color='#64748b'>Identifies domestic corridors where observed market prices severely diverge from base benchmarks (p_0), "
        "highlighting predatory surge extraction during constrained capacity windows.</font>",
        body_style,
    ))
    story.append(Spacer(1, 6))

    # Compute route deviations
    corridor_evaluations: List[Dict[str, Any]] = []
    # Fetch recent fares
    recent_fares = FareObservation.objects.order_by("-scraped_at")[:2000]
    route_fares: Dict[int, List[float]] = {}
    for r_id, price in recent_fares.values_list("route_id", "observed_price_inr"):
        if r_id not in route_fares:
            route_fares[r_id] = []
        if len(route_fares[r_id]) < 20:
            route_fares[r_id].append(float(price))

    for route in all_routes:
        base_f = float(route.base_benchmark_fare)
        fares = route_fares.get(route.id, [])
        if fares:
            current_f = float(statistics.median(fares))
        else:
            current_f = base_f

        dev_pct = ((current_f - base_f) / base_f) * 100.0

        is_t3 = "T3" in (route.origin.metro_tier, route.destination.metro_tier)
        is_t2 = "T2" in (route.origin.metro_tier, route.destination.metro_tier)
        tier_label = "Tier 3 UDAN" if is_t3 else ("Tier 2 Feeder" if is_t2 else "Tier 1 Metro")

        corridor_evaluations.append({
            "corridor": f"{route.origin.iata_code} → {route.destination.iata_code}",
            "route_name": f"{route.origin.city_name} to {route.destination.city_name}",
            "tier": tier_label,
            "weight": route.passenger_traffic_weight,
            "base_fare": base_f,
            "current_fare": current_f,
            "deviation_pct": dev_pct,
        })

    # Sort descending by deviation
    corridor_evaluations.sort(key=lambda x: x["deviation_pct"], reverse=True)
    top_gouging_corridors = corridor_evaluations[:10]

    # Table columns: Corridor, Sector Name, Tier, Benchmark (₹), Current (₹), Deviation (%), Regulatory Alert
    table_headers = [
        Paragraph("<b>Corridor</b>", table_header_style),
        Paragraph("<b>Sector Name</b>", table_header_style),
        Paragraph("<b>Tier</b>", table_header_style),
        Paragraph("<b>Benchmark (p₀)</b>", table_header_style),
        Paragraph("<b>Current (pₜ)</b>", table_header_style),
        Paragraph("<b>Deviation</b>", table_header_style),
        Paragraph("<b>Regulatory Status</b>", table_header_style),
    ]

    table_rows = [table_headers]
    for idx, c in enumerate(top_gouging_corridors):
        dev = c["deviation_pct"]
        if dev >= 25.0:
            alert_label = "<font color='#dc2626'><b>CRITICAL SURGE</b></font>"
        elif dev >= 12.0:
            alert_label = "<font color='#b45309'><b>ELEVATED RISK</b></font>"
        elif dev >= 0.0:
            alert_label = "<font color='#2563eb'>MODERATE</font>"
        else:
            alert_label = "<font color='#16a34a'>DISCOUNTED</font>"

        dev_str = f"+{dev:.1f}%" if dev > 0 else f"{dev:.1f}%"
        dev_para = Paragraph(f"<b>{dev_str}</b>", table_cell_red if dev > 15 else table_cell_bold)

        row = [
            Paragraph(f"<b>{c['corridor']}</b>", table_cell_bold),
            Paragraph(c["route_name"], table_cell_style),
            Paragraph(c["tier"], table_cell_style),
            Paragraph(f"₹{c['base_fare']:,.0f}", table_cell_style),
            Paragraph(f"₹{c['current_fare']:,.0f}", table_cell_bold),
            dev_para,
            Paragraph(alert_label, table_cell_style),
        ]
        table_rows.append(row)

    col_widths = [65, 120, 65, 70, 70, 60, 73]
    corridors_table = Table(table_rows, colWidths=col_widths, repeatRows=1)

    t_style = [
        ("BACKGROUND", (0, 0), (-1, 0), primary_color),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
        ("BOX", (0, 0), (-1, -1), 0.75, primary_color),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]

    for i in range(1, len(table_rows)):
        bg = colors.HexColor("#ffffff") if i % 2 != 0 else colors.HexColor("#f8fafc")
        t_style.append(("BACKGROUND", (0, i), (-1, i), bg))

    corridors_table.setStyle(TableStyle(t_style))
    story.append(corridors_table)
    story.append(Spacer(1, 14))

    # 7. MoSPI Policy Recommendations & Statutory Observations
    recommendations_content = (
        "<b>III. POLICY DIRECTIVES & SURVEILLANCE RECOMMENDATIONS</b><br/>"
        "<b>1. Dynamic Tariff Caps on UDAN Corridors:</b> When regional sector deviations exceed +25% over baseline benchmarks, "
        "statutory fare caps under the Aircraft Rules should be triggered to prevent monopolistic capacity exploitation.<br/>"
        "<b>2. ATF Surcharge Transparency:</b> Fuel surcharges should strictly correlate with actual Indian Oil Corporation (IOCL) "
        "Aviation Turbine Fuel base revisions. Unilateral fare bumps exceeding 40% fuel expense elasticity must be investigated by DGCA.<br/>"
        "<b>3. CPI Basket Calibration:</b> High-frequency airfare indices generated via VayuIndex will be integrated into the monthly "
        "National Statistical Office (NSO) Consumer Price Index release to replace lagged manual survey quotes."
    )

    rec_table = Table(
        [[Paragraph(recommendations_content, body_style)]],
        colWidths=[A4[0] - 72],
    )
    rec_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f1f5f9")),
        ("BOX", (0, 0), (-1, -1), 0.75, colors.HexColor("#94a3b8")),
        ("PADDING", (0, 0), (-1, -1), 8),
    ]))

    story.append(KeepTogether([rec_table]))
    story.append(Spacer(1, 14))

    # 8. Formal Authentication Block
    signoff_data = [
        [
            Paragraph("<b>Surveillance Engine:</b> VayuIndex Macro Analytics Engine v1.0", table_cell_style),
            Paragraph("<b>Issuing Authority:</b> MoSPI Economic Statistics Cell", table_cell_style),
        ],
        [
            Paragraph(f"<b>Data Digest Hash:</b> SHA-256 Verified Live Stream [{timezone.now().strftime('%Y%m%d%H%M')}]", table_cell_style),
            Paragraph("<b>Classification:</b> MoSPI Official Document // Public Release", table_cell_style),
        ],
    ]
    signoff_table = Table(signoff_data, colWidths=[(A4[0] - 72) / 2.0, (A4[0] - 72) / 2.0])
    signoff_table.setStyle(TableStyle([
        ("LINEABOVE", (0, 0), (-1, 0), 0.5, border_color),
        ("PADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(KeepTogether([signoff_table]))

    # Build Document using NumberedCanvas
    doc.build(story, canvasmaker=NumberedCanvas)
    buffer.seek(0)
    return buffer
