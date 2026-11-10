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
