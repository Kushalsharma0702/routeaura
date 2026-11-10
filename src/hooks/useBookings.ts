import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { bookingsApi, type BookingRequest, type HotelInput, type RoomInput } from '@/lib/api/bookings';

export const useHotels = (p: { q?: string; destination?: string; min_stars?: number; sort?: string; page?: number; page_size?: number }) =>
  useQuery({ queryKey: ['hotels', p], queryFn: () => bookingsApi.hotels(p), placeholderData: keepPreviousData });
export const useHotel = (ref: string | undefined) => useQuery({ queryKey: ['hotel', ref], queryFn: () => bookingsApi.hotel(ref!), enabled: !!ref, retry: false });
export const useAvailability = (ref: string | undefined, p: { check_in: string; check_out: string; guests: number; rooms: number } | null) =>
  useQuery({ queryKey: ['availability', ref, p], queryFn: () => bookingsApi.availability(ref!, p!), enabled: !!ref && !!p, retry: false });
export const useMyBookings = (status: string | undefined, page: number) =>
  useQuery({ queryKey: ['bookings', status, page], queryFn: () => bookingsApi.list({ status, page, page_size: 10 }), placeholderData: keepPreviousData });

const invalidate = (qc: ReturnType<typeof useQueryClient>) => {
  for (const k of ['bookings', 'availability', 'notifications', 'unread', 'admin-bookings', 'admin-analytics', 'hotel', 'admin-hotels']) qc.invalidateQueries({ queryKey: [k] });
};
export const useCreateBooking = () => {
  const qc = useQueryClient();
  return useMutation({ mutationFn: (v: { body: BookingRequest; key: string }) => bookingsApi.create(v.body, v.key), onSuccess: () => invalidate(qc) });
};
export const usePay = () => {
  const qc = useQueryClient();
  return useMutation({ mutationFn: (v: { id: string; method: string; key: string }) => bookingsApi.pay(v.id, v.method, v.key), onSuccess: () => invalidate(qc), onError: () => invalidate(qc) });
};
export const useCancelBooking = () => {
  const qc = useQueryClient();
  return useMutation({ mutationFn: (v: { id: string; reason?: string; admin?: boolean }) => (v.admin ? bookingsApi.admin.cancel(v.id, v.reason) : bookingsApi.cancel(v.id, v.reason)), onSuccess: () => invalidate(qc) });
};
export const useRetryRefund = () => {
  const qc = useQueryClient();
  return useMutation({ mutationFn: (id: string) => bookingsApi.admin.retryRefund(id), onSuccess: () => invalidate(qc) });
};

export const useAdminHotels = (p: { q?: string; page?: number }) => useQuery({ queryKey: ['admin-hotels', p], queryFn: () => bookingsApi.admin.hotels({ ...p, page_size: 10 }), placeholderData: keepPreviousData });
export const useAdminBookings = (p: { status?: string; q?: string; page?: number }) => useQuery({ queryKey: ['admin-bookings', p], queryFn: () => bookingsApi.admin.bookings({ ...p, page_size: 10 }), placeholderData: keepPreviousData });
export const useAnalytics = () => useQuery({ queryKey: ['admin-analytics'], queryFn: bookingsApi.admin.analytics });
export const useSaveHotel = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (v: { id?: string; data: HotelInput }) => (v.id ? bookingsApi.admin.updateHotel(v.id, v.data) : bookingsApi.admin.createHotel(v.data)),
    onSuccess: () => invalidate(qc),
  });
};
export const useDeleteHotel = () => {
  const qc = useQueryClient();
  return useMutation({ mutationFn: (id: string) => bookingsApi.admin.deleteHotel(id), onSuccess: () => invalidate(qc) });
};
export const useSaveRoom = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (v: { hotelId: string; id?: string; data: RoomInput }) => (v.id ? bookingsApi.admin.updateRoom(v.id, v.data) : bookingsApi.admin.createRoom(v.hotelId, v.data)),
    onSuccess: () => invalidate(qc),
  });
};
export const useInventory = () => {
  const qc = useQueryClient();
  return useMutation({ mutationFn: (v: { id: string; start: string; end: string; total: number }) => bookingsApi.admin.inventory(v.id, { start: v.start, end: v.end, total: v.total }), onSuccess: () => invalidate(qc) });
};
