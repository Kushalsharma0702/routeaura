import { apiFetch } from './client';
import type { Itinerary } from './itineraries';

export interface Weights { distance: number; time: number; cost: number; preference: number; taxi_rupees_per_km: number }
export interface PlanStop { id: string; name: string; lat: number; lng: number; start_time: string | null; duration_min: number; locked: boolean }
export interface PlanMetrics {
  distance_m: number; travel_min: number; wait_min: number; n_activities: number; utility: number;
  violations: { type: string; day: number | null; message: string }[];
  budget: { deviation_pct: number | null; within_budget: boolean | null };
}
export interface PlanView { days: { day: number; stops: PlanStop[] }[]; metrics: PlanMetrics }
export interface Optimization {
  id: string; itinerary_id: string; status: 'optimized' | 'relaxed' | 'infeasible'; applied: boolean; base_version: number; weights: Weights;
  routing: { source: string; notes: string[]; live_traffic: boolean; fetched_at: string };
  before: PlanView; after: PlanView | null;
  delta: { distance_m: number; distance_pct: string; travel_min: number; travel_pct: string; violations: number; activities: number } | null;
  changes: string[]; dropped: { id: string; name: string; reason: string }[]; notes: string[]; solver_ms: number | null; created_at: string; applied_at: string | null;
}

export const optimizationApi = {
  preview: (id: string, body: { weights?: Partial<Weights>; improve?: boolean; time_limit_ms?: number }) =>
    apiFetch<Optimization>(`/itineraries/${id}/optimize`, { method: 'POST', body }),
  history: (id: string) => apiFetch<Optimization[]>(`/itineraries/${id}/optimizations`),
  apply: (runId: string) => apiFetch<Itinerary>(`/optimizations/${runId}/apply`, { method: 'POST' }),
};
