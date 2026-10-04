import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { Observable, catchError, map, throwError } from 'rxjs';
import {
  Airport,
  DailyCPIIndex,
  FareObservation,
  FlightRoute,
  IngestionResponse,
  PaginatedResponse,
} from '../models/vayu.model';

@Injectable({
  providedIn: 'root',
})
export class VayuService {
  private readonly http = inject(HttpClient);
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
  getLatestIndex(): Observable<DailyCPIIndex> {
    return this.http
      .get<DailyCPIIndex>(`${this.apiUrl}/cpi-indices/latest/`)
      .pipe(catchError(this.handleError));
  }

  /**
   * Trigger the automated fare scraping ingestion pipeline and recalculate the daily index.
   * Endpoint: POST /api/fares/trigger-ingestion/
   *
   * Maps Django's backend response payload (records_ingested / updated_index_value)
   * to the requested TypeScript contract { status, records_logged, updated_index }.
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
}
