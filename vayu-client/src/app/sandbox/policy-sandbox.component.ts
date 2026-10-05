import { Component, OnInit, inject } from '@angular/core';
import { CommonModule, DecimalPipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { VayuService } from '../services/vayu.service';
import {
  ImpactedRoute,
  ShockSimulationPayload,
  ShockSimulationResult,
} from '../models/vayu.model';

@Component({
  selector: 'app-policy-sandbox',
  standalone: true,
  imports: [CommonModule, FormsModule, DecimalPipe],
  templateUrl: './policy-sandbox.component.html',
  styleUrl: './policy-sandbox.component.scss',
})
export class PolicySandboxComponent implements OnInit {
  private readonly vayuService = inject(VayuService);

  // Simulation Sliders Model
  fuelShockPct: number = 12.5;
  regionalSurgePct: number = 20.0;
  capacityCutPct: number = 5.0;

  // Simulation State
  isSimulating: boolean = false;
  isDownloadingPdf: boolean = false;
  hasSimulated: boolean = false;
  errorMessage: string | null = null;
  downloadSuccessMessage: string | null = null;

  // Flash indicator for changes
  flashDiff: boolean = false;

  // Results
  simulationResult: ShockSimulationResult | null = null;

  // Quick Preset Scenarios
  presets = [
    {
      name: 'Diwali Festive Rush',
      description: 'Massive seasonal UDAN surge with moderate capacity strain',
      fuel: 5.0,
      regional: 45.0,
      capacity: 10.0,
    },
    {
      name: 'Crude Oil & ATF Spike',
      description: 'Severe international aviation turbine fuel escalation',
      fuel: 35.0,
      regional: 10.0,
      capacity: 5.0,
    },
    {
      name: 'Engine Grounding Shock',
      description: 'Fleet supply squeeze with 0.8x price elasticity pressure',
      fuel: 8.0,
      regional: 25.0,
      capacity: 25.0,
    },
    {
      name: 'Neutral Baseline',
      description: 'Current real-time market baseline (no exogenous shocks)',
      fuel: 0.0,
      regional: 0.0,
      capacity: 0.0,
    },
  ];

  ngOnInit(): void {
    // Initial run with default recommended macroeconomic scenario (12.5% fuel, 20% regional, 5% capacity)
    this.runSimulation();
  }

  applyPreset(preset: { fuel: number; regional: number; capacity: number }): void {
    this.fuelShockPct = preset.fuel;
    this.regionalSurgePct = preset.regional;
    this.capacityCutPct = preset.capacity;
    this.runSimulation();
  }

  runSimulation(): void {
    this.isSimulating = true;
    this.errorMessage = null;

    const payload: ShockSimulationPayload = {
      fuel_shock_pct: Number(this.fuelShockPct),
      regional_surge_pct: Number(this.regionalSurgePct),
      capacity_cut_pct: Number(this.capacityCutPct),
    };

    this.vayuService.simulateShock(payload).subscribe({
      next: (result: ShockSimulationResult) => {
        this.simulationResult = result;
        this.isSimulating = false;
        this.hasSimulated = true;

        // Trigger flash pulse effect on difference badge
        this.flashDiff = true;
        setTimeout(() => {
          this.flashDiff = false;
        }, 1200);
      },
      error: (err) => {
        this.errorMessage = 'Shock simulation failed: ' + (err.message || 'Server error');
        this.isSimulating = false;
      },
    });
  }

  resetToRealtime(): void {
    this.fuelShockPct = 0.0;
    this.regionalSurgePct = 0.0;
    this.capacityCutPct = 0.0;
    this.runSimulation();
  }

  downloadMoSPIReport(): void {
    this.isDownloadingPdf = true;
    this.downloadSuccessMessage = null;
    this.errorMessage = null;

    this.vayuService.downloadPolicyReport().subscribe({
      next: (blob: Blob) => {
        const url = window.URL.createObjectURL(blob);
        const anchor = document.createElement('a');
        anchor.href = url;
        anchor.download = 'VayuIndex_MoSPI_Dossier.pdf';
        document.body.appendChild(anchor);
        anchor.click();
        document.body.removeChild(anchor);
        window.URL.revokeObjectURL(url);

        this.isDownloadingPdf = false;
        this.downloadSuccessMessage = 'Official MoSPI CPI Policy Dossier downloaded successfully!';
        setTimeout(() => {
          this.downloadSuccessMessage = null;
        }, 5000);
      },
      error: (err) => {
        this.errorMessage = 'Failed to download policy PDF: ' + (err.message || 'Server error');
        this.isDownloadingPdf = false;
      },
    });
  }

  getSeverityClass(delta: number): string {
    if (delta > 8.0) return 'severity-critical';
    if (delta > 4.0) return 'severity-high';
    if (delta > 0.0) return 'severity-moderate';
    return 'severity-neutral';
  }
}
