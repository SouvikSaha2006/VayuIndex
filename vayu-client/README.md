# VayuIndex Client

Frontend Angular client for **VayuIndex** (Domestic Indian Airfare Volatility & Laspeyres CPI Augmentation Engine).

## Features
- **Modern Angular Architecture**: Standalone components, modern `inject()` dependency injection, Zone event coalescing, and Fetch API HTTP client.
- **Strict Data Contracts**: Full TypeScript models matching Django REST Framework serializers (`Airport`, `FlightRoute`, `FareObservation`, `DailyCPIIndex`).
- **Reactive Data Service**: `VayuService` utilizing RxJS streams for real-time corridor metrics, fare observations, and pipeline ingestion triggers.
- **Built-in Proxy**: Pre-configured reverse proxy to Django backend at `http://127.0.0.1:8000`.

## Quick Start

### 1. Install Dependencies
```bash
npm install
```

### 2. Start Django Backend (Port 8000)
In another terminal, ensure the Django server is running:
```bash
cd ../backend
python manage.py runserver
```

### 3. Start Angular Development Server
```bash
npm start
```
Navigate to `http://localhost:4200/`. API calls to `/api/*` are automatically forwarded to Django via `proxy.conf.json`.

## Build
```bash
npm run build
```
Compiled output will be saved in `dist/vayu-client`.
