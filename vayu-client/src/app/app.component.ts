import { Component, inject, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterOutlet } from '@angular/router';
import { Observable } from 'rxjs';
import { VayuService } from './services/vayu.service';
import { DailyCPIIndex, FareObservation, FlightRoute } from './models/vayu.model';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [CommonModule, RouterOutlet],
  templateUrl: './app.component.html',
  styleUrl: './app.component.scss',
})
export class AppComponent implements OnInit {
  private readonly vayuService = inject(VayuService);

  title = 'VayuIndex Client';
  routes$!: Observable<FlightRoute[]>;
  fares$!: Observable<FareObservation[]>;
  cpiHistory$!: Observable<DailyCPIIndex[]>;
  latestIndex$!: Observable<DailyCPIIndex>;

  isIngesting = false;
  ingestionResult: { status: string; records_logged: number; updated_index: number } | null = null;
  errorMessage = '';

  ngOnInit(): void {
    this.loadData();
  }

  loadData(): void {
    this.routes$ = this.vayuService.getRoutes();
    this.fares$ = this.vayuService.getFares();
    this.cpiHistory$ = this.vayuService.getIndexHistory();
    this.latestIndex$ = this.vayuService.getLatestIndex();
  }

  triggerIngest(): void {
    this.isIngesting = true;
    this.errorMessage = '';
    this.vayuService.triggerIngestion().subscribe({
      next: (res) => {
        this.ingestionResult = res;
        this.isIngesting = false;
        this.loadData();
      },
      error: (err) => {
        this.errorMessage = err.message || 'Ingestion failed';
        this.isIngesting = false;
      },
    });
  }
}
