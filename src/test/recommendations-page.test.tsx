import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { toast } from 'sonner';
import Recommendations from '@/pages/client/Recommendations';
import { CATS, PREFS, STATE0, apiError, makeAttraction, makeDest, makeRecItem, makeRecResponse, mockApi, page, renderRoute } from './utils';

vi.mock('sonner', () => ({ toast: Object.assign(vi.fn(), { success: vi.fn(), error: vi.fn() }) }));
beforeEach(() => vi.clearAllMocks());
afterEach(() => vi.unstubAllGlobals());
const view = () => renderRoute(<Recommendations />);
const base = (extra: Record<string, unknown> = {}) => ({
  'GET /users/me/preferences': PREFS, 'GET /categories': CATS,
  'POST /recommendations/destinations': makeRecResponse(), 'POST /interactions': { recorded: true, state: { ...STATE0, saved: true } },
  ...extra,
});
const second = makeRecItem({ recommendation_item_id: 'ri2', rank: 2, destination: makeDest({ id: 'd2', slug: 'goa', name: 'Goa' }), score: 0.61, reasons: ['Tropical climate matches your preference.'], cautions: [], missing: [] });

describe('Recommendations page', () => {
  it('shows live recommendations with score, coverage, reasons, cautions, missing-data note and an honest disclaimer', async () => {
    mockApi(base());
    view();
    expect(await screen.findByRole('article', { name: /Recommendation 1: Jaipur/ })).toBeInTheDocument();
    expect(screen.getByText('Match 82%')).toBeInTheDocument();
    expect(screen.getByRole('meter', { name: 'Match score' })).toHaveAttribute('aria-valuenow', '82');
    expect(screen.getByText('Based on 80% of your criteria')).toBeInTheDocument();
    expect(screen.getByText(/Matches your interest in history/)).toBeInTheDocument();
    expect(screen.getByText(/within your ₹4,000\/day budget/)).toBeInTheDocument();
    expect(screen.getByText(/outside its best season/)).toBeInTheDocument();
    expect(screen.getByText(/1 of your criteria could not be checked/)).toBeInTheDocument();
    expect(screen.getByText(/not probabilities of satisfaction/)).toBeInTheDocument();
    expect(screen.getByText('Personalised using all of your preferences · with variety')).toBeInTheDocument();
  });

  it('expands "Why this?" to show each factor, its weight and its status, hiding unused factors', async () => {
    const user = userEvent.setup();
    mockApi(base());
    view();
    await user.click(await screen.findByRole('button', { name: /Why this\?/ }));
    expect(await screen.findByText(/weight 50%/)).toBeInTheDocument();
    expect(screen.getAllByText('Good match')).toHaveLength(2);
    expect(screen.getByText('No data')).toBeInTheDocument();
    expect(screen.queryByText(/Not used: you didn't set/)).not.toBeInTheDocument();
  });

  it('pre-fills controls from saved preferences and sends only changed values, priorities and strategy', async () => {
    const user = userEvent.setup();
    const calls = mockApi(base());
    view();
    await screen.findByText('Jaipur');
    await waitFor(() => expect(screen.getByLabelText('Interests')).toHaveValue('history, food'));
    expect(screen.getByLabelText('Budget per day (₹)')).toHaveValue('4000');
    const first = calls.find(c => c.path === '/recommendations/destinations')!;
    expect(first.body).toMatchObject({ page: 1, page_size: 6 });   // first load relies on the server defaults
    expect((first.body as { overrides?: unknown }).overrides).toBeUndefined();

    await user.clear(screen.getByLabelText('Budget per day (₹)'));
    await user.type(screen.getByLabelText('Budget per day (₹)'), '2500');
    await user.clear(screen.getByLabelText('Interests'));
    await user.type(screen.getByLabelText('Interests'), 'beach');
    await user.click(screen.getByText('How much does each factor matter?'));
    await user.click(screen.getByRole('combobox', { name: 'Budget importance' }));
    await user.click(await screen.findByRole('option', { name: 'High' }));
    await user.click(screen.getByRole('button', { name: 'Get recommendations' }));
    await waitFor(() => {
      const last = calls.filter(c => c.path === '/recommendations/destinations').at(-1)!.body as Record<string, unknown>;
      expect(last.overrides).toEqual({ budget_per_day_minor: 250000, interests: ['beach'] });
      expect(last.priorities).toEqual({ budget: 'high' });
    });
  });

  it('saves a recommendation (POST /interactions) and reflects the saved state', async () => {
    const user = userEvent.setup();
    const calls = mockApi(base());
    view();
    await user.click(await screen.findByRole('button', { name: 'Save' }));
    await waitFor(() => expect(screen.getByRole('button', { name: 'Saved' })).toHaveAttribute('aria-pressed', 'true'));
    const post = calls.find(c => c.path === '/interactions')!;
    expect(post.body).toMatchObject({ item_type: 'destination', item_id: 'd1', interaction_type: 'save', source: 'recommendation', recommendation_item_id: 'ri1' });
    expect(toast.success).toHaveBeenCalledWith('Saved');
  });

  it('hides a dismissed recommendation, records it, and offers undo', async () => {
    const user = userEvent.setup();
    const calls = mockApi(base({ 'POST /recommendations/destinations': makeRecResponse([makeRecItem(), second]) }));
    view();
    await screen.findByText('Goa');
    await user.click(screen.getByRole('button', { name: 'Hide Jaipur' }));
    await waitFor(() => expect(screen.queryByRole('article', { name: /Jaipur/ })).not.toBeInTheDocument());
    expect(screen.getByRole('article', { name: /Goa/ })).toBeInTheDocument();
    expect(calls.find(c => c.path === '/interactions')!.body).toMatchObject({ interaction_type: 'dismiss' });
    const [, opts] = (toast as unknown as ReturnType<typeof vi.fn>).mock.calls.at(-1)!;
    await opts.action.onClick();
    expect(calls.filter(c => c.path === '/interactions').at(-1)!.body).toMatchObject({ interaction_type: 'restore' });
    await waitFor(() => expect(screen.getByRole('article', { name: /Jaipur/ })).toBeInTheDocument());
  });

  it('collects feedback: thumbs-up and a reasoned thumbs-down', async () => {
    const user = userEvent.setup();
    const calls = mockApi(base({ 'POST /recommendations/feedback': { rating: 'relevant' } }));
    view();
    await user.click(await screen.findByRole('button', { name: 'Relevant' }));
    await waitFor(() => expect(screen.getByRole('button', { name: 'Relevant' })).toHaveAttribute('aria-pressed', 'true'));
    expect(calls.find(c => c.path === '/recommendations/feedback')!.body).toEqual({ recommendation_item_id: 'ri1', rating: 'relevant', reasons: [] });
    await user.click(screen.getByRole('button', { name: 'Not relevant' }));
    await user.click(await screen.findByRole('menuitem', { name: 'Too expensive' }));
    await waitFor(() => expect(calls.filter(c => c.path === '/recommendations/feedback')).toHaveLength(2));
    expect(calls.filter(c => c.path === '/recommendations/feedback').at(-1)!.body).toEqual({ recommendation_item_id: 'ri1', rating: 'not_relevant', reasons: ['too_expensive'] });
    expect(screen.getByRole('button', { name: 'Not relevant' })).toHaveAttribute('aria-pressed', 'true');
  });

  it('explains the popularity fallback and points to preferences', async () => {
    mockApi(base({ 'POST /recommendations/destinations': makeRecResponse([makeRecItem({ components: [], reasons: ['Popular with other travelers.'], cautions: [], missing: [] })],
      { strategy: 'popularity_fallback', diversified: false, notes: ['No usable preferences or history yet, so popular places are shown instead. Set your preferences for personalised results.'] }) }));
    view();
    expect(await screen.findByText('Popular places (no preferences yet)')).toBeInTheDocument();
    expect(screen.getByText(/No usable preferences or history yet/)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Set your travel preferences' })).toHaveAttribute('href', '/dashboard/profile');
    expect(screen.queryByText(/Based on \d+% of your criteria/)).not.toBeInTheDocument();
  });

  it('shows empty and error states, and recovers on retry', async () => {
    const user = userEvent.setup();
    mockApi(base({ 'POST /recommendations/destinations': makeRecResponse([]) }));
    view();
    expect(await screen.findByText('No recommendations found')).toBeInTheDocument();
    vi.unstubAllGlobals();
    let fail = true;
    mockApi(base({ 'POST /recommendations/destinations': () => (fail ? apiError(500, 'internal_error', 'x') : makeRecResponse()) }));
    view();
    const alerts = await screen.findAllByRole('alert');
    expect(alerts.some(a => /couldn't generate recommendations/.test(a.textContent ?? ''))).toBe(true);
    fail = false;
    await user.click(within(alerts.find(a => /couldn't generate/.test(a.textContent ?? ''))!).getByRole('button', { name: 'Try again' }));
    expect(await screen.findAllByText('Jaipur')).not.toHaveLength(0);
  });

  it('pages through recommendations using the server total', async () => {
    const user = userEvent.setup();
    const calls = mockApi(base({ 'POST /recommendations/destinations': c => makeRecResponse([makeRecItem({ recommendation_item_id: `p${(c.body as { page: number }).page}`, destination: makeDest({ name: `Place on page ${(c.body as { page: number }).page}` }) })], { total_candidates: 13, page: (c.body as { page: number }).page }) }));
    view();
    expect(await screen.findByText('Place on page 1')).toBeInTheDocument();
    expect(screen.getByText('Page 1 of 3')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Next' }));
    expect(await screen.findByText('Place on page 2')).toBeInTheDocument();
    expect(calls.filter(c => c.path === '/recommendations/destinations').map(c => (c.body as { page: number }).page)).toEqual([1, 2]);
  });

  it('shows attraction recommendations with the outdoor filter and links to the parent destination', async () => {
    const user = userEvent.setup();
    const attr = makeRecItem({ kind: 'attraction', destination: null, attraction: makeAttraction({ name: 'Amber Fort', destination_id: 'd1' }), recommendation_item_id: 'ra1' });
    const calls = mockApi(base({ 'POST /recommendations/attractions': makeRecResponse([attr], { kind: 'attraction' }) }));
    view();
    await screen.findByText('Jaipur');
    await user.click(screen.getByRole('tab', { name: 'Attractions' }));
    expect(await screen.findByRole('article', { name: /Amber Fort/ })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Open Amber Fort' })).toHaveAttribute('href', '/dashboard/destinations/d1');
    await user.click(screen.getByLabelText('Outdoor attractions only'));
    await waitFor(() => expect(calls.filter(c => c.path === '/recommendations/attractions').at(-1)!.body).toMatchObject({ filters: { outdoor: true } }));
  });

  it('lists saved places and removes one', async () => {
    const user = userEvent.setup();
    const calls = mockApi(base({
      'GET /interactions/saved': page([{ item_type: 'destination', destination: makeDest({ name: 'Goa', slug: 'goa' }), attraction: null }]),
      'POST /interactions': { recorded: true, state: STATE0 },
    }));
    view();
    await screen.findByText('Jaipur');
    await user.click(screen.getByRole('tab', { name: 'Saved' }));
    expect(await screen.findByRole('link', { name: 'Goa' })).toHaveAttribute('href', '/dashboard/destinations/goa');
    await user.click(screen.getByRole('button', { name: 'Remove' }));
    await waitFor(() => expect(calls.some(c => c.method === 'POST' && c.path === '/interactions')).toBe(true));
    expect(calls.find(c => c.path === '/interactions')!.body).toMatchObject({ interaction_type: 'unsave', item_id: 'd1' });
  });

  it('shows generation history, with an empty state when there is none', async () => {
    const user = userEvent.setup();
    mockApi(base({ 'GET /recommendations/history': page([{ run_id: 'r1', kind: 'destination', strategy: 'weighted', model_version: 'content-v1', created_at: '2026-11-11T10:00:00Z', total_candidates: 5, returned_count: 3, page: 1, page_size: 6, diversified: true, preferences: {}, top_items: ['Jaipur', 'Goa'] }]) }));
    view();
    await screen.findByText('Jaipur');
    await user.click(screen.getByRole('tab', { name: 'History' }));
    expect(await screen.findByText('Top: Jaipur, Goa')).toBeInTheDocument();
    expect(screen.getByText(/3 shown of 5/)).toBeInTheDocument();
    vi.unstubAllGlobals();
    mockApi(base({ 'GET /recommendations/history': page([]) }));
    view();
    await user.click((await screen.findAllByRole('tab', { name: 'History' })).at(-1)!);
    expect(await screen.findByText('No history yet')).toBeInTheDocument();
  });
});
