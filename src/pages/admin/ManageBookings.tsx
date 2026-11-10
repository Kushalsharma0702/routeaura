import { useEffect, useState } from 'react';
import { Search } from 'lucide-react';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import ConfirmDialog from '@/components/admin/ConfirmDialog';
import BookingBadge from '@/components/booking/BookingBadge';
import { EmptyState, ErrorState, Pager } from '@/components/QueryState';
import { Skeleton } from '@/components/ui/skeleton';
import { ApiError } from '@/lib/api/client';
import type { Booking } from '@/lib/api/bookings';
import { formatMinor } from '@/lib/format';
import { useAdminBookings, useCancelBooking, useRetryRefund } from '@/hooks/useBookings';
import { useDebounced } from '@/hooks/useDebounced';

const ALL = 'all';

export default function ManageBookings() {
  const [status, setStatus] = useState(ALL);
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);
  const q = useDebounced(search.trim());
  useEffect(() => setPage(1), [status, q]);
  const { data, isLoading, isError, refetch } = useAdminBookings({ status: status === ALL ? undefined : status, q: q || undefined, page });
  const cancel = useCancelBooking();
  const retry = useRetryRefund();
  const [toCancel, setToCancel] = useState<Booking | null>(null);
  const err = (e: unknown) => toast.error(e instanceof ApiError ? e.message : 'Something went wrong');

  return (
    <div className="space-y-6 pb-24 lg:pb-0">
      <div><h1 className="text-2xl font-display font-bold text-foreground">Bookings</h1><p className="text-sm text-muted-foreground mt-1">{data ? `${data.total} booking${data.total === 1 ? '' : 's'}` : 'Loading…'}</p></div>
      <div className="flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1 max-w-sm"><Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" /><Input aria-label="Search bookings" placeholder="Reference or guest name…" value={search} className="pl-9" onChange={e => setSearch(e.target.value)} /></div>
        <Select value={status} onValueChange={setStatus}><SelectTrigger className="w-full sm:w-52" aria-label="Status"><SelectValue /></SelectTrigger>
          <SelectContent><SelectItem value={ALL}>All statuses</SelectItem><SelectItem value="confirmed">Confirmed</SelectItem><SelectItem value="pending_payment">Awaiting payment</SelectItem><SelectItem value="cancelled">Cancelled</SelectItem><SelectItem value="expired">Expired</SelectItem></SelectContent></Select>
      </div>
      {isLoading && <div className="space-y-2" role="status" aria-label="Loading">{[0, 1, 2].map(i => <Skeleton key={i} className="h-14 rounded-lg" />)}</div>}
      {isError && <ErrorState message="We couldn't load bookings." onRetry={() => refetch()} />}
      {data?.items.length === 0 && <EmptyState title="No bookings found" hint={q || status !== ALL ? 'Try another filter.' : 'Bookings appear here as travelers book.'} />}
      {data && data.items.length > 0 && (
        <div className="bg-card rounded-xl border border-border/50 shadow-card overflow-x-auto">
          <table className="w-full text-sm">
            <thead><tr className="text-left text-xs text-muted-foreground border-b border-border/50"><th className="px-4 py-3">Reference</th><th className="px-4 py-3">Guest</th><th className="px-4 py-3">Hotel</th><th className="px-4 py-3">Dates</th><th className="px-4 py-3">Total</th><th className="px-4 py-3">Status</th><th className="px-4 py-3">Actions</th></tr></thead>
            <tbody>
              {data.items.map(b => (
                <tr key={b.id} className="border-b border-border/30 last:border-0">
                  <td className="px-4 py-3 font-medium">{b.reference}</td>
                  <td className="px-4 py-3">{b.guest_name}<span className="block text-xs text-muted-foreground">{b.user_email}</span></td>
                  <td className="px-4 py-3">{b.hotel_name}<span className="block text-xs text-muted-foreground">{b.room_type_name}</span></td>
                  <td className="px-4 py-3 whitespace-nowrap">{b.check_in} → {b.check_out}</td>
                  <td className="px-4 py-3">{formatMinor(b.total_minor, b.currency)}<span className="block text-xs text-muted-foreground capitalize">{b.payment_status.replace('_', ' ')}</span></td>
                  <td className="px-4 py-3"><BookingBadge status={b.status} /></td>
                  <td className="px-4 py-3"><div className="flex gap-2">
                    {(b.status === 'confirmed' || b.status === 'pending_payment') && <Button size="sm" variant="outline" onClick={() => setToCancel(b)}>Cancel</Button>}
                    {b.payment_status === 'refund_pending' && <Button size="sm" variant="outline" disabled={retry.isPending} onClick={() => retry.mutate(b.id, { onSuccess: () => toast.success('Refund processed'), onError: err })}>Retry refund</Button>}
                  </div></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {data && <Pager page={page} pageSize={data.page_size} total={data.total} onPage={setPage} />}
      <ConfirmDialog open={!!toCancel} onOpenChange={o => !o && setToCancel(null)} title={`Cancel booking ${toCancel?.reference}?`} confirmLabel="Cancel booking"
        description="Admin cancellations release the rooms and refund the traveler in full. The traveler is notified."
        onConfirm={() => toCancel && cancel.mutate({ id: toCancel.id, admin: true, reason: 'Cancelled by an administrator' }, { onSuccess: () => { toast.success('Booking cancelled'); setToCancel(null); }, onError: err })} />
    </div>
  );
}
