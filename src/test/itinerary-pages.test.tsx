import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { toast } from 'sonner';
import { Route, Routes } from 'react-router-dom';
import Planner from '@/pages/client/Planner';
import Itineraries from '@/pages/client/Itineraries';
import ItineraryDetail from '@/pages/client/ItineraryDetail';
import { PREFS, VERSIONS, apiError, makeAttraction, makeDest, makeItinerary, mockApi, page, renderRoute } from './utils';

vi.mock('sonner', () => ({ toast: Object.assign(vi.fn(), { success: vi.fn(), error: vi.fn() }) }));
beforeEach(() => vi.clearAllMocks());
afterEach(() => vi.unstubAllGlobals());

const planner = () => renderRoute(
  <Routes><Route path="/dashboard/planner" element={<Planner />} /><Route path="/dashboard/itineraries/:id" element={<div>ITINERARY PAGE</div>} /></Routes>,
  { path: '/*', route: '/dashboard/planner' });
const plannerApi = (extra: Record<string, unknown> = {}) => ({ 'GET /destinations': page([makeDest()]), 'GET /users/me/preferences': PREFS, ...extra });

describe('Planner form', () => {
  it('validates before calling the API', async () => {
    const user = userEvent.setup();
    const calls = mockApi(plannerApi());
    planner();
    await screen.findByRole('form', { name: 'Trip planner' });
    await waitFor(() => expect(screen.getByLabelText('Interests')).toHaveValue('history, food'));   // saved-preference prefill has landed
    await user.clear(screen.getByLabelText('Days'));
    await user.click(screen.getByRole('button', { name: /Create itinerary/ }));
    await waitFor(() => expect(screen.getAllByRole('alert').map(a => a.textContent)).toContain('Choose a destination'));
    await user.click(screen.getByRole('combobox', { name: 'Destination' }));
    await user.click(await screen.findByRole('option', { name: /Jaipur/ }));
    await user.click(screen.getByRole('button', { name: /Create itinerary/ }));
    await waitFor(() => expect(screen.getAllByRole('alert').map(a => a.textContent)).toContain('Enter the number of days or both dates'));
    expect(calls.some(c => c.method === 'POST')).toBe(false);
    await user.clear(screen.getByLabelText('Travelers'));
    await user.type(screen.getByLabelText('Days'), '20');
    await user.click(screen.getByRole('button', { name: /Create itinerary/ }));
    expect(await screen.findByText('Travelers is required')).toBeInTheDocument();
    expect(screen.getByText(/Days must be between 1 and 14/)).toBeInTheDocument();
  });

  it('pre-fills from saved preferences, posts the trip request and opens the new itinerary', async () => {
    const user = userEvent.setup();
    const calls = mockApi(plannerApi({ 'POST /itineraries/generate': () => new Response(JSON.stringify(makeItinerary()), { status: 201, headers: { 'content-type': 'application/json' } }) }));
    planner();
    await waitFor(() => expect(screen.getByLabelText('Interests')).toHaveValue('history, food'));
    await user.click(screen.getByRole('combobox', { name: 'Destination' }));
    await user.click(await screen.findByRole('option', { name: /Jaipur/ }));
    await user.clear(screen.getByLabelText('Days')); await user.type(screen.getByLabelText('Days'), '2');
    await user.clear(screen.getByLabelText('Travelers')); await user.type(screen.getByLabelText('Travelers'), '2');
    await user.type(screen.getByLabelText('Total budget (₹, optional)'), '20000');
    await user.click(screen.getByRole('button', { name: /Create itinerary/ }));
    expect(await screen.findByText('ITINERARY PAGE')).toBeInTheDocument();
    const body = calls.find(c => c.path === '/itineraries/generate')!.body as Record<string, unknown>;
    expect(body).toMatchObject({ destination_id: 'd1', days: 2, travelers: 2, budget_total_minor: 2000000, interests: ['history', 'food'] });
    expect(body.prompt).toBeUndefined();
    expect(toast.success).toHaveBeenCalledWith('Itinerary created');
  });

  it('shows an in-progress status while generating and surfaces server errors', async () => {
    const user = userEvent.setup();
    let release!: (r: Response) => void;
    mockApi(plannerApi({ 'POST /itineraries/generate': () => new Promise<Response>(res => { release = res; }) as unknown as Response }));
    // the harness expects sync handlers: emulate a slow server with a pending fetch instead
    vi.unstubAllGlobals();
    const real = vi.fn(async (url: string, init?: RequestInit) => {
      const path = new URL(url, 'http://x').pathname.replace('/api/v1', '');
      if (init?.method === 'POST') return new Promise<Response>(res => { release = res; });
      return new Response(JSON.stringify(path === '/destinations' ? page([makeDest()]) : PREFS), { status: 200, headers: { 'content-type': 'application/json' } });
    });
    vi.stubGlobal('fetch', real);
    planner();
    await user.click(await screen.findByRole('combobox', { name: 'Destination' }));
    await user.click(await screen.findByRole('option', { name: /Jaipur/ }));
    await user.click(screen.getByRole('button', { name: /Create itinerary/ }));
    expect(await screen.findByRole('status')).toHaveTextContent(/Ranking attractions, planning days/);
    expect(screen.getByRole('button', { name: /Planning/ })).toBeDisabled();
    release(new Response(JSON.stringify({ error: { code: 'no_attractions', message: 'This destination has no published attractions to plan with' } }), { status: 422, headers: { 'content-type': 'application/json' } }));
    await waitFor(() => expect(toast.error).toHaveBeenCalledWith('This destination has no published attractions to plan with'));
    expect(screen.getByRole('button', { name: /Create itinerary/ })).toBeEnabled();
  });
});

describe('My trips list', () => {
  const summary = { id: 'it1', title: 'Jaipur getaway', status: 'saved', destination_name: 'Jaipur', start_date: null, days: 2, traveler_count: 2, activity_count: 4, generation_source: 'llm', current_version: 3, updated_at: '2026-11-11T10:00:00Z' };
  it('lists trips, shows empty and error states, and deletes after confirmation', async () => {
    const user = userEvent.setup();
    const calls = mockApi({ 'GET /itineraries': page([summary]), 'DELETE /itineraries/it1': () => new Response(null, { status: 204 }) });
    renderRoute(<Itineraries />);
    expect(await screen.findByRole('link', { name: 'Jaipur getaway' })).toHaveAttribute('href', '/dashboard/itineraries/it1');
    expect(screen.getByText('Saved')).toBeInTheDocument(); expect(screen.getByText('AI-assisted')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Delete Jaipur getaway' }));
    expect(calls.some(c => c.method === 'DELETE')).toBe(false);
    await user.click(within(screen.getByRole('alertdialog')).getByRole('button', { name: 'Delete' }));
    await waitFor(() => expect(calls.some(c => c.method === 'DELETE' && c.path === '/itineraries/it1')).toBe(true));
    vi.unstubAllGlobals();
    mockApi({ 'GET /itineraries': page([]) });
    renderRoute(<Itineraries />);
    expect(await screen.findByText('No trips yet')).toBeInTheDocument();
    vi.unstubAllGlobals();
    mockApi({ 'GET /itineraries': () => apiError(500, 'internal_error', 'x') });
    renderRoute(<Itineraries />);
    expect((await screen.findAllByRole('alert')).length).toBeGreaterThan(0);
  });
});

describe('Itinerary detail', () => {
  const view = () => renderRoute(<ItineraryDetail />, { path: '/dashboard/itineraries/:id', route: '/dashboard/itineraries/it1' });
  const api = (extra: Record<string, unknown> = {}) => ({ 'GET /itineraries/it1': makeItinerary(), 'GET /itineraries/it1/versions': VERSIONS, ...extra });

  it('shows the plan honestly: fallback label, estimates, unknown fees, unverified hours, budget and steps', async () => {
    mockApi(api());
    view();
    expect(await screen.findByRole('heading', { name: 'Hawa Mahal' })).toBeInTheDocument();
    expect(screen.getByText(/deterministic planner \(no AI model was used\)/)).toBeInTheDocument();
    expect(screen.getAllByText(/~12 min \/ 4\.2 km from previous stop \(estimate\)/)).toHaveLength(2);
    expect(screen.getByText('Entry fee unknown (not included in totals)')).toBeInTheDocument();
    expect(screen.getAllByText('Opening hours not verified').length).toBe(2);
    const budget = screen.getByRole('region', { name: 'Budget breakdown' });
    expect(within(budget).getByText('₹13,200')).toBeInTheDocument();
    expect(within(budget).getByText(/1 activity has no known entry fee/)).toBeInTheDocument();
    expect(screen.getByText(/validate · 1\.2 ms/)).toBeInTheDocument();
    expect(screen.getByText(/not live routing/)).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: 'Day 2' })).toBeInTheDocument();
  });

  it('labels AI-assisted plans differently and lists violations', async () => {
    mockApi(api({ 'GET /itineraries/it1': makeItinerary({ generation_source: 'llm', generation_info: { notes: [], steps: [], llm: { provider: 'anthropic', model: 'claude-x' } },
      violations: [{ type: 'budget', day: null, activity_id: null, message: 'Estimated total exceeds the budget by 12%' }] }) }));
    view();
    expect(await screen.findByText(/suggested by an AI model \(claude-x\)/)).toBeInTheDocument();
    expect(screen.getByRole('alert')).toHaveTextContent('Estimated total exceeds the budget by 12%');
  });

  it('removes, reorders and edits activities through the API', async () => {
    const user = userEvent.setup();
    const calls = mockApi(api({ 'DELETE /itineraries/it1/activities/act1': makeItinerary(), 'POST /itineraries/it1/reorder': makeItinerary(), 'PATCH /itineraries/it1/activities/act1': makeItinerary() }));
    view();
    await screen.findByRole('heading', { name: 'Hawa Mahal' });
    await user.click(screen.getByRole('button', { name: 'Move Hawa Mahal later' }));
    await waitFor(() => expect(calls.some(c => c.path === '/itineraries/it1/reorder')).toBe(true));
    expect(calls.find(c => c.path === '/itineraries/it1/reorder')!.body).toEqual({ days: [{ day_number: 1, activity_ids: ['act2', 'act1'] }, { day_number: 2, activity_ids: [] }] });
    expect(screen.getByRole('button', { name: 'Move Hawa Mahal earlier' })).toBeDisabled();
    const dur = screen.getAllByLabelText('Visit length (min)')[0];
    await user.clear(dur); await user.type(dur, '90'); await user.tab();
    await waitFor(() => expect(calls.find(c => c.method === 'PATCH' && c.path.endsWith('/act1'))!.body).toEqual({ duration_min: 90 }));
    await user.click(screen.getByRole('button', { name: 'Remove Hawa Mahal' }));
    await waitFor(() => expect(calls.some(c => c.method === 'DELETE')).toBe(true));
    expect(toast.success).toHaveBeenCalledWith('Activity removed');
  });

  it('saves the itinerary, renames it, and restores an earlier version', async () => {
    const user = userEvent.setup();
    const calls = mockApi(api({ 'PATCH /itineraries/it1': makeItinerary({ status: 'saved' }), 'POST /itineraries/it1/versions/2/restore': makeItinerary() }));
    view();
    await user.click(await screen.findByRole('button', { name: /Save itinerary/ }));
    await waitFor(() => expect(calls.find(c => c.method === 'PATCH')!.body).toEqual({ status: 'saved' }));
    const title = screen.getByLabelText('Trip title');
    await user.clear(title); await user.type(title, 'Pink City weekend'); await user.tab();
    await waitFor(() => expect(calls.filter(c => c.method === 'PATCH').at(-1)!.body).toEqual({ title: 'Pink City weekend' }));
    expect(await screen.findByText(/v2 · Removed Amber Fort/)).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Restore' }));
    await waitFor(() => expect(calls.some(c => c.path === '/itineraries/it1/versions/2/restore')).toBe(true));
  });

  it('regenerates with new interests and adds an attraction that is not yet in the trip', async () => {
    const user = userEvent.setup();
    const calls = mockApi(api({
      'POST /itineraries/it1/regenerate': makeItinerary(), 'POST /itineraries/it1/activities': makeItinerary(),
      'GET /attractions': page([makeAttraction(), makeAttraction({ id: 'a3', name: 'City Palace' })]),
    }));
    view();
    await user.click(await screen.findByRole('button', { name: /Regenerate/ }));
    const dlg = await screen.findByRole('dialog');
    await user.clear(within(dlg).getByLabelText('Interests')); await user.type(within(dlg).getByLabelText('Interests'), 'food, beach');
    await user.click(within(dlg).getByRole('button', { name: 'Regenerate' }));
    await waitFor(() => expect(calls.find(c => c.path.endsWith('/regenerate'))!.body).toEqual({ interests: ['food', 'beach'], budget_total_minor: 2000000 }));
    await user.click(await screen.findByRole('button', { name: /Add attraction/ }));
    await user.click(await screen.findByRole('combobox', { name: 'Attraction' }));
    expect(screen.queryByRole('option', { name: 'Hawa Mahal' })).not.toBeInTheDocument();      // already in the trip
    await user.click(await screen.findByRole('option', { name: 'City Palace' }));
    await user.click(screen.getByRole('button', { name: 'Add to trip' }));
    await waitFor(() => expect(calls.find(c => c.path.endsWith('/activities'))!.body).toEqual({ attraction_id: 'a3', day_number: 1 }));
  });

  it('shows not-found and error states, and deletes after confirmation', async () => {
    const user = userEvent.setup();
    mockApi({ 'GET /itineraries/it1': () => apiError(404, 'not_found', 'Itinerary not found') });
    view();
    expect(await screen.findByText('Trip not found')).toBeInTheDocument();
    vi.unstubAllGlobals();
    mockApi({ 'GET /itineraries/it1': () => apiError(500, 'internal_error', 'x') });
    view();
    expect((await screen.findAllByRole('alert')).length).toBeGreaterThan(0);
    vi.unstubAllGlobals();
    const calls = mockApi(api({ 'DELETE /itineraries/it1': () => new Response(null, { status: 204 }) }));
    view();
    await user.click(await screen.findByRole('button', { name: 'Delete itinerary' }));
    await user.click(within(await screen.findByRole('alertdialog')).getByRole('button', { name: 'Delete' }));
    await waitFor(() => expect(calls.some(c => c.method === 'DELETE')).toBe(true));
  });
});
