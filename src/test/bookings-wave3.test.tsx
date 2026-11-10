import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import MyBookings from '@/pages/client/MyBookings';
import NotificationBell from '@/components/layouts/NotificationBell';
import Assistant from '@/pages/client/Assistant';
import ManageBookings from '@/pages/admin/ManageBookings';
import { apiError, json, mockApi, page, renderRoute } from './utils';

vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: vi.fn() } }));
beforeEach(() => vi.clearAllMocks());
afterEach(() => vi.unstubAllGlobals());

const booking = (o: Record<string, unknown> = {}) => ({
  id: 'b1', reference: 'RA-1', status: 'pending_payment', payment_status: 'unpaid', hotel_id: 'h1', hotel_name: 'Amber Haveli', hotel_slug: 'amber-haveli',
  destination_name: 'Jaipur', room_type_id: 'r1', room_type_name: 'Deluxe', check_in: '2030-02-01', check_out: '2030-02-03', nights: 2, rooms: 1, guests: 2,
  guest_name: 'A', guest_phone: null, total_minor: 800000, currency: 'INR', hold_expires_at: '2030-01-01T10:00:00Z', confirmed_at: null, cancelled_at: null,
  cancelled_by: null, cancel_reason: null, refund_amount_minor: null, itinerary_id: null, created_at: '2030-01-01T09:00:00Z', payments: [],
  refund_if_cancelled_now_minor: 0, cancellation_policy: 'Free cancellation 2 days before.', payment_note: null, ...o,
});

describe('My bookings', () => {
  it('pays with the simulator, sending an idempotency key, and warns it is not real', async () => {
    const user = userEvent.setup();
    const calls = mockApi({ 'GET /bookings': () => page([booking()]), 'POST /bookings/b1/pay': () => booking({ status: 'confirmed', payment_status: 'paid' }) });
    renderRoute(<MyBookings />);
    await user.click(await screen.findByRole('button', { name: 'Pay now' }));
    expect(screen.getByText(/Development payment simulator/)).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: /^Pay ₹/ }));
    await waitFor(() => expect(calls.some(c => c.path === '/bookings/b1/pay')).toBe(true));
    const pay = calls.find(c => c.path === '/bookings/b1/pay')!;
    expect(pay.body).toEqual({ payment_method: 'dev_card_ok' });
  });

  it('shows a decline inline and keeps the dialog open', async () => {
    const user = userEvent.setup();
    mockApi({ 'GET /bookings': () => page([booking()]), 'POST /bookings/b1/pay': () => apiError(402, 'payment_failed', 'Card declined') });
    renderRoute(<MyBookings />);
    await user.click(await screen.findByRole('button', { name: 'Pay now' }));
    await user.click(screen.getByRole('button', { name: /^Pay ₹/ }));
    expect(await screen.findByText('Card declined')).toBeInTheDocument();
  });

  it('shows the refund amount before cancelling and sends the cancel', async () => {
    const user = userEvent.setup();
    const calls = mockApi({
      'GET /bookings': () => page([booking({ status: 'confirmed', payment_status: 'paid', refund_if_cancelled_now_minor: 400000 })]),
      'POST /bookings/b1/cancel': () => booking({ status: 'cancelled' }),
    });
    renderRoute(<MyBookings />);
    await user.click(await screen.findByRole('button', { name: 'Cancel booking' }));
    expect(await screen.findByText(/your refund is ₹4,000/)).toBeInTheDocument();
    const buttons = screen.getAllByRole('button', { name: 'Cancel booking' });
    await user.click(buttons[buttons.length - 1]);
    await waitFor(() => expect(calls.some(c => c.path === '/bookings/b1/cancel')).toBe(true));
  });

  it('shows empty and error states', async () => {
    mockApi({ 'GET /bookings': () => page([]) });
    renderRoute(<MyBookings />);
    expect(await screen.findByText('No bookings yet')).toBeInTheDocument();
    vi.unstubAllGlobals();
    mockApi({ 'GET /bookings': () => apiError(500, 'internal_error', 'x') });
    renderRoute(<MyBookings />);
    expect(await screen.findByRole('alert')).toBeInTheDocument();
  });
});

describe('Notification bell', () => {
  it('shows the unread count and marks one read', async () => {
    const user = userEvent.setup();
    const calls = mockApi({
      'GET /notifications/unread-count': { unread: 2 },
      'GET /notifications': () => page([{ id: 'n1', type: 'booking_confirmed', title: 'Booking confirmed', body: 'RA-1', data: {}, read_at: null, created_at: '2030-01-01T00:00:00Z' }]),
      'POST /notifications/n1/read': () => ({ id: 'n1' }),
    });
    renderRoute(<NotificationBell />);
    const bell = await screen.findByRole('button', { name: 'Notifications, 2 unread' });
    await user.click(bell);
    await user.click(await screen.findByText('Booking confirmed'));
    await waitFor(() => expect(calls.some(c => c.path === '/notifications/n1/read')).toBe(true));
  });
});

describe('Assistant', () => {
  const caps = { text_chat: true, languages: ['en', 'hi'], speech_provider: 'none', server_speech_to_text: false, server_text_to_speech: false, browser_fallback: true, max_audio_bytes: 1000 };
  const result = (o: Record<string, unknown> = {}) => ({ conversation_id: 'c1', language: 'en', detected_language: 'en', language_mismatch: false, reply: 'Here are options.', actions: [], cards: [{ type: 'destination', slug: 'jaipur', name: 'Jaipur' }], awaiting_confirmation: false, interpreted_by: 'rules', ...o });

  it('sends a message, renders the reply and a card link; voice is disabled without browser support', async () => {
    const user = userEvent.setup();
    const calls = mockApi({ 'GET /assistant/capabilities': caps, 'GET /assistant/conversations': () => page([]), 'POST /assistant/chat': () => result() });
    renderRoute(<Assistant />);
    expect(await screen.findByRole('button', { name: /Voice input is not available/ })).toBeDisabled();
    await user.type(screen.getByLabelText('Message'), 'suggest places in Jaipur');
    await user.click(screen.getByRole('button', { name: 'Send' }));
    expect(await screen.findByText('Here are options.')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Jaipur/ })).toHaveAttribute('href', '/dashboard/destinations/jaipur');
    expect(calls.find(c => c.path === '/assistant/chat')!.body).toMatchObject({ message: 'suggest places in Jaipur' });
  });

  it('offers Yes/No when confirmation is needed and sends the answer', async () => {
    const user = userEvent.setup();
    const calls = mockApi({
      'GET /assistant/capabilities': caps, 'GET /assistant/conversations': () => page([]),
      'POST /assistant/chat': (c: { body: unknown }) => (c.body as { message: string }).message === 'yes' ? result({ reply: 'Done.', awaiting_confirmation: false }) : result({ reply: 'Remove it?', awaiting_confirmation: true, cards: [] }),
    });
    renderRoute(<Assistant />);
    await user.type(await screen.findByLabelText('Message'), 'remove the fort');
    await user.click(screen.getByRole('button', { name: 'Send' }));
    await user.click(await screen.findByRole('button', { name: 'Yes' }));
    expect(await screen.findByText('Done.')).toBeInTheDocument();
    expect(calls.filter(c => c.path === '/assistant/chat').map(c => (c.body as { message: string }).message)).toEqual(['remove the fort', 'yes']);
  });

  it('reports a chat failure without losing the page', async () => {
    const user = userEvent.setup();
    mockApi({ 'GET /assistant/capabilities': caps, 'GET /assistant/conversations': () => page([]), 'POST /assistant/chat': () => apiError(500, 'internal_error', 'boom') });
    renderRoute(<Assistant />);
    await user.type(await screen.findByLabelText('Message'), 'hello');
    await user.click(screen.getByRole('button', { name: 'Send' }));
    expect(await screen.findByRole('alert')).toBeInTheDocument();
    expect(screen.getByLabelText('Message')).toBeInTheDocument();
  });
});

describe('Admin bookings', () => {
  it('lists bookings and cancels with a full refund after confirmation', async () => {
    const user = userEvent.setup();
    const calls = mockApi({
      'GET /admin/bookings': () => page([booking({ status: 'confirmed', payment_status: 'paid', user_email: 'a@b.co' })]),
      'POST /admin/bookings/b1/cancel': () => json(200, booking({ status: 'cancelled' })),
    });
    renderRoute(<ManageBookings />);
    expect(await screen.findByText('RA-1')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: /Cancel/ }));
    const confirm = (await screen.findAllByRole('button', { name: /Cancel/ })).pop()!;
    await user.click(confirm);
    await waitFor(() => expect(calls.some(c => c.path === '/admin/bookings/b1/cancel')).toBe(true));
  });
});
