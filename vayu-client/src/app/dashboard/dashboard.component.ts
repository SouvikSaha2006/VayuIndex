import { Component, OnInit, inject } from '@angular/core';
import { CommonModule, DecimalPipe, DatePipe } from '@angular/common';
import { Observable, BehaviorSubject, switchMap, tap, shareReplay } from 'rxjs';
import { VayuService } from '../services/vayu.service';
import { DailyCPIIndex, FareObservation, FlightRoute } from '../models/vayu.model';

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [CommonModule, DecimalPipe, DatePipe],
  templateUrl: './dashboard.component.html',
  styleUrl: './dashboard.component.scss',
})
export class DashboardComponent implements OnInit {
  private readonly vayuService = inject(VayuService);

  // Reactive trigger subject to refresh streams dynamically
  private readonly refresh$ = new BehaviorSubject<void>(undefined);

  // Observable data streams
  routes$!: Observable<FlightRoute[]>;
  fares$!: Observable<FareObservation[]>;
  latestIndex$!: Observable<DailyCPIIndex>;
  indexHistory$!: Observable<DailyCPIIndex[]>;

  // Component state
  isIngesting = false;
  ingestionSuccessMessage: string | null = null;
  errorMessage: string | null = null;

  ngOnInit(): void {
    this.initDataStreams();
  }

  /**
   * Initializes reactive observables bound to the refresh trigger.
   */
  private initDataStreams(): void {
    this.routes$ = this.refresh$.pipe(
      switchMap(() => this.vayuService.getRoutes()),
      shareReplay(1)
    );

    this.fares$ = this.refresh$.pipe(
      switchMap(() => this.vayuService.getFares()),
      shareReplay(1)
    );

    this.latestIndex$ = this.refresh$.pipe(
      switchMap(() => this.vayuService.getLatestIndex()),
      shareReplay(1)
    );

    this.indexHistory$ = this.refresh$.pipe(
      switchMap(() => this.vayuService.getIndexHistory()),
      shareReplay(1)
    );
  }

  /**
   * Calculates the percentage deviation between the current average fare and the baseline benchmark:
   * ((current_avg - baseline) / baseline) * 100
   */
  getPercentageDeviation(route: FlightRoute): number {
    const base = Number(route.base_benchmark_fare);
    const current = Number(route.current_avg_fare ?? route.base_benchmark_fare);
    if (!base || base === 0) return 0;
    return ((current - base) / base) * 100;
  }

  /**
   * Triggers the backend simulation pipeline and re-emits on the refresh subject
   * to reload all dashboard streams without a full page reload.
   */
  triggerIngestion(): void {
    this.isIngesting = true;
    this.errorMessage = null;
    this.ingestionSuccessMessage = null;

    this.vayuService.triggerIngestion().subscribe({
      next: (res) => {
        this.isIngesting = false;
        this.ingestionSuccessMessage = `Successfully logged ${res.records_logged} fresh fare observations. Recalculated Laspeyres Index: ${res.updated_index.toFixed(2)}`;
        // Dynamically trigger reload across all subscribed streams
        this.refresh$.next();
      },
      error: (err) => {
        this.isIngesting = false;
        this.errorMessage = err.message || 'Failed to trigger simulated fare ingestion.';
      },
    });
  }

  /**
   * Returns a clean CSS class name based on the airline carrier code.
   */
  getCarrierBadgeClass(carrier: string): string {
    switch (carrier?.toUpperCase()) {
      case 'INDIGO':
        return 'carrier-indigo';
      case 'AIRINDIA':
        return 'carrier-airindia';
      case 'SPICEJET':
        return 'carrier-spicejet';
      case 'AKASA':
        return 'carrier-akasa';
      default:
        return 'carrier-default';
    }
  }
}
