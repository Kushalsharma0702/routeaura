/**
 * Client dashboard: live counts and upcoming items from the API (bookings, itineraries, notifications),
 * plus personalised recommendations. No mock data.
 */
import { Link } from 'react-router-dom';
import { Bell, CalendarDays, Hotel, Map as MapIcon, Plane } from 'lucide-react';
import { motion } from 'framer-motion';
import StatCard from '@/components/StatCard';
import BookingBadge from '@/components/booking/BookingBadge';
import RecommendationsSection from '@/components/recommendations/RecommendationsSection';
import { ErrorState } from '@/components/QueryState';
import { Skeleton } from '@/components/ui/skeleton';
import { useAuth } from '@/contexts/AuthContext';
import { formatMinor } from '@/lib/format';
import { useMyBookings } from '@/hooks/useBookings';
import { useItineraries } from '@/hooks/useItineraries';
import { useUnreadCount } from '@/hooks/useNotifications';

export default function ClientDashboard() {
  const { user } = useAuth();
  const all = useMyBookings(undefined, 1);
  const confirmed = useMyBookings('confirmed', 1);
  const trips = useItineraries(1);
  const unread = useUnreadCount();
  const today = new Date().toISOString().slice(0, 10);
  const upcoming = (confirmed.data?.items ?? []).filter(b => b.check_out >= today).sort((a, b) => a.check_in.localeCompare(b.check_in));
  const loading = all.isLoading || trips.isLoading;

  return (
    <div className="space-y-8 pb-24 lg:pb-0">
      <div>
        <h1 className="text-2xl font-display font-bold text-foreground">Welcome back, {user?.name?.split(' ')[0]}!</h1>
        <p className="text-muted-foreground text-sm mt-1">Here's your travel overview</p>
      </div>

      {(all.isError || trips.isError) && <ErrorState message="We couldn't load all of your overview." onRetry={() => { void all.refetch(); void trips.refetch(); }} />}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4">
        <StatCard title="Bookings" value={loading ? '…' : all.data?.total ?? 0} icon={Hotel} variant="primary" />
        <StatCard title="Upcoming stays" value={confirmed.isLoading ? '…' : upcoming.length} icon={CalendarDays} variant="accent" />
        <StatCard title="Trips planned" value={loading ? '…' : trips.data?.total ?? 0} icon={MapIcon} variant="success" />
        <StatCard title="Unread alerts" value={unread.data?.unread ?? 0} icon={Bell} variant="warning" />
      </div>

      <RecommendationsSection />

      <section aria-labelledby="up-h" className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 id="up-h" className="text-lg font-display font-semibold text-foreground">Upcoming stays</h2>
          <Link to="/dashboard/bookings" className="text-sm text-primary hover:underline">All bookings</Link>
        </div>
        {confirmed.isLoading && <Skeleton className="h-24 rounded-xl" />}
        {!confirmed.isLoading && upcoming.length === 0 && (
          <p className="text-sm text-muted-foreground">No confirmed stays yet. <Link to="/dashboard/hotels" className="text-primary hover:underline">Find a hotel</Link> or <Link to="/dashboard/planner" className="text-primary hover:underline">plan a trip</Link>.</p>
        )}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {upcoming.slice(0, 4).map((b, i) => (
            <motion.div key={b.id} initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.05 }} className="bg-card rounded-xl border border-border/50 shadow-card p-4 space-y-1">
              <div className="flex items-start justify-between gap-2"><p className="font-semibold text-card-foreground">{b.hotel_name}</p><BookingBadge status={b.status} /></div>
              <p className="text-xs text-muted-foreground">{b.destination_name} · {b.check_in} → {b.check_out}</p>
              <p className="text-sm font-display font-bold text-primary">{formatMinor(b.total_minor, b.currency)}</p>
            </motion.div>
          ))}
        </div>
      </section>

      <section aria-labelledby="tr-h" className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 id="tr-h" className="text-lg font-display font-semibold text-foreground flex items-center gap-2"><Plane className="w-5 h-5 text-primary" />Your trips</h2>
          <Link to="/dashboard/itineraries" className="text-sm text-primary hover:underline">All trips</Link>
        </div>
        {trips.data?.items.length === 0 && <p className="text-sm text-muted-foreground">No trips yet. <Link to="/dashboard/planner" className="text-primary hover:underline">Plan your first trip</Link>.</p>}
        <ul className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {trips.data?.items.slice(0, 4).map(t => (
            <li key={t.id} className="bg-card rounded-xl border border-border/50 shadow-card p-4">
              <Link to={`/dashboard/itineraries/${t.id}`} className="font-semibold text-card-foreground hover:underline">{t.title}</Link>
              <p className="text-xs text-muted-foreground">{t.destination_name} · {t.days} days · {t.activity_count} activities{t.start_date ? ` · from ${t.start_date}` : ''}</p>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
