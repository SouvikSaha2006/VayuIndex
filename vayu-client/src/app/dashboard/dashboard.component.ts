import { Component, OnInit, OnDestroy, inject } from '@angular/core';
import { CommonModule, DecimalPipe, DatePipe } from '@angular/common';
import { Observable, BehaviorSubject, Subscription, switchMap, shareReplay } from 'rxjs';
import { VayuService } from '../services/vayu.service';
import { DailyCPIIndex, FareObservation, FlightRoute } from '../models/vayu.model';

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [CommonModule, DecimalPipe, DatePipe],
  templateUrl: './dashboard.component.html',
  styleUrl: './dashboard.component.scss',
})
export class DashboardComponent implements OnInit, OnDestroy {
  private readonly vayuService = inject(VayuService);

  private readonly refresh$ = new BehaviorSubject<void>(undefined);
  private sseSubscription?: Subscription;

  // Real-time SSE stream storage
  liveStreamFares: any[] = [];
  liveStreamActive = false;

  routes$!: Observable<FlightRoute[]>;
  fares$!: Observable<FareObservation[]>;
  latestIndex$!: Observable<DailyCPIIndex | null>;
  indexHistory$!: Observable<DailyCPIIndex[]>;

  isIngesting = false;
  ingestionSuccessMessage: string | null = null;
  errorMessage: string | null = null;

  ngOnInit(): void {
    this.initDataStreams();
    this.startLiveStream();
  }

  ngOnDestroy(): void {
    this.sseSubscription?.unsubscribe();
  }

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

  private startLiveStream(): void {
    this.sseSubscription = this.vayuService.connectToLiveStream().subscribe({
      next: (data) => {
        if (data && data.fare) {
          this.liveStreamActive = true;
          this.liveStreamFares.unshift(data.fare);
          if (this.liveStreamFares.length > 25) {
            this.liveStreamFares.pop();
          }
          this.refresh$.next();
        }
      },
      error: (err) => {
        console.warn('Live SSE stream error:', err);
        this.liveStreamActive = false;
      },
    });
  }

  getCombinedFares(fares: FareObservation[] | null): any[] {
    const historical = fares || [];
    const combined = [...this.liveStreamFares, ...historical];
    return combined.slice(0, 40);
  }

  getPercentageDeviation(route: FlightRoute): number {
    const base = Number(route.base_benchmark_fare);
    const current = Number(route.current_avg_fare ?? route.base_benchmark_fare);
    if (!base || base === 0) return 0;
    return ((current - base) / base) * 100;
  }

  triggerIngestion(): void {
    this.isIngesting = true;
    this.errorMessage = null;
    this.ingestionSuccessMessage = null;

    this.vayuService.triggerIngestion().subscribe({
      next: (res) => {
        this.isIngesting = false;
        this.ingestionSuccessMessage = `Successfully logged ${res.records_logged} fresh fare observations. Recalculated Laspeyres Index: ${res.updated_index.toFixed(2)}`;
        this.refresh$.next();
      },
      error: (err) => {
        this.isIngesting = false;
        this.errorMessage = err.message || 'Failed to trigger simulated fare ingestion.';
      },
    });
  }

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
