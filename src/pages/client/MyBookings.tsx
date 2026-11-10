import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { CalendarDays, Hotel as HotelIcon, Users } from 'lucide-react';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import ConfirmDialog from '@/components/admin/ConfirmDialog';
import BookingBadge from '@/components/booking/BookingBadge';
import PaymentDialog from '@/components/booking/PaymentDialog';
import { EmptyState, ErrorState, GridSkeleton, Pager } from '@/components/QueryState';
import { ApiError } from '@/lib/api/client';
import type { Booking } from '@/lib/api/bookings';
import { formatMinor } from '@/lib/format';
import { useCancelBooking, useMyBookings } from '@/hooks/useBookings';

const ALL = 'all';
const time = (iso: string) => new Date(iso).toLocaleString(undefined, { hour: '2-digit', minute: '2-digit', day: 'numeric', month: 'short' });

function BookingCard({ b, onPay, onCancel }: { b: Booking; onPay: () => void; onCancel: () => void }) {
  const open = b.status === 'pending_payment' || b.status === 'confirmed';
  return (
    <article aria-label={`Booking ${b.reference}`} className="bg-card rounded-xl border border-border/50 shadow-card p-5 space-y-3">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div><p className="text-xs text-muted-foreground">Reference {b.reference}</p>
          <Link to={`/dashboard/hotels/${b.hotel_slug}`} className="font-display font-semibold text-card-foreground hover:underline flex items-center gap-1.5"><HotelIcon className="w-4 h-4" />{b.hotel_name}</Link>
          <p className="text-sm text-muted-foreground">{b.destination_name} · {b.room_type_name}</p></div>
        <BookingBadge status={b.status} />
      </div>
      <div className="flex flex-wrap gap-x-5 gap-y-1 text-sm text-muted-foreground">
        <span className="flex items-center gap-1.5"><CalendarDays className="w-4 h-4" />{b.check_in} → {b.check_out} ({b.nights} night{b.nights === 1 ? '' : 's'})</span>
        <span className="flex items-center gap-1.5"><Users className="w-4 h-4" />{b.guests} guest{b.guests === 1 ? '' : 's'}, {b.rooms} room{b.rooms === 1 ? '' : 's'}</span>
        <span className="font-semibold text-foreground">{formatMinor(b.total_minor, b.currency)}</span>
      </div>
      {b.status === 'pending_payment' && b.hold_expires_at && <p className="text-xs text-warning">Rooms are held until {time(b.hold_expires_at)}. Pay before then to confirm.</p>}
      {b.status === 'cancelled' && <p className="text-xs text-muted-foreground">Cancelled{b.cancelled_by ? ` by ${b.cancelled_by}` : ''}. {b.refund_amount_minor != null && (b.refund_amount_minor > 0 ? `Refund: ${formatMinor(b.refund_amount_minor, b.currency)} (${b.payment_status.replace('_', ' ')}).` : 'No refund was due.')}</p>}
      {b.status === 'expired' && <p className="text-xs text-muted-foreground">The hold expired and the rooms were released.</p>}
      {b.payments.length > 0 && (
        <ul className="text-xs text-muted-foreground space-y-0.5" aria-label="Payments">{b.payments.map(p => <li key={p.id}>{p.kind === 'charge' ? 'Payment' : 'Refund'} {formatMinor(p.amount_minor, p.currency)} · {p.status}{p.failure_reason ? ` (${p.failure_reason})` : ''}{p.simulated ? ' · simulated' : ''}</li>)}</ul>
      )}
      {b.payment_note && <p className="text-[11px] text-muted-foreground">{b.payment_note}</p>}
      {open && (
        <div className="flex flex-wrap gap-2 pt-1">
          {b.status === 'pending_payment' && <Button size="sm" className="gradient-primary text-primary-foreground" onClick={onPay}>Pay now</Button>}
          <Button size="sm" variant="outline" onClick={onCancel}>Cancel booking</Button>
        </div>
      )}
    </article>
  );
}

export default function MyBookings() {
  const [status, setStatus] = useState(ALL);
  const [page, setPage] = useState(1);
  useEffect(() => setPage(1), [status]);
  const { data, isLoading, isError, refetch } = useMyBookings(status === ALL ? undefined : status, page);
  const cancel = useCancelBooking();
  const [paying, setPaying] = useState<Booking | null>(null);
  const [cancelling, setCancelling] = useState<Booking | null>(null);

  const refundText = (b: Booking) => b.status === 'pending_payment' ? 'The held rooms will be released. You have not been charged.'
    : `${b.cancellation_policy} If you cancel now your refund is ${formatMinor(b.refund_if_cancelled_now_minor ?? 0, b.currency)}.`;

  return (
    <div className="space-y-6 pb-24 lg:pb-0">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div><h1 className="text-2xl font-display font-bold text-foreground">My Bookings</h1><p className="text-sm text-muted-foreground mt-1">{data ? `${data.total} booking${data.total === 1 ? '' : 's'}` : 'Loading…'}</p></div>
        <div className="flex items-center gap-3">
          <Select value={status} onValueChange={setStatus}><SelectTrigger className="w-48" aria-label="Filter by status"><SelectValue /></SelectTrigger>
            <SelectContent><SelectItem value={ALL}>All bookings</SelectItem><SelectItem value="confirmed">Confirmed</SelectItem><SelectItem value="pending_payment">Awaiting payment</SelectItem><SelectItem value="cancelled">Cancelled</SelectItem><SelectItem value="expired">Expired</SelectItem></SelectContent></Select>
          <Button asChild className="gradient-primary text-primary-foreground"><Link to="/dashboard/hotels">Find a hotel</Link></Button>
        </div>
      </div>
      {isLoading && <GridSkeleton count={3} height="h-48" />}
      {isError && <ErrorState message="We couldn't load your bookings." onRetry={() => refetch()} />}
      {data?.items.length === 0 && <EmptyState title={status === ALL ? 'No bookings yet' : 'No bookings with this status'} hint="Book a hotel and it will appear here." />}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        {data?.items.map(b => <BookingCard key={b.id} b={b} onPay={() => setPaying(b)} onCancel={() => setCancelling(b)} />)}
      </div>
      {data && <Pager page={page} pageSize={data.page_size} total={data.total} onPage={setPage} />}
      <PaymentDialog booking={paying} open={!!paying} onOpenChange={o => !o && setPaying(null)} />
      <ConfirmDialog open={!!cancelling} onOpenChange={o => !o && setCancelling(null)} title={`Cancel booking ${cancelling?.reference}?`} confirmLabel="Cancel booking"
        description={cancelling ? refundText(cancelling) : ''}
        onConfirm={() => cancelling && cancel.mutate({ id: cancelling.id }, {
          onSuccess: () => { toast.success('Booking cancelled'); setCancelling(null); },
          onError: e => toast.error(e instanceof ApiError ? e.message : 'Could not cancel the booking'),
        })} />
    </div>
  );
}
