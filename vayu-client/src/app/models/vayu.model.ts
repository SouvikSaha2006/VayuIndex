export type MetroTier = 'T1' | 'T2';

export type CarrierCode = 'INDIGO' | 'AIRINDIA' | 'SPICEJET' | 'AKASA';

export type SourcePortalCode = 'DIRECT' | 'MAKEMYTRIP' | 'EASEMYTRIP' | 'YATRA';

/**
 * Domestic Indian Airport Entity
 */
export interface Airport {
  id: number;
  iata_code: string;
  city_name: string;
  metro_tier: MetroTier;
}

/**
 * Directed Domestic Flight Route connecting two airports
 */
export interface FlightRoute {
  id: number;
  origin: number;
  destination: number;
  passenger_traffic_weight: number;
  base_benchmark_fare: number | string;
  route_name: string;
  origin_code: string;
  origin_city: string;
  destination_code: string;
  destination_city: string;
  current_avg_fare: number | null;
}

/**
 * Scraped/Observed Airfare Snapshot
 */
export interface FareObservation {
  id: number;
  route: number;
  route_str?: string;
  route_name?: string;
  carrier: CarrierCode | string;
  carrier_display?: string;
  source_portal: SourcePortalCode | string;
  source_portal_display?: string;
  observed_price_inr: number | string;
  formatted_price?: string;
  formatted_currency?: string;
  departure_date: string; // ISO 8601 Date (YYYY-MM-DD)
  advance_booking_days: number;
  scraped_at: string; // ISO 8601 DateTime
}

/**
 * Laspeyres CPI Airfare Price Index Metric
 */
export interface DailyCPIIndex {
  id: number;
  calculation_date: string; // ISO 8601 Date (YYYY-MM-DD)
  laspeyres_index_value: number;
  inflation_rate_mom: number;
  total_observations_analyzed: number;
  recorded_at: string; // ISO 8601 DateTime
}

/**
 * Standard Django REST Framework PageNumberPagination envelope
 */
export interface PaginatedResponse<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

/**
 * Pipeline Ingestion API Response payload
 */
export interface IngestionResponse {
  status: string;
  records_logged: number;
  updated_index: number;
}
