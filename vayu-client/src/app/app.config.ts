import { ApplicationConfig, provideZoneChangeDetection } from '@angular/core';
import { provideRouter, withComponentInputBinding } from '@angular/router';
import { provideHttpClient, withFetch } from '@angular/common/http';
import { routes } from './app.routes';

export const appConfig: ApplicationConfig = {
  providers: [
    // Optimizes change detection by coalescing micro-tasks
    provideZoneChangeDetection({ eventCoalescing: true }),

    // Standalone component routing
    provideRouter(routes, withComponentInputBinding()),

    // Modern HttpClient backed by browser Fetch API
    provideHttpClient(withFetch()),
  ],
};
