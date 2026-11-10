import { afterEach, describe, expect, it, vi } from 'vitest';
import { screen } from '@testing-library/react';
import RecommendationsSection from '@/components/recommendations/RecommendationsSection';
import { apiError, makeDest, makeRecItem, makeRecResponse, mockApi, renderRoute } from './utils';

afterEach(() => vi.unstubAllGlobals());
const view = () => renderRoute(<RecommendationsSection />);

describe('Dashboard recommendations section', () => {
  it('requests the top 3 destinations and shows compact cards with a link to the full page', async () => {
    const items = [makeRecItem(), makeRecItem({ recommendation_item_id: 'ri2', rank: 2, destination: makeDest({ id: 'd2', slug: 'goa', name: 'Goa' }) })];
    const calls = mockApi({ 'POST /recommendations/destinations': makeRecResponse(items) });
    view();
    expect(await screen.findByRole('article', { name: /Goa/ })).toBeInTheDocument();
    expect(calls[0].body).toMatchObject({ page: 1, page_size: 3 });
    expect(screen.getByRole('link', { name: /Tune & see more/ })).toHaveAttribute('href', '/dashboard/recommendations');
    expect(screen.queryByRole('button', { name: /Why this/ })).not.toBeInTheDocument();   // compact: no long explanation UI
    expect(screen.getAllByText(/Matches your interest in history/).length).toBeGreaterThan(0);
  });

  it('shows loading, empty, error and fallback states', async () => {
    mockApi({ 'POST /recommendations/destinations': makeRecResponse([]) });
    view();
    expect(screen.getByRole('status', { name: 'Loading' })).toBeInTheDocument();
    expect(await screen.findByText('No recommendations yet')).toBeInTheDocument();
    vi.unstubAllGlobals();
    mockApi({ 'POST /recommendations/destinations': apiError(500, 'internal_error', 'x') });
    view();
    expect((await screen.findAllByRole('alert')).length).toBeGreaterThan(0);
    vi.unstubAllGlobals();
    mockApi({ 'POST /recommendations/destinations': makeRecResponse([makeRecItem()], { strategy: 'popularity_fallback' }) });
    view();
    expect(await screen.findByText(/Showing popular places/)).toBeInTheDocument();
  });
});
