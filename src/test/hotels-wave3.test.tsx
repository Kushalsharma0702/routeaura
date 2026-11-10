import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import HotelDetail from '@/pages/client/HotelDetail';
import ManageHotels from '@/pages/admin/ManageHotels';
import { apiError, makeDest, mockApi, page, renderRoute } from './utils';

vi.mock('@/contexts/AuthContext', () => ({ useAuth: () => ({ user: { id: 'u1', name: 'Asha', email: 'a@b.co', role: 'client' } }) }));
vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: vi.fn() } }));
beforeEach(() => vi.clearAllMocks());
afterEach(() => vi.unstubAllGlobals());

const room = { id: 'r1', hotel_id: 'h1', name: 'Deluxe', description: '', capacity: 2, price_per_night_minor: 400000, currency: 'INR', total_rooms: 3, amenities: [], is_active: true };
const hotel = (o = {}) => ({ id: 'h1', slug: 'amber-haveli', name: 'Amber Haveli', description: 'd', address: null, latitude: 26.9, longitude: 75.8, star_rating: 4, amenities: ['Wi-Fi'], images: [],
  is_published: true, source: 'seed', destination_id: 'd1', destination_name: 'Jaipur', room_types: [room], from_price_minor: 400000, currency: 'INR', ...o });

describe('Hotel detail', () => {
  it('checks availability with the entered dates and flags seed data as illustrative', async () => {
    const calls = mockApi({
      'GET /hotels/amber-haveli': hotel(),
      'GET /hotels/amber-haveli/availability': () => ({ hotel_id: 'h1', check_in: '2030-02-01', check_out: '2030-02-03', guests: 2, rooms: 1,
        options: [{ room_type: room, nights: 2, available_rooms: 0, price_per_night_minor: 400000, total_minor: 800000, can_book: false, reason: 'Sold out for some nights' }] }),
    });
    renderRoute(<HotelDetail />, { path: '/h/:ref', route: '/h/amber-haveli' });
    expect(await screen.findByText(/fictional property with placeholder prices/)).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('Check-in'), { target: { value: '2030-02-01' } });
    fireEvent.change(screen.getByLabelText('Check-out'), { target: { value: '2030-02-03' } });
    await userEvent.setup().click(screen.getByRole('button', { name: 'Check availability' }));
    expect(await screen.findByText('Sold out for some nights')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Book' })).toBeDisabled();
    const av = calls.find(c => c.path.endsWith('/availability'))!;
    expect(av.query.get('check_in')).toBe('2030-02-01');
    expect(av.query.get('check_out')).toBe('2030-02-03');
  });

  it('rejects check-out on or before check-in without calling the API', async () => {
    const calls = mockApi({ 'GET /hotels/amber-haveli': hotel() });
    renderRoute(<HotelDetail />, { path: '/h/:ref', route: '/h/amber-haveli' });
    await screen.findByText('Amber Haveli');
    fireEvent.change(screen.getByLabelText('Check-in'), { target: { value: '2030-02-03' } });
    fireEvent.change(screen.getByLabelText('Check-out'), { target: { value: '2030-02-01' } });
    await userEvent.setup().click(screen.getByRole('button', { name: 'Check availability' }));
    expect(await screen.findByRole('alert')).toBeInTheDocument();
    expect(calls.some(c => c.path.endsWith('/availability'))).toBe(false);
  });

  it('shows not-found', async () => {
    mockApi({ 'GET /hotels/nope': () => apiError(404, 'not_found', 'Hotel not found') });
    renderRoute(<HotelDetail />, { path: '/h/:ref', route: '/h/nope' });
    expect(await screen.findByText(/not found|couldn't/i)).toBeInTheDocument();
  });
});

describe('Admin hotels', () => {
  it('lists hotels with status and deletes after confirmation', async () => {
    const user = userEvent.setup();
    const calls = mockApi({
      'GET /admin/hotels': () => page([hotel(), hotel({ id: 'h2', slug: 'x', name: 'Draft Inn', is_published: false })]),
      'GET /destinations': () => page([makeDest()]),
      'DELETE /admin/hotels/h2': () => new Response(null, { status: 204 }),
    });
    renderRoute(<ManageHotels />);
    expect(await screen.findByText('Draft Inn')).toBeInTheDocument();
    expect(screen.getByText('Draft')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Delete Draft Inn' }));
    const buttons = await screen.findAllByRole('button', { name: /Delete/ });
    await user.click(buttons[buttons.length - 1]);
    await waitFor(() => expect(calls.some(c => c.method === 'DELETE' && c.path === '/admin/hotels/h2')).toBe(true));
  });

  it('validates the hotel form before sending', async () => {
    const user = userEvent.setup();
    const calls = mockApi({ 'GET /admin/hotels': () => page([]), 'GET /destinations': () => page([makeDest()]) });
    renderRoute(<ManageHotels />);
    await screen.findByText('No hotels yet');
    await user.click(screen.getByRole('button', { name: /Add hotel/ }));
    await user.type(screen.getByLabelText('Name'), 'Test Inn');
    await user.type(screen.getByLabelText('Latitude'), '95');
    await user.type(screen.getByLabelText('Longitude'), '75');
    await user.click(screen.getByRole('button', { name: 'Create' }));
    expect(await screen.findByText(/Latitude must be between -90 and 90/)).toBeInTheDocument();
    expect(calls.some(c => c.method === 'POST')).toBe(false);
  });
});
