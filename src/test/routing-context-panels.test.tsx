import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { toast } from 'sonner';
import OptimizationPanel from '@/components/itinerary/OptimizationPanel';
import ContextPanel from '@/components/itinerary/ContextPanel';
import { apiError, makeContextStatus, makeItinerary, makeOptimization, makeProposal, mockApi, renderRoute } from './utils';

vi.mock('sonner', () => ({ toast: Object.assign(vi.fn(), { success: vi.fn(), error: vi.fn() }) }));
// The real map needs a browser layout engine; the stub exposes exactly what would be drawn.
vi.mock('@/components/itinerary/ItineraryMap', () => ({
  default: ({ routes, start }: { routes: { key: string; dashed?: boolean; title: string; stops: { name: string }[] }[]; start?: { name: string } }) => (
    <div data-testid="map" data-start={start?.name}>
      {routes.map(r => <div key={r.key} data-route={r.key} data-dashed={r.dashed ? 'true' : 'false'}>{r.title}: {r.stops.map(s => s.name).join(',')}</div>)}
    </div>
  ),
}));
beforeEach(() => vi.clearAllMocks());
afterEach(() => vi.unstubAllGlobals());
const IT = makeItinerary() as never;

describe('OptimizationPanel', () => {
  const view = () => renderRoute(<OptimizationPanel it={IT} />);

  it('previews, compares original and optimized routes, explains the changes and labels estimated travel data', async () => {
    const user = userEvent.setup();
    const calls = mockApi({ 'GET /itineraries/it1/optimizations': [], 'POST /itineraries/it1/optimize': makeOptimization() });
    view();
    await user.click(await screen.findByRole('button', { name: 'Preview optimization' }));
    const result = await screen.findByLabelText('Optimization result');
    expect(within(result).getByText('Optimized plan')).toBeInTheDocument();
    expect(within(result).getByText(/Distance \(-40%\)/)).toBeInTheDocument();
    expect(within(result).getByText('20 km')).toBeInTheDocument();
    expect(within(result).getByText('12 km')).toBeInTheDocument();
    expect(within(result).getByText(/Travel times are estimates/)).toBeInTheDocument();
    expect(within(result).getByText(/Travel data: estimate \(no live traffic\)/)).toBeInTheDocument();
    expect(within(result).getByText('Day 1 order changed: Hawa Mahal → Amber Fort ⇒ Amber Fort → Hawa Mahal.')).toBeInTheDocument();
    // map: the original is drawn dashed, the optimized route solid
    const map = within(result).getByTestId('map');
    expect(map.querySelector('[data-route="o1"]')).toHaveAttribute('data-dashed', 'true');
    expect(map.querySelector('[data-route="n1"]')).toHaveAttribute('data-dashed', 'false');
    expect(map.querySelector('[data-route="n1"]')!.textContent).toContain('Amber Fort,Hawa Mahal');
    expect(calls.find(c => c.path.endsWith('/optimize'))!.body).toEqual({ weights: { distance: 1, time: 1, cost: 0.5, preference: 1 }, improve: false });
  });

  it('applies an optimization and clears the preview; the previous run is listed in history', async () => {
    const user = userEvent.setup();
    const calls = mockApi({ 'GET /itineraries/it1/optimizations': [makeOptimization({ id: 'old', applied: true })], 'POST /itineraries/it1/optimize': makeOptimization(), 'POST /optimizations/op1/apply': makeItinerary({ current_version: 2 }) });
    view();
    expect(await screen.findByText(/-40% distance, -40% travel time · applied/)).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Preview optimization' }));
    await user.click(await screen.findByRole('button', { name: 'Apply this route' }));
    await waitFor(() => expect(calls.some(c => c.path === '/optimizations/op1/apply')).toBe(true));
    await waitFor(() => expect(screen.queryByLabelText('Optimization result')).not.toBeInTheDocument());
    expect(toast.success).toHaveBeenCalledWith('Optimized route applied');
  });

  it('shows an infeasible result honestly and cannot be applied', async () => {
    const user = userEvent.setup();
    mockApi({ 'GET /itineraries/it1/optimizations': [], 'POST /itineraries/it1/optimize': makeOptimization({ status: 'infeasible', after: null, delta: null, changes: ['No change was possible: No feasible schedule exists.'], notes: ['Locked activities need 2000 min but the trip offers only 1080 min of daytime.'] }) });
    view();
    await user.click(await screen.findByRole('button', { name: 'Preview optimization' }));
    expect(await screen.findByText('No feasible plan')).toBeInTheDocument();
    expect(screen.getByText(/No change was possible/)).toBeInTheDocument();
    expect(screen.getByText(/Locked activities need 2000 min/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Apply this route' })).toBeDisabled();
  });

  it('shows remaining violations of a relaxed plan, dropped activities, and a provider label', async () => {
    const user = userEvent.setup();
    const o = makeOptimization({ status: 'relaxed', routing: { source: 'osrm', notes: ['road network free-flow estimate from OSRM; no live traffic'], live_traffic: false, fetched_at: '' },
      dropped: [{ id: 'x', name: 'Jantar Mantar', reason: 'over the activity budget' }] });
    (o.after as { metrics: { violations: unknown[] } }).metrics.violations = [{ type: 'opening_hours', day: 1, message: 'Amber Fort: verified closed on that weekday' }];
    mockApi({ 'GET /itineraries/it1/optimizations': [], 'POST /itineraries/it1/optimize': o });
    view();
    await user.click(await screen.findByRole('button', { name: 'Preview optimization' }));
    expect(await screen.findByText(/Relaxed plan/)).toBeInTheDocument();
    expect(screen.getByText(/Travel data: osrm/)).toBeInTheDocument();
    expect(screen.queryByText(/Travel times are estimates/)).not.toBeInTheDocument();
    expect(screen.getByRole('alert')).toHaveTextContent('Amber Fort: verified closed on that weekday');
    expect(screen.getByText(/Would remove Jantar Mantar: over the activity budget/)).toBeInTheDocument();
  });

  it('surfaces server errors from the optimizer', async () => {
    const user = userEvent.setup();
    mockApi({ 'GET /itineraries/it1/optimizations': [], 'POST /itineraries/it1/optimize': () => apiError(422, 'empty_itinerary', 'Add activities before optimizing') });
    view();
    await user.click(await screen.findByRole('button', { name: 'Preview optimization' }));
    await waitFor(() => expect(toast.error).toHaveBeenCalledWith('Add activities before optimizing'));
  });
});

describe('ContextPanel', () => {
  const view = (it = IT) => renderRoute(<ContextPanel it={it} />);
  const base = (extra: Record<string, unknown> = {}) => ({ 'GET /itineraries/it1/context': makeContextStatus(), 'GET /itineraries/it1/adaptations': [], ...extra });

  it('explains that weather is unavailable without a provider and disables weather refresh', async () => {
    mockApi(base());
    view();
    expect(await screen.findByText(/No weather provider is configured/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Refresh weather' })).toBeDisabled();
    expect(screen.getByText(/unavailable until a provider is configured/)).toBeInTheDocument();
    expect(screen.getByText('No suggestions yet.')).toBeInTheDocument();
  });

  it('shows weather provenance and marks stale data as unused', async () => {
    mockApi(base({ 'GET /itineraries/it1/context': makeContextStatus({ weather_provider: 'open-meteo', weather_configured: true, notes: [], snapshots: [
      { id: 's1', kind: 'weather', day_number: 1, source: 'open-meteo', payload: { precip_prob: 80, temp_max_c: 31 }, fetched_at: '', age_minutes: 12, fresh: true },
      { id: 's2', kind: 'weather', day_number: 2, source: 'open-meteo', payload: { precip_prob: null }, fetched_at: '', age_minutes: 400, fresh: false }] }) }));
    view();
    expect(await screen.findByText(/Day 1: 80% rain, high 31°C · open-meteo, 12 min ago/)).toBeInTheDocument();
    expect(screen.getByText(/Day 2: rain chance unknown · open-meteo, 400 min ago \(stale: not used\)/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Refresh weather' })).toBeEnabled();
  });

  it('checks conditions, lists the proposal with evidence and source, and approves it', async () => {
    const user = userEvent.setup();
    const state = { proposals: [] as unknown[] };
    const calls = mockApi({
      'GET /itineraries/it1/context': makeContextStatus(), 'GET /itineraries/it1/adaptations': () => state.proposals,
      'POST /itineraries/it1/adapt': () => { state.proposals = [makeProposal()]; return { issues: [], proposals: state.proposals, unresolved: [], stale_days: [], notes: ['Weather for day(s) 2 is older than 180 minutes and was NOT used. Refresh it first.'], latency_ms: 3 }; },
      'POST /adaptations/pr1/approve': () => { state.proposals = [makeProposal({ status: 'approved' })]; return makeItinerary({ current_version: 2 }); },
    });
    view();
    await user.click(await screen.findByRole('button', { name: 'Check conditions' }));
    const card = await screen.findByRole('listitem', { name: 'Suggestion: rain' });
    expect(within(card).getByText(/85% chance of rain, 12\.0 mm expected \(open-meteo/)).toBeInTheDocument();
    expect(within(card).getByText(/source: open-meteo/)).toBeInTheDocument();
    expect(within(card).getByText('Amber Fort').tagName).toBe('STRONG');
    expect(await screen.findByText(/was NOT used/)).toBeInTheDocument();
    expect(calls.some(c => c.path.endsWith('/apply'))).toBe(false);      // proposing changes nothing
    await user.click(within(card).getByRole('button', { name: 'Approve change' }));
    await waitFor(() => expect(calls.some(c => c.path === '/adaptations/pr1/approve')).toBe(true));
    expect(toast.success).toHaveBeenCalledWith('Change applied');
    expect(await screen.findByText('approved')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Approve change' })).not.toBeInTheDocument();
  });

  it('rejects a proposal without touching the itinerary', async () => {
    const user = userEvent.setup();
    const state = { p: [makeProposal()] };
    const calls = mockApi(base({ 'GET /itineraries/it1/adaptations': () => state.p, 'POST /adaptations/pr1/reject': () => { state.p = [makeProposal({ status: 'rejected' })]; return state.p[0]; } }));
    view();
    await user.click(await screen.findByRole('button', { name: 'Reject' }));
    await waitFor(() => expect(calls.some(c => c.path === '/adaptations/pr1/reject')).toBe(true));
    expect(await screen.findByText('rejected')).toBeInTheDocument();
    expect(calls.some(c => c.path.includes('/approve'))).toBe(false);
  });

  it('shows conflict errors, e.g. a stale proposal', async () => {
    const user = userEvent.setup();
    mockApi(base({ 'GET /itineraries/it1/adaptations': [makeProposal()], 'POST /adaptations/pr1/approve': () => apiError(409, 'stale_proposal', 'The itinerary changed after this suggestion was made; check conditions again') }));
    view();
    await user.click(await screen.findByRole('button', { name: 'Approve change' }));
    await waitFor(() => expect(toast.error).toHaveBeenCalledWith('The itinerary changed after this suggestion was made; check conditions again'));
  });

  it('sends traveler reports for closure, delay and spending', async () => {
    const user = userEvent.setup();
    const calls = mockApi(base({ 'POST /itineraries/it1/context/report': makeContextStatus() }));
    view();
    await user.click(await screen.findByText('Tell us what is happening'));
    await user.click(screen.getByRole('combobox', { name: /Place is closed/ }));
    await user.click(await screen.findByRole('option', { name: 'Amber Fort' }));
    await user.click(screen.getByRole('button', { name: 'Report closure' }));
    await waitFor(() => expect(calls.find(c => c.path.endsWith('/report'))!.body).toEqual({ type: 'closure', activity_id: 'act2' }));
    const time = screen.getByLabelText('Current time');
    await user.clear(time); await user.type(time, '15:30');
    await user.click(screen.getByRole('button', { name: 'Report delay' }));
    await waitFor(() => expect(calls.filter(c => c.path.endsWith('/report')).at(-1)!.body).toEqual({ type: 'delay', day_number: 1, current_time_min: 930, completed_activity_ids: [] }));
    await user.type(screen.getByLabelText(/Spent so far/), '2500');
    await user.click(screen.getByRole('button', { name: 'Report spending' }));
    await waitFor(() => expect(calls.filter(c => c.path.endsWith('/report')).at(-1)!.body).toEqual({ type: 'spent', spent_minor: 250000 }));
  });

  it('refreshes weather when a provider is configured and shows provider errors', async () => {
    const user = userEvent.setup();
    mockApi(base({ 'GET /itineraries/it1/context': makeContextStatus({ weather_provider: 'open-meteo', weather_configured: true, notes: [] }),
      'POST /itineraries/it1/context/refresh': () => apiError(502, 'provider_error', 'The weather provider failed: boom') }));
    view();
    await user.click(await screen.findByRole('button', { name: 'Refresh weather' }));
    await waitFor(() => expect(toast.error).toHaveBeenCalledWith('The weather provider failed: boom'));
  });

  it('disables weather refresh until the trip has dates', async () => {
    mockApi(base({ 'GET /itineraries/it1/context': makeContextStatus({ weather_provider: 'open-meteo', weather_configured: true, needs_dates: true, notes: ['Set trip dates to enable weather checks.'] }) }));
    view();
    expect(await screen.findByText(/Set trip dates to enable weather checks\./)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Refresh weather' })).toBeDisabled();
  });
});
