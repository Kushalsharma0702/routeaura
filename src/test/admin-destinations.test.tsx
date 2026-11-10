import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { toast } from 'sonner';
import ManageDestinations from '@/pages/admin/ManageDestinations';
import { CATS, apiError, makeDest, mockApi, page, renderRoute } from './utils';

vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: vi.fn() } }));
beforeEach(() => vi.clearAllMocks());
afterEach(() => vi.unstubAllGlobals());
const view = () => renderRoute(<ManageDestinations />);

const fill = async (user: ReturnType<typeof userEvent.setup>, v: Record<string, string>) => {
  for (const [label, value] of Object.entries(v)) {
    const el = screen.getByLabelText(label);
    await user.clear(el);
    await user.type(el, value);
  }
};

describe('Admin destinations', () => {
  it('lists destinations with draft/published status and attraction links', async () => {
    mockApi({ 'GET /admin/destinations': () => page([makeDest(), makeDest({ id: 'd2', slug: 'goa', name: 'Goa', is_published: false })], 2), 'GET /categories': CATS });
    view();
    expect(await screen.findByText('Published')).toBeInTheDocument();
    expect(screen.getByText('Draft')).toBeInTheDocument();
    expect(screen.getAllByRole('link', { name: /Attractions/ })[0]).toHaveAttribute('href', '/admin/destinations/d1/attractions');
  });

  it('shows an empty state and an error state', async () => {
    mockApi({ 'GET /admin/destinations': () => page([]), 'GET /categories': CATS });
    view();
    expect(await screen.findByText('No destinations yet')).toBeInTheDocument();
    vi.unstubAllGlobals();
    mockApi({ 'GET /admin/destinations': () => apiError(500, 'internal_error', 'x'), 'GET /categories': CATS });
    view();
    expect(await screen.findByRole('alert')).toBeInTheDocument();
  });

  it('blocks invalid coordinates client-side without calling the API', async () => {
    const user = userEvent.setup();
    const calls = mockApi({ 'GET /admin/destinations': () => page([]), 'GET /categories': CATS });
    view();
    await screen.findByText('No destinations yet');
    await user.click(screen.getByRole('button', { name: /Add Destination/ }));
    await fill(user, { Name: 'Nowhere', Country: 'India', Latitude: '95', Longitude: '-181' });
    await user.click(screen.getByRole('button', { name: 'Create' }));
    expect(await screen.findByText(/Latitude must be between -90 and 90/)).toBeInTheDocument();
    expect(screen.getByText(/Longitude must be between -180 and 180/)).toBeInTheDocument();
    expect(calls.some(c => c.method === 'POST')).toBe(false);
  });

  it('creates a destination with correctly converted values and refreshes the list', async () => {
    const user = userEvent.setup();
    let created = false;
    const calls = mockApi({
      'GET /admin/destinations': () => page(created ? [makeDest({ name: 'Udaipur' })] : []),
      'GET /categories': CATS,
      'POST /admin/destinations': () => { created = true; return json201(); },
    });
    view();
    await screen.findByText('No destinations yet');
    await user.click(screen.getByRole('button', { name: /Add Destination/ }));
    await fill(user, { Name: 'Udaipur', Country: 'India', Latitude: '24.5854', Longitude: '73.7125', 'Estimated cost per day (₹)': '4500', 'Recommended days': '3' });
    await user.click(screen.getByRole('checkbox', { name: /History/ }));
    await user.click(screen.getByLabelText(/Published/));
    await user.click(screen.getByRole('button', { name: 'Create' }));
    await waitFor(() => expect(toast.success).toHaveBeenCalledWith('Destination created'));
    const post = calls.find(c => c.method === 'POST')!;
    expect(post.body).toMatchObject({
      name: 'Udaipur', country: 'India', latitude: 24.5854, longitude: 73.7125,
      estimated_cost_per_day_minor: 450000, recommended_duration_days: 3, is_published: true,
      category_ids: ['c1'], best_season_start_month: null, climate: null,
    });
    expect(await screen.findByText('Udaipur')).toBeInTheDocument(); // list was refetched
  });

  it('surfaces server-side rejections as an error toast and keeps the form open', async () => {
    const user = userEvent.setup();
    mockApi({ 'GET /admin/destinations': () => page([]), 'GET /categories': CATS, 'POST /admin/destinations': () => apiError(403, 'forbidden', 'You do not have permission to do that') });
    view();
    await screen.findByText('No destinations yet');
    await user.click(screen.getByRole('button', { name: /Add Destination/ }));
    await fill(user, { Name: 'Udaipur', Country: 'India', Latitude: '24', Longitude: '73' });
    await user.click(screen.getByRole('button', { name: 'Create' }));
    await waitFor(() => expect(toast.error).toHaveBeenCalledWith('You do not have permission to do that'));
    expect(screen.getByRole('dialog')).toBeInTheDocument();
  });

  it('edits an existing destination with prefilled values (PATCH)', async () => {
    const user = userEvent.setup();
    const calls = mockApi({ 'GET /admin/destinations': () => page([makeDest()]), 'GET /categories': CATS, 'PATCH /admin/destinations/d1': () => makeDest({ name: 'Jaipur City' }) });
    view();
    await screen.findByText('Jaipur');
    await user.click(screen.getByRole('button', { name: /^Edit/ }));
    expect(screen.getByLabelText('Name')).toHaveValue('Jaipur');
    expect(screen.getByLabelText('Estimated cost per day (₹)')).toHaveValue('3200');
    await fill(user, { Name: 'Jaipur City' });
    await user.click(screen.getByRole('button', { name: 'Save Changes' }));
    await waitFor(() => expect(toast.success).toHaveBeenCalledWith('Destination updated'));
    expect(calls.find(c => c.method === 'PATCH')!.body).toMatchObject({ name: 'Jaipur City', estimated_cost_per_day_minor: 320000 });
  });

  it('asks for confirmation before deleting', async () => {
    const user = userEvent.setup();
    const calls = mockApi({ 'GET /admin/destinations': () => page([makeDest()]), 'GET /categories': CATS, 'DELETE /admin/destinations/d1': () => new Response(null, { status: 204 }) });
    view();
    await screen.findByText('Jaipur');
    await user.click(screen.getByRole('button', { name: 'Delete Jaipur' }));
    expect(calls.some(c => c.method === 'DELETE')).toBe(false); // not yet
    await user.click(within(screen.getByRole('alertdialog')).getByRole('button', { name: 'Delete' }));
    await waitFor(() => expect(toast.success).toHaveBeenCalledWith('Destination deleted'));
    expect(calls.some(c => c.method === 'DELETE' && c.path === '/admin/destinations/d1')).toBe(true);
  });

  it('shows the API error when a category is in use', async () => {
    const user = userEvent.setup();
    mockApi({ 'GET /admin/destinations': () => page([makeDest()]), 'GET /categories': CATS, 'DELETE /admin/categories/c1': () => apiError(409, 'category_in_use', 'Category is used by 3 record(s)') });
    view();
    await screen.findByText('Jaipur');
    await user.click(screen.getByRole('button', { name: /Categories/ }));
    await user.click(await screen.findByRole('button', { name: 'Delete History & Heritage' }));
    await waitFor(() => expect(toast.error).toHaveBeenCalledWith('Category is used by 3 record(s)'));
  });
});

function json201() {
  return new Response(JSON.stringify(makeDest({ name: 'Udaipur' })), { status: 201, headers: { 'content-type': 'application/json' } });
}
