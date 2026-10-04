import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule } from '@angular/router';

@Component({
  selector: 'app-methodology',
  standalone: true,
  imports: [CommonModule, RouterModule],
  templateUrl: './methodology.component.html',
  styleUrl: './methodology.component.scss',
})
export class MethodologyComponent {
  corridorWeights = [
    { origin: 'DEL', destination: 'BOM', route: 'Delhi to Mumbai', weight: 2.8, benchmark: '₹4,800.00', tier: 'Tier 1 Metro' },
    { origin: 'DEL', destination: 'BLR', route: 'Delhi to Bengaluru', weight: 2.4, benchmark: '₹5,400.00', tier: 'Tier 1 Metro' },
    { origin: 'BOM', destination: 'BLR', route: 'Mumbai to Bengaluru', weight: 2.1, benchmark: '₹4,200.00', tier: 'Tier 1 Metro' },
    { origin: 'DEL', destination: 'CCU', route: 'Delhi to Kolkata', weight: 1.8, benchmark: '₹4,900.00', tier: 'Tier 1 Metro' },
    { origin: 'BOM', destination: 'MAA', route: 'Mumbai to Chennai', weight: 1.5, benchmark: '₹3,900.00', tier: 'Tier 1 Metro' },
    { origin: 'BLR', destination: 'HYD', route: 'Bengaluru to Hyderabad', weight: 1.3, benchmark: '₹3,100.00', tier: 'Tier 1 Metro' },
  ];
}
