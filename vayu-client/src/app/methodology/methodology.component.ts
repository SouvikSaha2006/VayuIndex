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
    { origin: 'DEL', destination: 'BOM', route: 'Delhi to Mumbai', weight: 2.8, benchmark: '₹4,874.00', tier: 'Tier 1 Metro' },
    { origin: 'DEL', destination: 'BLR', route: 'Delhi to Bengaluru', weight: 2.4, benchmark: '₹5,860.00', tier: 'Tier 1 Metro' },
    { origin: 'BOM', destination: 'BLR', route: 'Mumbai to Bengaluru', weight: 2.2, benchmark: '₹4,316.00', tier: 'Tier 1 Metro' },
    { origin: 'DEL', destination: 'PNQ', route: 'Delhi to Pune', weight: 1.6, benchmark: '₹5,005.00', tier: 'Tier 2 Commercial Hub' },
    { origin: 'BOM', destination: 'GOI', route: 'Mumbai to Goa', weight: 1.5, benchmark: '₹3,598.00', tier: 'Tier 2 Commercial Hub' },
    { origin: 'DEL', destination: 'SXR', route: 'Delhi to Srinagar', weight: 0.9, benchmark: '₹4,015.00', tier: 'Tier 3 Regional / UDAN' },
    { origin: 'CCU', destination: 'IXB', route: 'Kolkata to Bagdogra', weight: 0.8, benchmark: '₹3,700.00', tier: 'Tier 3 Regional / UDAN' },
    { origin: 'DEL', destination: 'IXZ', route: 'Delhi to Port Blair', weight: 0.7, benchmark: '₹7,260.00', tier: 'Tier 3 Regional / UDAN' },
  ];
}
