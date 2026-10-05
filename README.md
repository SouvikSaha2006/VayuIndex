# VayuIndex (वायु इंडेक्स)
### *National Domestic Airfare Volatility Index & Consumer Price Index (CPI) Augmentation Engine*

[![Python](https://img.shields.io/badge/Python-3.12-blue?logo=python&logoColor=white)](https://www.python.org/)
[![Django](https://img.shields.io/badge/Django-5.1-092E20?logo=django&logoColor=white)](https://www.djangoproject.com/)
[![Django REST Framework](https://img.shields.io/badge/DRF-3.15-red?logo=django&logoColor=white)](https://www.django-rest-framework.org/)
[![Angular](https://img.shields.io/badge/Angular-18-DD0031?logo=angular&logoColor=white)](https://angular.dev/)
[![ReportLab](https://img.shields.io/badge/ReportLab-5.0-orange)](https://www.reportlab.com/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

---

## 🏛️ Executive Summary & Macroeconomic Context

In India, headline **Consumer Price Index (CPI)** numbers released by the **Ministry of Statistics and Programme Implementation (MoSPI)** augment the national transport basket using periodic, manual survey quotes. However, contemporary commercial civil aviation relies heavily on algorithmic dynamic yield management. During festival peaks (Diwali, Chhath Puja, Durga Puja) or aviation supply shocks (Aviation Turbine Fuel hikes, aircraft groundings), airfares on regional **UDAN** and non-metro corridors can spike by over **300%** within hours.

**VayuIndex** is a mission-critical, full-stack macroeconomic surveillance platform designed to bridge this high-frequency gap. Built on **Django 5.1** and **Angular 18**, VayuIndex continuously captures fare quotes across carriers and distribution portals, formulates a daily **Laspeyres Airfare Price Index**, tracks Month-over-Month (MoM) inflation deltas, stress-tests price shocks through a Monte-Carlo simulation sandbox, and exports formal **MoSPI Policy Dossiers**.

---

## 🏗️ System Architecture

```mermaid
flowchart TD
    subgraph Data Layer
        A[Carrier Portals / Direct] --> D[Fare Scraper / Ingestion Service]
        B[OTA Aggregators MakeMyTrip / EaseMyTrip / Yatra] --> D
        C[Historical DGCA Benchmarks] --> D
    end

    subgraph Django Core Engine [Backend: Django 5.1 + DRF]
        D -->|Bulk Create| E[(SQLite / PostgreSQL)]
        E --> F[Airport & Route ORM Models]
        E --> G[FareObservation Ingestion Models]
        F & G --> H[Laspeyres Index Formulation Engine]
        H --> I[(DailyCPIIndex Time-Series)]
        
        subgraph Specialized Django Services
            J[Macro Shock Simulation Engine services.py]
            K[ReportLab MoSPI Policy Dossier Generator pdf_generator.py]
            L[VayuMitra Conversational AI & Helpline Engine chatbot.py]
            M[Server-Sent Events SSE Stream Generator views.py]
        end
        
        H --> J
        H --> K
        H --> L
        G --> M
    end

    subgraph REST API & Webhooks
        N[REST API ViewSets DefaultRouter]
        O[SSE Live Fare Stream text/event-stream]
        P[Twilio WhatsApp Webhook TwiML XML]
    end

    Django Core Engine --> N
    Django Core Engine --> O
    Django Core Engine --> P

    subgraph Frontend [Angular 18 Standalone]
        Q[Live Macro Dashboard Component]
        R[Corridor Price Finder & Search]
        S[Laspeyres CPI Methodology & Weights]
        T[Macroeconomic Policy Sandbox]
        U[Floating VayuMitra AI Assistant Widget]
    end

    N --> Q & R & S & T & U
    O --> Q
    P --> V[WhatsApp Mobile Users]
```

---

## 🐍 Deep Dive: Serious Django Implementation

VayuIndex leverages Django as an industrial-grade analytical backend rather than a simple CRUD layer. The backend architecture adheres strictly to separation of concerns across models, algorithmic services, streaming viewsets, and automated testing.

### 1. Robust Django ORM Data Architecture (`backend/indexer/models.py`)

- **`Airport` Model**:
  - Enforces strict 3-letter IATA uppercase validation using Django's `RegexValidator(regex=r"^[A-Z]{3}$")`.
  - Normalizes IATA codes automatically on `save()` and `clean()`.
  - Categorizes domestic hubs into statistical demographic clusters via `MetroTier.choices`:
    - `T1`: Tier-1 Metro (DEL, BOM, BLR, CCU, HYD, MAA)
    - `T2`: Tier-2 Commercial Hub (AMD, PNQ, COK, JAI, LKO)
    - `T3`: Tier-3 Regional / UDAN (IXL, IXZ, GAU, SXR)
  - Stores high-precision coordinates (`latitude`, `longitude`) for spatial yield analysis.

- **`FlightRoute` Model**:
  - Directed pair corridor entity connecting `origin` and `destination` airports via cascading foreign keys.
  - Enforces route uniqueness with `unique_together = ("origin", "destination")`.
  - Encapsulates statistical passenger traffic weight ($W_i$) aligned with DGCA domestic scheduled capacity.
  - Maintains `base_benchmark_fare` ($P_{i,0}$) in INR representing official baseline price levels.

- **`FareObservation` Model**:
  - Ingests high-frequency quotes across operating carriers (`INDIGO`, `AIRINDIA`, `SPICEJET`, `AKASA`) and distribution portals (`DIRECT`, `MAKEMYTRIP`, `EASEMYTRIP`, `YATRA`).
  - Tracks scheduled departure dates and advance booking windows ($3, 7, 14, 21$ days).
  - High-performance database indexing:
    ```python
    indexes = [
        models.Index(fields=["route", "departure_date"]),
        models.Index(fields=["carrier", "scraped_at"]),
    ]
    ```

- **`DailyCPIIndex` Model**:
  - Immutable daily time-series snapshot capturing national `laspeyres_index_value`, `metro_sub_index`, `regional_sub_index`, and derived `inflation_rate_mom`.

---

### 2. Computational Economics & Laspeyres Formulation (`backend/indexer/services.py`)

The airfare index strictly follows the Laspeyres price relative aggregator:

$$\text{Index}_t = \frac{\sum_{i=1}^N (P_{i,t} \cdot W_i)}{\sum_{i=1}^N (P_{i,0} \cdot W_i)} \times 100$$

Where:
- $P_{i,t}$ is the median observed fare for route $i$ on date $t$.
- $P_{i,0}$ is the baseline benchmark fare for route $i$.
- $W_i$ is the passenger traffic weight for route $i$.

The Month-over-Month (MoM) inflation drift is computed dynamically against preceding historical records:

$$\text{Inflation Rate}_{\text{MoM}} = \left( \frac{\text{Index}_t - \text{Index}_{t-1}}{\text{Index}_{t-1}} \right) \times 100$$

---

### 3. Exogenous Shock Simulation Engine (`simulate_inflation_shock`)

Models macroeconomic stress vectors using an elasticity stack:

$$\text{Simulated Price} = P_{\text{current}} \times \left(1 + \frac{\Delta_{\text{Fuel}} \times 0.40}{100}\right) \times \left(1 + \frac{\text{is\_regional} \cdot \Delta_{\text{Regional}}}{100}\right) \times \left(1 + \frac{\Delta_{\text{Capacity}} \times 0.80}{100}\right)$$

- **Aviation Turbine Fuel (ATF) Factor**: Jet fuel represents ~40% of airline operational expense (OPEX) in India.
- **Regional UDAN Factor**: Asymmetrically affects Tier-2 & Tier-3 corridors during festive supply shortages.
- **Fleet Grounding Factor**: Contracted seat capacity exerts price pressure scaled by a $0.80$ transport elasticity coefficient.
- Re-aggregates simulated Laspeyres indices and isolates the **Top 5 highest fare spike corridors**.

---

### 4. Publication-Ready PDF Dossier Engine (`backend/indexer/pdf_generator.py`)

Built with **ReportLab 5.0**, VayuIndex compiles an executive publication dossier for policy stakeholders:
- **Two-Pass `NumberedCanvas`**: Computes total dynamic page count (`Page X of Y`), running headers, and timestamped security hashes.
- **Official Identity**: Deep navy styling (`#0f2b48`), Indian national tricolor accents, and official Ministry headings.
- **Surveillance Tables**: Highlights price gouging corridors where observed fares exceed statutory benchmarks, flagging alert statuses (*Critical Surge*, *Elevated Risk*, *Moderate*).
- **Direct Streaming**: Delivered via Django `FileResponse` with automated `Content-Disposition: attachment; filename="VayuIndex_MoSPI_Dossier.pdf"`.

---

### 5. Conversational AI & WhatsApp Helpdesk (`backend/indexer/chatbot.py`)

- **VayuMitra Knowledge Engine**:
  - Regex-driven corridor parsing (e.g., `"DEL to BOM"`, `"price CCU to DEL"`, `"flights Bangalore to Mumbai"`).
  - Resolves aliases to 3-letter IATA codes and retrieves real-time pricing, baseline benchmarks, and cheapest operating carriers.
  - Reports national CPI inflation, sub-index breakdowns, and market pressure categories.
  - Integrates official helplines: **AirSewa (1800-11-3006)**, **DGCA Passenger Rights (011-24622495)**, and **National Consumer Helpline (1915)**.
- **Twilio WhatsApp Integration**:
  - `@csrf_exempt` webhook accepting incoming WhatsApp payloads.
  - Returns compliant **TwiML XML** (`MessagingResponse`), enabling identical conversational intelligence on both WhatsApp and the web client.

---

### 6. Real-Time Server-Sent Events (SSE) Stream

- `live_fare_stream_view` utilizes Django's `StreamingHttpResponse` with `content_type="text/event-stream"`.
- Emits real-time simulated fare updates and freshly computed index metrics every 3 seconds without client-side polling overhead.

---

### 7. Customized Django Admin (`backend/indexer/admin.py`)

- Displays color-coded HTML badges for inflation metrics:
  - **Red (`#dc2626`)** for inflationary surges ($>0\%$).
  - **Green (`#16a34a`)** for price deflation ($<0\%$).
  - **Slate (`#4b5563`)** for stable yield windows ($0\%$).
- Comprehensive filtering across metro tiers, airlines, advance booking horizons, and date ranges.

---

### 8. Rigorous Automated Test Suite (`backend/indexer/tests.py`)

The test suite covers **31 automated test cases** verifying every architectural layer:
- Model validation and IATA regex cleaning.
- Laspeyres aggregation accuracy and edge-case handling.
- Monte-Carlo shock simulation formula correctness.
- ReportLab `%PDF` binary output integrity.
- Web widget chatbot responses and Twilio TwiML XML formatting.

Run the test suite with:
```bash
python manage.py test
# Ran 31 tests in 0.521s -> OK
```

---

## 🌐 Complete REST API Specification

| Method | Endpoint | Description | Auth / Flags |
|---|---|---|---|
| `GET` | `/` | Backend service discovery and health status | Public |
| `GET` | `/api/` | DRF browsable API root discovery | Public |
| `GET` | `/api/airports/` | List domestic Indian airports (IATA, tier, lat/long) | Paginated |
| `GET` | `/api/routes/` | List directed corridors with passenger weights | Paginated |
| `GET` | `/api/routes/search/?origin=DEL&destination=BOM` | Intelligent corridor search, carrier quotes & window pricing | Query Params |
| `GET` | `/api/fares/` | Scraped fare quote history | Filterable |
| `GET` | `/api/fares/live-stream/` | Real-time Server-Sent Events (SSE) live feed | Streaming |
| `POST` | `/api/fares/trigger-ingestion/` | Triggers stochastic fare ingestion batch | Idempotent |
| `GET` | `/api/cpi-indices/` | Historical daily Laspeyres CPI index time-series | Paginated |
| `GET` | `/api/cpi-indices/latest/` | Most recent daily CPI computation | Single Object |
| `GET` | `/api/index/summary/` | Macro summary: 7-day trend, top surging/discounted routes | Public |
| `POST` | `/api/index/simulate-shock/` | Monte-Carlo macroeconomic inflation shock simulation | JSON Payload |
| `GET` | `/api/index/export-policy-report/` | Official publication-grade MoSPI Policy Dossier PDF | Binary PDF Stream |
| `POST` | `/api/chatbot/message/` | VayuMitra conversational AI web endpoint | JSON Payload |
| `POST` | `/api/webhook/whatsapp/` | Twilio WhatsApp incoming webhook | CSRF-Exempt, TwiML |

---

## 💻 Frontend Architecture (Angular 18 Standalone)

The frontend is an enterprise-grade client built using **Angular 18 standalone components**, **RxJS reactive pipelines**, and **SCSS design tokens**.

### Key Views & Components:
1. **Live Dashboard (`/dashboard`)**:
   - Macro index indicator cards with live pulsing badges.
   - Historical 7-day CPI trend chart with SVG path interpolation.
   - Real-time SSE live ticker displaying incoming carrier quotes.
   - Route inventory table with tier filtering (`Tier 1`, `Tier 2`, `Tier 3 UDAN`).
2. **Corridor Price Finder (`/search`)**:
   - Airport autocomplete and bi-directional corridor search.
   - Carrier pricing breakdown (IndiGo, Air India, SpiceJet, Akasa Air).
   - Advance booking horizon yield curve ($3\text{d}, 7\text{d}, 14\text{d}, 21\text{d}$).
3. **CPI Methodology & Statistical Weights (`/methodology`)**:
   - Mathematical exposition of the Laspeyres Index formulation.
   - Passenger traffic weight breakdown aligned with DGCA commercial scheduling.
4. **Policy Sandbox & Simulation Deck (`/sandbox`)**:
   - Interactive slider deck:
     - *ATF Jet Fuel Price Fluctuation* ($-20\%$ to $+50\%$)
     - *Festival / Holiday Surge Demand* ($0\%$ to $+60\%$)
     - *Fleet Capacity Constraints / Groundings* ($0\%$ to $+30\%$)
   - Quick preset scenarios: *Diwali Festive Rush*, *Crude Oil & ATF Spike*, *Engine Grounding Shock*, and *Neutral Baseline*.
   - Animated flashing differential indicators (`+X.XX pts`).
   - Top 5 Most Vulnerable Regional Routes vulnerability table.
   - One-click trigger for downloading the MoSPI PDF Dossier.
5. **VayuMitra Floating Assistant Widget (`<app-vayumitra-chat>`)**:
   - Persistent launcher anchored to viewport bottom-right.
   - Government portal design language with national tricolor accents.
   - Suggestion chips, markdown parsing for bold text and lists, and auto-scrolling message bubbles.

---

## 🚀 Quickstart Guide

### Prerequisites
- **Python 3.12+**
- **Node.js 18+** & **npm**

---

### Step 1: Clone the Repository
```bash
git clone https://github.com/SouvikSaha2006/VayuIndex.git
cd VayuIndex
```

---

### Step 2: Backend Setup (Django)

```bash
cd backend

# Create and activate virtual environment
python -m venv venv

# Windows
.\venv\Scripts\activate
# Linux / macOS
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run migrations
python manage.py migrate

# Seed domestic airports, flight routes, and initial fare observations
python manage.py seed_data

# (Optional) Seed backtest historical records
python manage.py seed_routes

# Run test suite to verify installation
python manage.py test

# Start the Django development server
python manage.py runserver 127.0.0.1:8000
```
*Backend API will be live at `http://127.0.0.1:8000/`.*

---

### Step 3: Frontend Setup (Angular)

In a separate terminal:
```bash
cd vayu-client

# Install frontend dependencies
npm install

# Start the Angular development server with backend proxying
npm start
```
*Frontend will be live at `http://localhost:4200/`.*

---

## 🧪 Simulation Example (cURL)

Test the macroeconomic shock simulation directly:
```bash
curl -X POST http://127.0.0.1:8000/api/index/simulate-shock/ \
  -H "Content-Type: application/json" \
  -d '{
    "fuel_shock_pct": 15.0,
    "regional_surge_pct": 25.0,
    "capacity_cut_pct": 8.0
  }'
```

**Response:**
```json
{
  "baseline_index": 99.71,
  "simulated_index": 128.45,
  "index_delta": 28.74,
  "simulated_mom_inflation": 11.23,
  "most_impacted_routes": [
    {
      "corridor": "DEL -> IXZ",
      "route_name": "New Delhi to Port Blair",
      "tier_tag": "Tier 3 UDAN",
      "baseline_fare": 7271.91,
      "simulated_fare": 9785.40,
      "fare_spike_inr": 2513.49,
      "spike_percentage": 34.56
    }
  ]
}
```

---

## 📄 Download MoSPI Policy Dossier (PDF)

Download the publication dossier directly via browser or cURL:
```bash
curl -O http://127.0.0.1:8000/api/index/export-policy-report/
```

---

## 💬 WhatsApp Integration via Twilio

To hook up VayuMitra to WhatsApp:
1. In the **Twilio Console**, configure the WhatsApp Sandbox Webhook URL:
   ```
   https://<your-ngrok-domain>.ngrok-free.app/api/webhook/whatsapp/
   ```
   HTTP Method: `POST`.
2. Send messages like `"Price DEL to BOM"` or `"Current CPI"` on WhatsApp to receive real-time, official aviation intelligence.

---

## 🛡️ License

This project is licensed under the **MIT License**.

Developed with pride for **National Airfare Price Transparency & CPI Augmentation**.
