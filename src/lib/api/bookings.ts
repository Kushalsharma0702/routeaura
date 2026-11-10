import { apiFetch } from './client';
import type { Page } from './users';

export interface RoomType { id: string; hotel_id: string; name: string; description: string; capacity: number; price_per_night_minor: number; currency: string; total_rooms: number; amenities: string[]; is_active: boolean }
export interface Hotel {
  id: string; slug: string; name: string; description: string; address: string | null; latitude: number; longitude: number; star_rating: number | null;
  amenities: string[]; images: string[]; is_published: boolean; source: string; destination_id: string; destination_name: string;
  room_types: RoomType[]; from_price_minor: number | null; currency: string;
}
export interface RoomAvailability { room_type: RoomType; nights: number; available_rooms: number; price_per_night_minor: number; total_minor: number; can_book: boolean; reason: string | null }
export interface Availability { hotel_id: string; check_in: string; check_out: string; guests: number; rooms: number; options: RoomAvailability[] }
export interface Payment { id: string; kind: 'charge' | 'refund'; provider: string; amount_minor: number; currency: string; status: string; failure_reason: string | null; simulated: boolean; created_at: string }
export type BookingStatus = 'pending_payment' | 'confirmed' | 'cancelled' | 'expired' | 'failed';
export interface Booking {
  id: string; reference: string; status: BookingStatus; payment_status: string; hotel_id: string; hotel_name: string; hotel_slug: string; destination_name: string;
  room_type_id: string; room_type_name: string; check_in: string; check_out: string; nights: number; rooms: number; guests: number; guest_name: string;
  guest_phone: string | null; total_minor: number; currency: string; hold_expires_at: string | null; confirmed_at: string | null; cancelled_at: string | null;
  cancelled_by: string | null; cancel_reason: string | null; refund_amount_minor: number | null; itinerary_id: string | null; created_at: string; payments: Payment[];
  refund_if_cancelled_now_minor: number | null; cancellation_policy: string; payment_note: string | null; user_email?: string | null;
}
export interface BookingRequest { room_type_id: string; check_in: string; check_out: string; rooms: number; guests: number; guest_name: string; guest_phone?: string; itinerary_id?: string }
export interface Analytics {
  bookings_by_status: Record<string, number>; confirmed_revenue_minor: number; refunded_minor: number;
  monthly: { month: string; bookings: number; revenue_minor: number }[]; top_destinations: { destination: string; bookings: number }[];
  future_occupancy_pct: number | null; users: number; itineraries: number; hotels: number; currency: string; notes: string[];
}
export interface HotelInput { destination_id: string; name: string; description?: string; address?: string | null; latitude: number; longitude: number; star_rating?: number | null; amenities?: string[]; images?: string[]; is_published?: boolean }
export interface RoomInput { name: string; description?: string; capacity: number; price_per_night_minor: number; total_rooms: number; amenities?: string[]; is_active?: boolean }

const idem = (key: string) => ({ 'Idempotency-Key': key });
export const bookingsApi = {
  hotels: (p: { q?: string; destination?: string; min_stars?: number; sort?: string; page?: number; page_size?: number }) => apiFetch<Page<Hotel>>('/hotels', { params: { ...p } }),
  hotel: (ref: string) => apiFetch<Hotel>(`/hotels/${encodeURIComponent(ref)}`),
  availability: (ref: string, p: { check_in: string; check_out: string; guests: number; rooms: number }) => apiFetch<Availability>(`/hotels/${encodeURIComponent(ref)}/availability`, { params: { ...p } }),
  create: (body: BookingRequest, key: string) => apiFetch<Booking>('/bookings', { method: 'POST', body, headers: idem(key) }),
  pay: (id: string, method: string, key: string) => apiFetch<Booking>(`/bookings/${id}/pay`, { method: 'POST', body: { payment_method: method }, headers: idem(key) }),
  cancel: (id: string, reason?: string) => apiFetch<Booking>(`/bookings/${id}/cancel`, { method: 'POST', body: { reason } }),
  list: (p: { status?: string; page?: number; page_size?: number }) => apiFetch<Page<Booking>>('/bookings', { params: { ...p } }),
  admin: {
    hotels: (p: { q?: string; page?: number; page_size?: number }) => apiFetch<Page<Hotel>>('/admin/hotels', { params: { ...p } }),
    createHotel: (b: HotelInput) => apiFetch<Hotel>('/admin/hotels', { method: 'POST', body: b }),
    updateHotel: (id: string, b: Partial<HotelInput>) => apiFetch<Hotel>(`/admin/hotels/${id}`, { method: 'PATCH', body: b }),
    deleteHotel: (id: string) => apiFetch<void>(`/admin/hotels/${id}`, { method: 'DELETE' }),
    createRoom: (hotelId: string, b: RoomInput) => apiFetch<RoomType>(`/admin/hotels/${hotelId}/rooms`, { method: 'POST', body: b }),
    updateRoom: (id: string, b: Partial<RoomInput>) => apiFetch<RoomType>(`/admin/rooms/${id}`, { method: 'PATCH', body: b }),
    inventory: (id: string, b: { start: string; end: string; total: number }) => apiFetch<{ nights: number; total: number }>(`/admin/rooms/${id}/inventory`, { method: 'PUT', body: b }),
    bookings: (p: { status?: string; q?: string; page?: number; page_size?: number }) => apiFetch<Page<Booking>>('/admin/bookings', { params: { ...p } }),
    cancel: (id: string, reason?: string) => apiFetch<Booking>(`/admin/bookings/${id}/cancel`, { method: 'POST', body: { reason } }),
    retryRefund: (id: string) => apiFetch<Booking>(`/admin/bookings/${id}/retry-refund`, { method: 'POST' }),
    analytics: () => apiFetch<Analytics>('/admin/analytics'),
  },
};
