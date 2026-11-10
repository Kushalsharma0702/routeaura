import { cn } from '@/lib/utils';
import type { BookingStatus } from '@/lib/api/bookings';

const STYLE: Record<BookingStatus, string> = {
  confirmed: 'bg-success/15 text-success border-success/20', pending_payment: 'bg-warning/15 text-warning border-warning/20',
  cancelled: 'bg-muted text-muted-foreground border-border', expired: 'bg-muted text-muted-foreground border-border', failed: 'bg-destructive/15 text-destructive border-destructive/20',
};
const LABEL: Record<BookingStatus, string> = { confirmed: 'Confirmed', pending_payment: 'Awaiting payment', cancelled: 'Cancelled', expired: 'Expired', failed: 'Failed' };

export default function BookingBadge({ status }: { status: BookingStatus }) {
  return <span className={cn('inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium border', STYLE[status])}>{LABEL[status]}</span>;
}
