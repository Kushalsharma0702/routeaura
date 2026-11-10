import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { BellRing, CheckCheck } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';
import { EmptyState, ErrorState, Pager } from '@/components/QueryState';
import { Skeleton } from '@/components/ui/skeleton';
import { useMarkAllRead, useMarkRead, useNotifications } from '@/hooks/useNotifications';

const LINKS: Record<string, (d: Record<string, unknown>) => string | null> = {
  booking_confirmed: () => '/dashboard/bookings', booking_cancelled: () => '/dashboard/bookings', booking_refund_failed: () => '/dashboard/bookings',
  trip_reminder: d => (d.itinerary_id ? `/dashboard/itineraries/${d.itinerary_id}` : '/dashboard/bookings'),
  weather_alert: d => (d.itinerary_id ? `/dashboard/itineraries/${d.itinerary_id}` : null),
  adaptation_proposal: d => (d.itinerary_id ? `/dashboard/itineraries/${d.itinerary_id}` : null),
  itinerary_adapted: d => (d.itinerary_id ? `/dashboard/itineraries/${d.itinerary_id}` : null),
};

export default function Notifications() {
  const [unreadOnly, setUnreadOnly] = useState(false);
  const [page, setPage] = useState(1);
  useEffect(() => setPage(1), [unreadOnly]);
  const { data, isLoading, isError, refetch } = useNotifications({ unread: unreadOnly || undefined, page, page_size: 15 });
  const mark = useMarkRead();
  const markAll = useMarkAllRead();
  return (
    <div className="space-y-6 pb-24 lg:pb-0 max-w-3xl">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div><h1 className="text-2xl font-display font-bold text-foreground flex items-center gap-2"><BellRing className="w-6 h-6 text-primary" />Notifications</h1>
          <p className="text-sm text-muted-foreground mt-1">Booking updates, trip reminders and itinerary alerts</p></div>
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2"><Switch id="n-unread" checked={unreadOnly} onCheckedChange={setUnreadOnly} /><Label htmlFor="n-unread" className="text-sm">Unread only</Label></div>
          <Button variant="outline" className="gap-2" disabled={markAll.isPending} onClick={() => markAll.mutate()}><CheckCheck className="w-4 h-4" />Mark all read</Button>
        </div>
      </div>
      {isLoading && <div className="space-y-3" role="status" aria-label="Loading">{[0, 1, 2].map(i => <Skeleton key={i} className="h-20 rounded-xl" />)}</div>}
      {isError && <ErrorState message="We couldn't load your notifications." onRetry={() => refetch()} />}
      {data?.items.length === 0 && <EmptyState title={unreadOnly ? 'No unread notifications' : 'No notifications yet'} hint="Updates about bookings and trips will appear here." />}
      <ul className="space-y-3">
        {data?.items.map(n => {
          const href = LINKS[n.type]?.(n.data) ?? null;
          return (
            <li key={n.id} className={`rounded-xl border p-4 space-y-1 ${n.read_at ? 'border-border/50 bg-card' : 'border-primary/30 bg-primary/5'}`}>
              <div className="flex items-start justify-between gap-3">
                <p className={`text-sm ${n.read_at ? '' : 'font-semibold'}`}>{n.title}</p>
                <time className="text-xs text-muted-foreground shrink-0" dateTime={n.created_at}>{new Date(n.created_at).toLocaleString()}</time>
              </div>
              <p className="text-sm text-muted-foreground">{n.body}</p>
              <div className="flex gap-3 pt-1">
                {href && <Button size="sm" variant="outline" asChild><Link to={href} onClick={() => { if (!n.read_at) mark.mutate(n.id); }}>Open</Link></Button>}
                {!n.read_at && <Button size="sm" variant="ghost" disabled={mark.isPending} onClick={() => mark.mutate(n.id)}>Mark as read</Button>}
              </div>
            </li>
          );
        })}
      </ul>
      {data && <Pager page={page} pageSize={data.page_size} total={data.total} onPage={setPage} />}
    </div>
  );
}
