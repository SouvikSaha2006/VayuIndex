import { Routes } from '@angular/router';
import { DashboardComponent } from './dashboard/dashboard.component';
import { RouteSearchComponent } from './search/route-search.component';
import { MethodologyComponent } from './methodology/methodology.component';
import { PolicySandboxComponent } from './sandbox/policy-sandbox.component';

export const routes: Routes = [
  {
    path: '',
    redirectTo: 'dashboard',
    pathMatch: 'full',
  },
  {
    path: 'dashboard',
    component: DashboardComponent,
    title: 'VayuIndex | Live Airfare CPI Dashboard',
  },
  {
    path: 'search',
    component: RouteSearchComponent,
    title: 'VayuIndex | Domestic Corridor Price Finder',
  },
  {
    path: 'sandbox',
    component: PolicySandboxComponent,
    title: 'VayuIndex | Inflation Shock Policy Sandbox',
  },
  {
    path: 'policy-sandbox',
    redirectTo: 'sandbox',
  },
  {
    path: 'methodology',
    component: MethodologyComponent,
    title: 'VayuIndex | Laspeyres CPI Methodology & Weights',
  },
  {
    path: '**',
    redirectTo: 'dashboard',
  },
];
