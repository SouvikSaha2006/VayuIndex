export type MetroTier = 'T1' | 'T2' | 'T3';

export type CarrierCode = 'INDIGO' | 'AIRINDIA' | 'SPICEJET' | 'AKASA';

export type SourcePortalCode = 'DIRECT' | 'MAKEMYTRIP' | 'EASEMYTRIP' | 'YATRA';

/**
 * Domestic Indian Airport Entity
 */
export interface Airport {
  id: number;
  iata_code: string;
  city_name: string;
  state_name?: string;
  latitude?: number;
  longitude?: number;
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
  origin_tier?: MetroTier;
  destination_code: string;
  destination_city: string;
  destination_tier?: MetroTier;
  tier_classification?: string;
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
  departure_date: string;
  advance_booking_days: number;
  tier_tag?: string;
  volatility_percentage?: number;
  scraped_at: string;
}

/**
 * Laspeyres CPI Airfare Price Index Metric
 */
export interface DailyCPIIndex {
  id: number;
  calculation_date: string;
  laspeyres_index_value: number;
  metro_sub_index?: number;
  regional_sub_index?: number;
  inflation_rate_mom: number;
  total_observations_analyzed: number;
  recorded_at: string;
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

/**
 * Macroeconomic Inflation Shock Simulation Payload
 */
export interface ShockSimulationPayload {
  fuel_shock_pct: number;
  regional_surge_pct: number;
  capacity_cut_pct: number;
}

/**
 * Corridors most impacted by simulation shock
 */
export interface ImpactedRoute {
  route_id: number;
  corridor: string;
  route_name: string;
  origin_code: string;
  origin_city: string;
  destination_code: string;
  destination_city: string;
  tier_tag: string;
  is_regional: boolean;
  baseline_fare: number;
  current_fare: number;
  simulated_fare: number;
  fare_spike_inr: number;
  spike_percentage: number;
  weight: number;
}

/**
 * Inflation Shock Simulation API Response
 */
export interface ShockSimulationResult {
  baseline_index: number;
  simulated_index: number;
  index_delta: number;
  simulated_mom_inflation: number;
  most_impacted_routes: ImpactedRoute[];
}

/**
 * VayuMitra Conversational Assistant Chat Message
 */
export interface ChatMessage {
  id: string;
  sender: 'user' | 'bot';
  text: string;
  timestamp: string;
  chips?: string[];
}

/**
 * VayuMitra API Response
 */
export interface ChatbotResponse {
  reply: string;
  timestamp: string;
  suggested_chips: string[];
}
