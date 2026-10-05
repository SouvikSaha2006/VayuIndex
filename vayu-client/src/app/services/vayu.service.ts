import { Injectable, NgZone, inject } from '@angular/core';
import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { Observable, catchError, map, of, throwError } from 'rxjs';
import {
  Airport,
  DailyCPIIndex,
  FareObservation,
  FlightRoute,
  IngestionResponse,
  PaginatedResponse,
  ShockSimulationPayload,
  ShockSimulationResult,
  ChatbotResponse,
} from '../models/vayu.model';

@Injectable({
  providedIn: 'root',
})
export class VayuService {
  private readonly http = inject(HttpClient);
  private readonly zone = inject(NgZone);
  private readonly apiUrl = '/api';

  /**
   * Helper utility to normalize responses whether DRF pagination is enabled or disabled.
   */
  private extractResults<T>(response: PaginatedResponse<T> | T[]): T[] {
    if (Array.isArray(response)) {
      return response;
    }
    return response?.results ?? [];
  }

  /**
   * Centralized HTTP error handler for reactive pipeline safety.
   */
  private handleError(error: HttpErrorResponse): Observable<never> {
    const errorMsg =
      error.error instanceof ErrorEvent
        ? `Client Error: ${error.error.message}`
        : `Backend Server Error [${error.status}]: ${JSON.stringify(error.error || error.message)}`;
    console.error('[VayuService]', errorMsg);
    return throwError(() => new Error(errorMsg));
  }

  /**
   * Fetch all domestic airports.
   */
  getAirports(): Observable<Airport[]> {
    return this.http
      .get<PaginatedResponse<Airport> | Airport[]>(`${this.apiUrl}/airports/`)
      .pipe(
        map((response) => this.extractResults(response)),
        catchError(this.handleError)
      );
  }

  /**
   * Fetch all domestic flight route corridors.
   * Endpoint: GET /api/routes/
   */
  getRoutes(): Observable<FlightRoute[]> {
    return this.http
      .get<PaginatedResponse<FlightRoute> | FlightRoute[]>(`${this.apiUrl}/routes/`)
      .pipe(
        map((response) => this.extractResults(response)),
        catchError(this.handleError)
      );
  }

  /**
   * Fetch observed airfares across carriers and horizons.
   * Endpoint: GET /api/fares/
   */
  getFares(): Observable<FareObservation[]> {
    return this.http
      .get<PaginatedResponse<FareObservation> | FareObservation[]>(`${this.apiUrl}/fares/`)
      .pipe(
        map((response) => this.extractResults(response)),
        catchError(this.handleError)
      );
  }

  /**
   * Fetch historical daily Laspeyres CPI index time-series.
   * Endpoint: GET /api/cpi-indices/
   */
  getIndexHistory(): Observable<DailyCPIIndex[]> {
    return this.http
      .get<PaginatedResponse<DailyCPIIndex> | DailyCPIIndex[]>(`${this.apiUrl}/cpi-indices/`)
      .pipe(
        map((response) => this.extractResults(response)),
        catchError(this.handleError)
      );
  }

  /**
   * Fetch the most recent daily Laspeyres CPI index calculation.
   * Endpoint: GET /api/cpi-indices/latest/
   */
  getLatestIndex(): Observable<DailyCPIIndex | null> {
    return this.http
      .get<DailyCPIIndex>(`${this.apiUrl}/cpi-indices/latest/`)
      .pipe(
        catchError((error: HttpErrorResponse) => {
          if (error.status === 404) {
            return of(null);
          }
          return this.handleError(error);
        })
      );
  }

  /**
   * Source-destination flight route search.
   * Endpoint: GET /api/routes/search/?origin=DEL&destination=BOM
   */
  searchRoutes(origin: string, destination: string): Observable<any> {
    return this.http
      .get<any>(`${this.apiUrl}/routes/search/?origin=${encodeURIComponent(origin)}&destination=${encodeURIComponent(destination)}`)
      .pipe(catchError(this.handleError));
  }

  /**
   * Fetch macro statistics summary.
   * Endpoint: GET /api/index/summary/
   */
  getIndexSummary(): Observable<any> {
    return this.http
      .get<any>(`${this.apiUrl}/index/summary/`)
      .pipe(catchError(this.handleError));
  }

  /**
   * Trigger the automated fare scraping ingestion pipeline and recalculate the daily index.
   * Endpoint: POST /api/fares/trigger-ingestion/
   */
  triggerIngestion(): Observable<{ status: string; records_logged: number; updated_index: number }> {
    return this.http
      .post<any>(`${this.apiUrl}/fares/trigger-ingestion/`, {})
      .pipe(
        map((res) => ({
          status: res.status ?? 'success',
          records_logged: Number(res.records_logged ?? res.records_ingested ?? res.record_count ?? 0),
          updated_index: Number(res.updated_index ?? res.updated_index_value ?? res.index_value ?? 0),
        })),
        catchError(this.handleError)
      );
  }

  /**
   * Connects to live real-time Server-Sent Events stream (/api/fares/live-stream/).
   */
  connectToLiveStream(): Observable<{ fare: any; index: any }> {
    return new Observable((subscriber) => {
      const eventSource = new EventSource(`${this.apiUrl}/fares/live-stream/`);

      eventSource.onmessage = (event) => {
        this.zone.run(() => {
          try {
            const data = JSON.parse(event.data);
            subscriber.next(data);
          } catch (err) {
            console.error('Error parsing SSE event:', err);
          }
        });
      };

      eventSource.onerror = (err) => {
        this.zone.run(() => {
          console.warn('SSE EventSource error connection lost:', err);
        });
      };

      return () => {
        eventSource.close();
      };
    });
  }

  /**
   * Run Monte-Carlo Macroeconomic Inflation Shock Simulation.
   * Endpoint: POST /api/index/simulate-shock/
   */
  simulateShock(payload: ShockSimulationPayload): Observable<ShockSimulationResult> {
    return this.http
      .post<ShockSimulationResult>(`${this.apiUrl}/index/simulate-shock/`, payload)
      .pipe(catchError(this.handleError));
  }

  /**
   * Fetch generated MoSPI CPI Policy Dossier PDF as a binary Blob.
   * Endpoint: GET /api/index/export-policy-report/
   */
  downloadPolicyReport(): Observable<Blob> {
    return this.http
      .get(`${this.apiUrl}/index/export-policy-report/`, {
        responseType: 'blob',
      })
      .pipe(catchError(this.handleError));
  }

  /**
   * Send user message to VayuMitra conversational AI assistant.
   * Endpoint: POST /api/chatbot/message/
   */
  sendChatMessage(message: string): Observable<ChatbotResponse> {
    return this.http
      .post<ChatbotResponse>(`${this.apiUrl}/chatbot/message/`, { message })
      .pipe(catchError(this.handleError));
  }
}
