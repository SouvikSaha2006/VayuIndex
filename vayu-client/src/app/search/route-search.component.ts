import { Component, OnInit, inject } from '@angular/core';
import { CommonModule, DecimalPipe, DatePipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RouterModule } from '@angular/router';
import { VayuService } from '../services/vayu.service';
import { Airport } from '../models/vayu.model';

@Component({
  selector: 'app-route-search',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterModule, DecimalPipe, DatePipe],
  templateUrl: './route-search.component.html',
  styleUrl: './route-search.component.scss',
})
export class RouteSearchComponent implements OnInit {
  private readonly vayuService = inject(VayuService);

  airports: Airport[] = [
    { id: 1, iata_code: 'DEL', city_name: 'New Delhi', metro_tier: 'T1' },
    { id: 2, iata_code: 'BOM', city_name: 'Mumbai', metro_tier: 'T1' },
    { id: 3, iata_code: 'BLR', city_name: 'Bengaluru', metro_tier: 'T1' },
    { id: 4, iata_code: 'CCU', city_name: 'Kolkata', metro_tier: 'T1' },
    { id: 5, iata_code: 'HYD', city_name: 'Hyderabad', metro_tier: 'T1' },
    { id: 6, iata_code: 'MAA', city_name: 'Chennai', metro_tier: 'T1' },
    { id: 7, iata_code: 'PNQ', city_name: 'Pune', metro_tier: 'T2' },
    { id: 8, iata_code: 'IXB', city_name: 'Bagdogra', metro_tier: 'T3' },
  ];

  selectedOrigin = 'DEL';
  selectedDestination = 'BOM';
  isSearching = false;
  searchResult: any = null;
  errorMessage: string | null = null;

  ngOnInit(): void {
    this.fetchAirports();
    this.onSearch();
  }

  get t1Airports(): Airport[] {
    return this.airports.filter((a) => a.metro_tier === 'T1');
  }

  get t2Airports(): Airport[] {
    return this.airports.filter((a) => a.metro_tier === 'T2');
  }

  get t3Airports(): Airport[] {
    return this.airports.filter((a) => a.metro_tier === 'T3');
  }

  fetchAirports(): void {
    this.vayuService.getAirports().subscribe({
      next: (data) => {
        if (data && data.length > 0) {
          this.airports = data;
        }
      },
      error: (err) => console.warn('Using default airport list fallback', err),
    });
  }

  onSearch(): void {
    if (this.selectedOrigin === this.selectedDestination) {
      this.errorMessage = 'Origin and destination airports must be different.';
      return;
    }

    this.isSearching = true;
    this.errorMessage = null;

    this.vayuService.searchRoutes(this.selectedOrigin, this.selectedDestination).subscribe({
      next: (res) => {
        this.isSearching = false;
        this.searchResult = res;
      },
      error: (err) => {
        this.isSearching = false;
        this.errorMessage = err.message || 'Failed to search flight routes.';
      },
    });
  }

  swapAirports(): void {
    const temp = this.selectedOrigin;
    this.selectedOrigin = this.selectedDestination;
    this.selectedDestination = temp;
    this.onSearch();
  }

  getRouteTierBadge(): string {
    const orig = this.airports.find((a) => a.iata_code === this.selectedOrigin);
    const dest = this.airports.find((a) => a.iata_code === this.selectedDestination);
    if (!orig || !dest) return 'Domestic Indian Corridor';

    if (orig.metro_tier === 'T1' && dest.metro_tier === 'T1') {
      return 'Tier 1 Metro ➔ Metro Corridor';
    }
    if (orig.metro_tier === 'T3' || dest.metro_tier === 'T3') {
      return 'Regional ➔ UDAN Connectivity Corridor';
    }
    return 'Metro ➔ Tier 2 Commercial Feeder';
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
