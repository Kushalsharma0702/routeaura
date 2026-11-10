import { afterEach, describe, expect, it } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { vi } from 'vitest';
import BrowseDestinations from '@/pages/client/BrowseDestinations';
import { CATS, apiError, makeDest, mockApi, page, renderRoute } from './utils';

afterEach(() => vi.unstubAllGlobals());
const view = () => renderRoute(<BrowseDestinations />);

describe('BrowseDestinations', () => {
  it('shows a loading state, then destination cards linking to details', async () => {
    mockApi({ 'GET /categories': CATS, 'GET /destinations': () => page([makeDest(), makeDest({ id: 'd2', slug: 'goa', name: 'Goa' })], 2) });
    view();
    expect(screen.getByRole('status', { name: 'Loading' })).toBeInTheDocument();
    const link = await screen.findByRole('link', { name: /Jaipur, India/ });
    expect(link).toHaveAttribute('href', '/dashboard/destinations/jaipur');
    expect(screen.getByRole('link', { name: /Goa/ })).toBeInTheDocument();
    expect(screen.getByText('2 destinations')).toBeInTheDocument();
    expect(screen.getAllByText('Oct – Mar')).toHaveLength(2);
    expect(screen.getAllByText(/estimate/i).length).toBeGreaterThan(0); // costs are labelled as estimates
  });

  it('shows an empty state with a filter hint when nothing matches', async () => {
    const user = userEvent.setup();
    mockApi({ 'GET /categories': CATS, 'GET /destinations': c => page(c.query.get('q') ? [] : [makeDest()]) });
    view();
    await screen.findByText('Jaipur');
    await user.type(screen.getByLabelText('Search destinations'), 'zzz');
    expect(await screen.findByText('No destinations match your filters')).toBeInTheDocument();
  });

  it('shows an error state and recovers on retry', async () => {
    const user = userEvent.setup();
    let fail = true;
    mockApi({ 'GET /categories': CATS, 'GET /destinations': () => (fail ? apiError(500, 'internal_error', 'boom') : page([makeDest()])) });
    view();
    expect(await screen.findByRole('alert')).toHaveTextContent("couldn't load destinations");
    fail = false;
    await user.click(screen.getByRole('button', { name: 'Try again' }));
    expect(await screen.findByText('Jaipur')).toBeInTheDocument();
  });

  it('sends the debounced search term to the API and resets to page 1', async () => {
    const user = userEvent.setup();
    const calls = mockApi({ 'GET /categories': CATS, 'GET /destinations': () => page([makeDest()], 20) });
    view();
    await screen.findByText('Jaipur');
    await user.click(screen.getByRole('button', { name: 'Next' }));
    await waitFor(() => expect(calls.some(c => c.path === '/destinations' && c.query.get('page') === '2')).toBe(true));
    await user.type(screen.getByLabelText('Search destinations'), 'pink');
    await waitFor(() => {
      const last = calls.filter(c => c.path === '/destinations').at(-1)!;
      expect(last.query.get('q')).toBe('pink');
      expect(last.query.get('page')).toBe('1');
    });
  });

  it('paginates with next/previous', async () => {
    const user = userEvent.setup();
    const calls = mockApi({ 'GET /categories': CATS, 'GET /destinations': c => page([makeDest({ name: `Page ${c.query.get('page')} place` })], 25, Number(c.query.get('page'))) });
    view();
    expect(await screen.findByText('Page 1 place')).toBeInTheDocument();
    expect(screen.getByText('Page 1 of 3')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Previous' })).toBeDisabled();
    await user.click(screen.getByRole('button', { name: 'Next' }));
    expect(await screen.findByText('Page 2 place')).toBeInTheDocument();
    expect(calls.filter(c => c.path === '/destinations').map(c => c.query.get('page'))).toContain('2');
  });
});
