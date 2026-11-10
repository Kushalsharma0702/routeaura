import { apiFetch } from './client';
import type { Itinerary } from './itineraries';

export interface Snapshot { id: string; kind: 'weather' | 'report'; day_number: number | null; source: string; payload: Record<string, unknown>; fetched_at: string; age_minutes: number; fresh: boolean }
export interface ContextStatus {
  weather_provider: string; weather_configured: boolean; needs_dates: boolean; max_age_minutes: number;
  snapshots: Snapshot[]; stale_days: number[]; notes: string[];
}
export interface Issue { type: string; day: number; activity_id: string | null; evidence: string; source: string; fetched_at: string | null; reason?: string }
export interface Change { action: 'replace' | 'move' | 'remove'; activity_id: string; reason: string; from?: string; to?: string; name?: string; day?: number; from_day?: number; to_day?: number; introduces_violations?: number }
export interface Proposal {
  id: string; itinerary_id: string; status: 'pending' | 'approved' | 'rejected' | 'superseded'; trigger: Issue; changes: Change[];
  preview: { before?: { violations: { message: string }[]; days: { day: number; stops: string[] }[] }; after?: { violations: { message: string }[]; days: { day: number; stops: string[] }[] }; alternatives?: { name: string; why: string }[] };
  base_version: number; material: boolean; applied_version: number | null; created_at: string; decided_at: string | null;
}
export interface AdaptResult { issues: Issue[]; proposals: Proposal[]; unresolved: Issue[]; stale_days: number[]; notes: string[]; latency_ms: number }
export type Report =
  | { type: 'closure'; activity_id: string }
  | { type: 'delay'; day_number: number; current_time_min: number; completed_activity_ids: string[] }
  | { type: 'spent'; spent_minor: number };

export const contextApi = {
  status: (id: string) => apiFetch<ContextStatus>(`/itineraries/${id}/context`),
  refresh: (id: string) => apiFetch<ContextStatus>(`/itineraries/${id}/context/refresh`, { method: 'POST' }),
  report: (id: string, body: Report) => apiFetch<ContextStatus>(`/itineraries/${id}/context/report`, { method: 'POST', body }),
  adapt: (id: string) => apiFetch<AdaptResult>(`/itineraries/${id}/adapt`, { method: 'POST' }),
  proposals: (id: string) => apiFetch<Proposal[]>(`/itineraries/${id}/adaptations`),
  approve: (pid: string) => apiFetch<Itinerary>(`/adaptations/${pid}/approve`, { method: 'POST' }),
  reject: (pid: string) => apiFetch<Proposal>(`/adaptations/${pid}/reject`, { method: 'POST' }),
};
