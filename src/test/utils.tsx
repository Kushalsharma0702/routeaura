import { render } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { vi } from 'vitest';
import type { ReactElement } from 'react';

export interface Call { method: string; path: string; query: URLSearchParams; body: unknown }
type Handler = ((call: Call) => unknown) | Response | Record<string, unknown> | unknown[];

export const json = (status: number, body?: unknown) =>
  new Response(body === undefined ? null : JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } });
export const apiError = (status: number, code: string, message: string) => json(status, { error: { code, message } });

/**
 * Routes "METHOD /path" (without /api/v1) to handlers. Unmatched requests fail the test loudly
 * rather than silently returning data. Returns the recorded calls.
 */
export function mockApi(routes: Record<string, Handler>) {
  const calls: Call[] = [];
  vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => {
    const u = new URL(url, 'http://localhost');
    const call: Call = { method: (init?.method ?? 'GET').toUpperCase(), path: u.pathname.replace('/api/v1', ''), query: u.searchParams, body: init?.body ? JSON.parse(init.body as string) : undefined };
    calls.push(call);
    const handler = routes[`${call.method} ${call.path}`];
    if (!handler) throw new Error(`Unmocked request: ${call.method} ${call.path}`);
    const res = typeof handler === 'function' ? (handler as (c: Call) => unknown)(call) : handler; // plain values are bodies
    return res instanceof Response ? res.clone() : json(200, res);
  }));
  return calls;
}

export function renderRoute(ui: ReactElement, { path = '/', route = '/' }: { path?: string; route?: string } = {}) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[route]}><Routes><Route path={path} element={ui} /></Routes></MemoryRouter>
    </QueryClientProvider>,
  );
}

const now = '2026-01-01T00:00:00Z';
export const makeDest = (o: Record<string, unknown> = {}) => ({
  id: 'd1', slug: 'jaipur', name: 'Jaipur', country: 'India', region: 'Rajasthan', description: 'The Pink City',
  latitude: 26.9124, longitude: 75.7873, estimated_cost_per_day_minor: 320000, currency: 'INR',
  recommended_duration_days: 4, best_season_start_month: 10, best_season_end_month: 3, climate: 'arid',
  climate_notes: null, accessibility_notes: null, images: [], is_published: true, source: 'seed',
  categories: [{ id: 'c1', slug: 'history-heritage', name: 'History & Heritage' }], attraction_count: 2,
  distance_m: null, created_at: now, updated_at: now, deleted_at: null, ...o,
});
export const makeAttraction = (o: Record<string, unknown> = {}) => ({
  id: 'a1', destination_id: 'd1', slug: 'hawa-mahal', name: 'Hawa Mahal', description: '', category: { id: 'c1', slug: 'history-heritage', name: 'History & Heritage' },
  latitude: 26.9239, longitude: 75.8267, estimated_cost_minor: null, currency: 'INR', typical_duration_minutes: 60,
  opening_hours: null, opening_hours_source: null, is_outdoor: false, accessibility_notes: null, images: [],
  is_published: true, source: 'seed', distance_m: null, ...o,
});
export const page = <T,>(items: T[], total = items.length, p = 1, size = 9) => ({ items, total, page: p, page_size: size });
export const CATS = [{ id: 'c1', slug: 'history-heritage', name: 'History & Heritage' }, { id: 'c2', slug: 'beach', name: 'Beach' }];

export const makeRecItem = (o: Record<string, unknown> = {}) => ({
  recommendation_item_id: 'ri1', kind: 'destination', rank: 1, original_rank: 1, score: 0.82, confidence: 0.8,
  destination: makeDest(), attraction: null,
  components: [
    { feature: 'interest', label: 'Interests', value: 0.9, weight: 0.5, contribution: 0.45, status: 'matched', detail: 'Matches your interest in history (History & Heritage).' },
    { feature: 'budget', label: 'Budget', value: 1, weight: 0.3, contribution: 0.3, status: 'matched', detail: 'Estimated ₹3,200/day is within your ₹4,000/day budget.' },
    { feature: 'season', label: 'Travel season', value: null, weight: 0.2, contribution: 0, status: 'unknown', detail: 'No best-season information on record, so season fit could not be assessed.' },
    { feature: 'climate', label: 'Climate', value: null, weight: 0, contribution: 0, status: 'not_applicable', detail: "Not used: you didn't set this preference." },
  ],
  reasons: ['Matches your interest in history (History & Heritage).', 'Estimated ₹3,200/day is within your ₹4,000/day budget.'],
  cautions: ['Winter is outside its best season (Jun – Sep).'],
  missing: ['No best-season information on record, so season fit could not be assessed.'],
  saved: false, liked: false, disliked: false, feedback: null, ...o,
});
export const makeRecResponse = (items = [makeRecItem()], o: Record<string, unknown> = {}) => ({
  run_id: 'run1', kind: 'destination', strategy: 'weighted', model_version: 'content-v1', diversified: true, diversity_lambda: 0.7,
  total_candidates: items.length, page: 1, page_size: 6, items, applied_preferences: {}, effective_weights: {}, notes: [],
  disclaimer: 'Scores rank places against your stated preferences and the catalogue data. They are not probabilities of satisfaction.', ...o,
});
export const PREFS = {
  budget_per_day_minor: 400000, trip_duration_days: 4, interests: ['history', 'food'], preferred_climate: 'arid',
  preferred_season: null, group_size: null, travel_style: 'comfort', accommodation_preference: null, language: 'en',
};
export const STATE0 = { saved: false, liked: false, disliked: false, dismissed: false };

export const makeActivity = (o: Record<string, unknown> = {}) => ({
  id: 'act1', attraction: { id: 'a1', name: 'Hawa Mahal', category: 'History & Heritage', latitude: 26.92, longitude: 75.82, is_outdoor: false },
  day_number: 1, position: 1, start_min: 540, end_min: 600, start_time: '09:00', end_time: '10:00', duration_min: 60, travel_min: 12, travel_m: 4200,
  travel_source: 'estimate', wait_min: 0, cost_minor: null, cost_total_minor: null, hours_status: 'unknown', source: 'generated', score: 0.8,
  explanation: { reasons: ['Matches your interest in history (History & Heritage).'], cautions: [], missing: [] }, notes: null, warnings: [], ...o,
});
export const makeItinerary = (o: Record<string, unknown> = {}) => ({
  id: 'it1', title: '2-day trip to Jaipur', status: 'draft', destination: { id: 'd1', slug: 'jaipur', name: 'Jaipur', latitude: 26.9, longitude: 75.78 },
  start_date: null, days: 2, traveler_count: 2, budget_total_minor: 2000000, currency: 'INR', interests: ['history'], travel_style: null,
  accommodation_preference: null, start_location: null, generation_source: 'deterministic_fallback',
  generation_info: { notes: ['This itinerary was generated by the app\'s deterministic planner (no AI model was used).'],
    steps: [{ step: 'validate', status: 'ok', ms: 1.2, detail: '2 days' }, { step: 'deterministic_plan', status: 'ok', ms: 3.4, detail: 'nearest-neighbour' }],
    llm: { provider: 'none', model: 'none' }, travel_times: 'estimates (great-circle x 1.3 / 30 km/h), not live routing' },
  current_version: 1,
  day_plans: [
    { day_number: 1, date: null, lunch_start_min: 780, ends_at: '15:00', activities: [makeActivity(), makeActivity({ id: 'act2', position: 2, start_min: 660, start_time: '11:00', end_min: 780, end_time: '13:00', duration_min: 120,
      attraction: { id: 'a2', name: 'Amber Fort', category: 'History & Heritage', latitude: 26.98, longitude: 75.85, is_outdoor: true }, cost_minor: 20000, cost_total_minor: 40000 })] },
    { day_number: 2, date: null, lunch_start_min: null, ends_at: null, activities: [] },
  ],
  budget: { activities_minor: 40000, living_estimate_minor: 1280000, total_estimate_minor: 1320000, budget_minor: 2000000, unknown_cost_items: 1, currency: 'INR',
    note: 'Totals include only known costs; living cost is the destination\'s per-day estimate.', deviation_pct: -34, within_budget: true },
  violations: [], created_at: '2026-11-11T10:00:00Z', updated_at: '2026-11-11T10:00:00Z', ...o,
});
export const VERSIONS = [{ version: 2, summary: 'Removed Amber Fort', created_at: '2026-11-11T10:05:00Z' }, { version: 1, summary: 'Generated', created_at: '2026-11-11T10:00:00Z' }];

export const makeOptimization = (o: Record<string, unknown> = {}) => ({
  id: 'op1', itinerary_id: 'it1', status: 'optimized', applied: false, base_version: 1,
  weights: { distance: 1, time: 1, cost: 0.5, preference: 1, taxi_rupees_per_km: 12 },
  routing: { source: 'estimate', notes: ['great-circle x 1.3 at 30 km/h; not road routing and no traffic'], live_traffic: false, fetched_at: '2026-11-11T10:00:00Z' },
  before: { days: [{ day: 1, stops: [{ id: 'act1', name: 'Hawa Mahal', lat: 26.92, lng: 75.82, start_time: null, duration_min: 60, locked: false }, { id: 'act2', name: 'Amber Fort', lat: 26.98, lng: 75.85, start_time: null, duration_min: 120, locked: false }] }],
    metrics: { distance_m: 20000, travel_min: 40, wait_min: 0, n_activities: 2, utility: 1, violations: [{ type: 'day_overrun', day: 1, message: 'Day 1 ends at 18:30, after the 18:00 day end' }], budget: { deviation_pct: -20, within_budget: true } } },
  after: { days: [{ day: 1, stops: [{ id: 'act2', name: 'Amber Fort', lat: 26.98, lng: 75.85, start_time: null, duration_min: 120, locked: false }, { id: 'act1', name: 'Hawa Mahal', lat: 26.92, lng: 75.82, start_time: null, duration_min: 60, locked: false }] }],
    metrics: { distance_m: 12000, travel_min: 24, wait_min: 0, n_activities: 2, utility: 1, violations: [], budget: { deviation_pct: -20, within_budget: true } } },
  delta: { distance_m: -8000, distance_pct: '-40%', travel_min: -16, travel_pct: '-40%', violations: -1, activities: 0 },
  changes: ['Travel distance 20.0 km → 12.0 km (-40%).', 'Day 1 order changed: Hawa Mahal → Amber Fort ⇒ Amber Fort → Hawa Mahal.'],
  dropped: [], notes: [], solver_ms: 12.5, created_at: '2026-11-11T10:00:00Z', applied_at: null, ...o,
});
export const makeContextStatus = (o: Record<string, unknown> = {}) => ({
  weather_provider: 'none', weather_configured: false, needs_dates: false, max_age_minutes: 180, snapshots: [], stale_days: [],
  notes: ['No weather provider is configured, so no weather is shown or used. You can still report closures, delays and spending yourself.'], ...o,
});
export const makeProposal = (o: Record<string, unknown> = {}) => ({
  id: 'pr1', itinerary_id: 'it1', status: 'pending',
  trigger: { type: 'rain', day: 1, activity_id: 'act2', evidence: '85% chance of rain, 12.0 mm expected (open-meteo, fetched 10:00 UTC)', source: 'open-meteo', fetched_at: '2026-11-11T10:00:00Z' },
  changes: [{ action: 'replace', activity_id: 'act2', day: 1, from: 'Amber Fort', to: 'City Palace', to_attraction_id: 'a9', reason: 'rain: 85% chance. Suggested City Palace: same category (history), 9.0 km from Amber Fort, indoor.' }],
  preview: { after: { violations: [], days: [] }, alternatives: [{ name: 'City Palace', why: 'indoor' }] }, base_version: 1, material: true, applied_version: null,
  created_at: '2026-11-11T10:00:00Z', decided_at: null, ...o,
});
