/** Admin dashboard: every figure is computed by the API from the database. */
import { Bar, BarChart, CartesianGrid, Cell, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { Building2, CalendarCheck, IndianRupee, Map as MapIcon, Users } from 'lucide-react';
import StatCard from '@/components/StatCard';
import { EmptyState, ErrorState } from '@/components/QueryState';
import { Skeleton } from '@/components/ui/skeleton';
import { formatMinor } from '@/lib/format';
import { useAnalytics } from '@/hooks/useBookings';

const COLORS = ['hsl(var(--primary))', 'hsl(var(--accent))', 'hsl(var(--warning))', 'hsl(var(--muted-foreground))', 'hsl(var(--destructive))'];

export default function AdminDashboard() {
  const { data, isLoading, isError, refetch } = useAnalytics();
  if (isLoading) return <div className="space-y-4" role="status" aria-label="Loading"><Skeleton className="h-10 w-64" /><div className="grid grid-cols-2 lg:grid-cols-5 gap-4">{[0, 1, 2, 3, 4].map(i => <Skeleton key={i} className="h-28 rounded-xl" />)}</div></div>;
  if (isError || !data) return <ErrorState message="We couldn't load the analytics." onRetry={() => refetch()} />;
  const totalBookings = Object.values(data.bookings_by_status).reduce((a, b) => a + b, 0);
  const statusData = Object.entries(data.bookings_by_status).map(([name, value]) => ({ name: name.replace('_', ' '), value }));

  return (
    <div className="space-y-8 pb-24 lg:pb-0">
      <div><h1 className="text-2xl font-display font-bold text-foreground">Admin Dashboard</h1><p className="text-muted-foreground text-sm mt-1">Live figures from the database</p></div>
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-3 sm:gap-4">
        <StatCard title="Users" value={data.users} icon={Users} variant="primary" />
        <StatCard title="Hotels" value={data.hotels} icon={Building2} variant="accent" />
        <StatCard title="Bookings" value={totalBookings} icon={CalendarCheck} variant="success" />
        <StatCard title="Confirmed revenue" value={formatMinor(data.confirmed_revenue_minor, data.currency)} icon={IndianRupee} variant="warning" />
        <StatCard title="Trips planned" value={data.itineraries} icon={MapIcon} variant="default" />
      </div>
      <p className="text-xs text-muted-foreground">{data.notes.join(' ')} Refunded so far: {formatMinor(data.refunded_minor, data.currency)}. Future occupancy: {data.future_occupancy_pct == null ? 'no inventory yet' : `${data.future_occupancy_pct}%`}.</p>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <section className="bg-card rounded-xl border border-border/50 shadow-card p-4" aria-label="Bookings per month">
          <h2 className="font-display font-semibold mb-3">Bookings per month</h2>
          {data.monthly.length === 0 ? <EmptyState title="No bookings yet" hint="Charts appear after the first booking." /> : (
            <div style={{ height: 240 }}><ResponsiveContainer><BarChart data={data.monthly}><CartesianGrid strokeDasharray="3 3" /><XAxis dataKey="month" fontSize={12} /><YAxis allowDecimals={false} fontSize={12} /><Tooltip /><Bar dataKey="bookings" fill="hsl(var(--primary))" radius={[4, 4, 0, 0]} /></BarChart></ResponsiveContainer></div>
          )}
        </section>
        <section className="bg-card rounded-xl border border-border/50 shadow-card p-4" aria-label="Bookings by status">
          <h2 className="font-display font-semibold mb-3">Bookings by status</h2>
          {statusData.length === 0 ? <EmptyState title="No bookings yet" /> : (
            <>
              <div style={{ height: 200 }}><ResponsiveContainer><PieChart><Pie data={statusData} dataKey="value" nameKey="name" innerRadius={45} outerRadius={75} paddingAngle={3}>{statusData.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}</Pie><Tooltip /></PieChart></ResponsiveContainer></div>
              <ul className="text-sm space-y-1">{statusData.map(s => <li key={s.name} className="flex justify-between capitalize"><span>{s.name}</span><span className="font-medium">{s.value}</span></li>)}</ul>
            </>
          )}
        </section>
      </div>

      <section className="bg-card rounded-xl border border-border/50 shadow-card p-4" aria-label="Top destinations">
        <h2 className="font-display font-semibold mb-3">Top destinations by confirmed bookings</h2>
        {data.top_destinations.length === 0 ? <p className="text-sm text-muted-foreground">None yet.</p>
          : <table className="w-full text-sm"><thead><tr className="text-left text-xs text-muted-foreground"><th className="py-1">Destination</th><th className="py-1 text-right">Bookings</th></tr></thead>
            <tbody>{data.top_destinations.map(d => <tr key={d.destination} className="border-t border-border/40"><td className="py-2">{d.destination}</td><td className="py-2 text-right font-medium">{d.bookings}</td></tr>)}</tbody></table>}
      </section>
    </div>
  );
}
