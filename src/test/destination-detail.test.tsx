import { afterEach, describe, expect, it, vi } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import DestinationDetail from '@/pages/client/DestinationDetail';
import { CATS, apiError, makeAttraction, makeDest, mockApi, page, renderRoute } from './utils';

afterEach(() => vi.unstubAllGlobals());
const view = (slug = 'jaipur') => renderRoute(<DestinationDetail />, { path: '/dashboard/destinations/:ref', route: `/dashboard/destinations/${slug}` });

describe('DestinationDetail', () => {
  it('renders facts, estimates disclaimer and its attractions', async () => {
    const calls = mockApi({
      'GET /destinations/jaipur': makeDest(),
      'GET /categories': CATS,
      'GET /attractions': page([makeAttraction(), makeAttraction({ id: 'a2', name: 'Amber Fort', estimated_cost_minor: 20000, is_outdoor: true })]),
    });
    view();
    expect(await screen.findByRole('heading', { name: /Jaipur/, level: 1 })).toBeInTheDocument();
    expect(await screen.findByText('Hawa Mahal')).toBeInTheDocument();
    expect(screen.getByText('Amber Fort')).toBeInTheDocument();
    expect(screen.getByText('₹3,200')).toBeInTheDocument();
    expect(screen.getByText(/curated estimates, not live data/i)).toBeInTheDocument();
    expect(screen.getAllByText(/not verified/i).length).toBe(2); // unknown opening hours are never presented as fact
    expect(screen.getByText('Entry: unknown')).toBeInTheDocument();
    const attractionCall = calls.find(c => c.path === '/attractions')!;
    expect(attractionCall.query.get('destination_id')).toBe('d1');
    expect(attractionCall.query.get('lat')).toBeNull(); // no radius selected by default
  });

  it('shows a not-found state for an unknown or unpublished destination', async () => {
    mockApi({ 'GET /destinations/nowhere': apiError(404, 'not_found', 'Destination not found'), 'GET /categories': CATS });
    view('nowhere');
    expect(await screen.findByText('Destination not found')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /All destinations/ })).toHaveAttribute('href', '/dashboard/destinations');
  });

  it('shows an error state for server failures and an empty state without attractions', async () => {
    mockApi({ 'GET /destinations/jaipur': apiError(500, 'internal_error', 'x'), 'GET /categories': CATS });
    view();
    expect(await screen.findByRole('alert')).toHaveTextContent("couldn't load this destination");
    vi.unstubAllGlobals();
    mockApi({ 'GET /destinations/jaipur': makeDest({ attraction_count: 0 }), 'GET /categories': CATS, 'GET /attractions': page([]) });
    view();
    expect(await screen.findByText('No attractions found')).toBeInTheDocument();
  });

  it('applies a radius filter around the destination centre and shows distances', async () => {
    const calls = mockApi({
      'GET /destinations/jaipur': makeDest(), 'GET /categories': CATS,
      'GET /attractions': c => page([makeAttraction({ distance_m: c.query.get('radius_km') ? 1234 : null })]),
    });
    view();
    await screen.findByText('Hawa Mahal');
    const { default: userEvent } = await import('@testing-library/user-event');
    const user = userEvent.setup();
    await user.click(screen.getByRole('combobox', { name: 'Distance from centre' }));
    await user.click(await screen.findByRole('option', { name: 'Within 10 km of centre' }));
    await waitFor(() => expect(screen.getByText('1.2 km from centre')).toBeInTheDocument());
    const last = calls.filter(c => c.path === '/attractions').at(-1)!;
    expect(last.query.get('radius_km')).toBe('10');
    expect(last.query.get('lat')).toBe('26.9124');
    expect(last.query.get('sort')).toBe('distance');
  });
});
