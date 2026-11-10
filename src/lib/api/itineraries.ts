import { apiFetch } from './client';
import type { Page } from './users';

export interface Activity {
  id: string;
  attraction: { id: string; name: string; category: string; latitude: number; longitude: number; is_outdoor: boolean };
  day_number: number; position: number; start_min: number; end_min: number; start_time: string; end_time: string;
  duration_min: number; travel_min: number; travel_m: number; travel_source: string; wait_min: number;
  /** per person; null = unknown (never assumed to be free) */
  cost_minor: number | null; cost_total_minor: number | null;
  hours_status: 'verified_open' | 'verified_closed' | 'unknown'; source: string; score: number | null;
  explanation: { reasons?: string[]; cautions?: string[]; missing?: string[]; llm?: { theme?: string; rationale?: string } };
  notes: string | null; warnings: string[];
}
export interface DayPlan { day_number: number; date: string | null; activities: Activity[]; lunch_start_min: number | null; ends_at: string | null }
export interface Violation { type: string; day: number | null; activity_id: string | null; message: string }
export interface Budget {
  activities_minor: number; living_estimate_minor: number | null; total_estimate_minor: number; budget_minor: number | null;
  unknown_cost_items: number; currency: string; note: string; deviation_pct: number | null; within_budget: boolean | null;
}
export interface Itinerary {
  id: string; title: string; status: 'draft' | 'saved';
  destination: { id: string; slug: string; name: string; latitude: number; longitude: number };
  start_date: string | null; days: number; traveler_count: number; budget_total_minor: number | null; currency: string;
  interests: string[]; travel_style: string | null; accommodation_preference: string | null;
  start_location: { name: string; lat: number; lng: number } | null;
  generation_source: 'llm' | 'deterministic_fallback' | 'manual';
  generation_info: { notes?: string[]; steps?: { step: string; status: string; ms: number; detail: string }[]; dropped?: { attraction: string; reason: string }[];
    llm?: { provider: string; model: string; error?: string }; travel_times?: string };
  current_version: number; day_plans: DayPlan[]; budget: Budget; violations: Violation[]; created_at: string; updated_at: string;
}
export interface ItinerarySummary {
  id: string; title: string; status: string; destination_name: string; start_date: string | null; days: number;
  traveler_count: number; activity_count: number; generation_source: string; current_version: number; updated_at: string;
}
export interface TripRequest {
  destination_id: string; days?: number; start_date?: string; end_date?: string; travelers: number; budget_total_minor?: number;
  interests?: string[]; travel_style?: string; accommodation_preference?: string; title?: string; prompt?: string; use_llm?: boolean;
  start_location?: { name: string; lat: number; lng: number };
}
export interface Version { version: number; summary: string; created_at: string }

const base = (id: string) => `/itineraries/${id}`;
export const itinerariesApi = {
  generate: (req: TripRequest) => apiFetch<Itinerary>('/itineraries/generate', { method: 'POST', body: req }),
  list: (p: { page?: number; page_size?: number }) => apiFetch<Page<ItinerarySummary>>('/itineraries', { params: { ...p } }),
  get: (id: string) => apiFetch<Itinerary>(base(id)),
  update: (id: string, body: { title?: string; status?: 'draft' | 'saved'; budget_total_minor?: number; traveler_count?: number; start_date?: string | null }) =>
    apiFetch<Itinerary>(base(id), { method: 'PATCH', body }),
  remove: (id: string) => apiFetch<void>(base(id), { method: 'DELETE' }),
  regenerate: (id: string, body: { interests?: string[]; travel_style?: string; budget_total_minor?: number; use_llm?: boolean }) =>
    apiFetch<Itinerary>(`${base(id)}/regenerate`, { method: 'POST', body }),
  addActivity: (id: string, body: { attraction_id: string; day_number: number; position?: number; duration_min?: number }) =>
    apiFetch<Itinerary>(`${base(id)}/activities`, { method: 'POST', body }),
  updateActivity: (id: string, aid: string, body: { duration_min?: number; notes?: string | null }) =>
    apiFetch<Itinerary>(`${base(id)}/activities/${aid}`, { method: 'PATCH', body }),
  removeActivity: (id: string, aid: string) => apiFetch<Itinerary>(`${base(id)}/activities/${aid}`, { method: 'DELETE' }),
  reorder: (id: string, days: { day_number: number; activity_ids: string[] }[]) =>
    apiFetch<Itinerary>(`${base(id)}/reorder`, { method: 'POST', body: { days } }),
  versions: (id: string) => apiFetch<Version[]>(`${base(id)}/versions`),
  restore: (id: string, version: number) => apiFetch<Itinerary>(`${base(id)}/versions/${version}/restore`, { method: 'POST' }),
};
