/**
 * Client Dashboard Page
 * Main dashboard for regular users where they can:
 * - See overview of their bookings
 * - View upcoming trips
 * - Check booking history
 * - See travel statistics
 */
import { CalendarDays, MapPin, Clock, Plane } from 'lucide-react';
import StatCard from '@/components/StatCard';
import StatusBadge from '@/components/StatusBadge';
import { bookings, travelPackages, formatINR } from '@/data/mockData';
import { useAuth } from '@/contexts/AuthContext';
import { motion } from 'framer-motion';

export default function ClientDashboard() {
  const { user } = useAuth();
  
  // Filter bookings to show only this user's bookings
  const myBookings = bookings.filter(b => b.clientId === user?.id);
  const upcoming = myBookings.filter(b => b.status === 'approved');
  const pending = myBookings.filter(b => b.status === 'pending');

  return (
    <div className="space-y-8 pb-24 lg:pb-0">
      <div>
        <h1 className="text-2xl font-display font-bold text-foreground">Welcome back, {user?.name?.split(' ')[0]}!</h1>
        <p className="text-muted-foreground text-sm mt-1">Here's your travel overview</p>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4">
        <StatCard title="Total Bookings" value={myBookings.length} icon={CalendarDays} variant="primary" />
        <StatCard title="Upcoming Trips" value={upcoming.length} icon={Plane} variant="accent" />
        <StatCard title="Pending" value={pending.length} icon={Clock} variant="warning" />
        <StatCard title="Destinations" value={new Set(myBookings.map(b => b.packageName)).size} icon={MapPin} variant="success" />
      </div>

      {/* Upcoming Trips */}
      {upcoming.length > 0 && (
        <div className="space-y-4">
          <h2 className="text-lg font-display font-semibold text-foreground">Upcoming Trips</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {upcoming.map((b, i) => {
              const pkg = travelPackages.find(p => p.id === b.packageId);
              return (
                <motion.div key={b.id} initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.1 }}
                  whileHover={{ y: -2, transition: { duration: 0.2 } }}
                  className="bg-card rounded-xl border border-border/50 shadow-card overflow-hidden flex">
                  <div className="w-28 sm:w-32 h-full shrink-0">
                    <img src={pkg?.images[0]} alt={b.packageName} className="w-full h-full object-cover" />
                  </div>
                  <div className="flex-1 p-4 min-w-0">
                    <h3 className="font-semibold text-card-foreground text-sm sm:text-base truncate">{b.packageName}</h3>
                    <p className="text-xs text-muted-foreground mt-1">📅 {b.travelDate} · 👥 {b.travelers} travelers</p>
                    <div className="flex items-center justify-between mt-3">
                      <span className="text-sm font-display font-bold text-primary">{formatINR(b.totalAmount)}</span>
                      <StatusBadge status={b.status} />
                    </div>
                  </div>
                </motion.div>
              );
            })}
          </div>
        </div>
      )}

      {/* All Bookings Summary */}
      <div className="space-y-4">
        <h2 className="text-lg font-display font-semibold text-foreground">Booking History</h2>
        <div className="bg-card rounded-xl border border-border/50 shadow-card overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-border/50">
                  <th className="text-left text-xs font-medium text-muted-foreground px-3 sm:px-6 py-3">Package</th>
                  <th className="text-left text-xs font-medium text-muted-foreground px-3 sm:px-6 py-3 hidden sm:table-cell">Date</th>
                  <th className="text-left text-xs font-medium text-muted-foreground px-3 sm:px-6 py-3 hidden md:table-cell">Travelers</th>
                  <th className="text-left text-xs font-medium text-muted-foreground px-3 sm:px-6 py-3">Amount</th>
                  <th className="text-left text-xs font-medium text-muted-foreground px-3 sm:px-6 py-3">Status</th>
                </tr>
              </thead>
              <tbody>
                {myBookings.map(b => (
                  <tr key={b.id} className="border-t border-border/30 hover:bg-muted/30 transition-colors">
                    <td className="px-3 sm:px-6 py-3 sm:py-4">
                      <p className="text-sm font-medium text-card-foreground truncate max-w-[120px] sm:max-w-none">{b.packageName}</p>
                      <p className="text-xs text-muted-foreground sm:hidden">{b.travelDate}</p>
                    </td>
                    <td className="px-3 sm:px-6 py-3 sm:py-4 text-sm text-muted-foreground hidden sm:table-cell">{b.travelDate}</td>
                    <td className="px-3 sm:px-6 py-3 sm:py-4 text-sm text-card-foreground hidden md:table-cell">{b.travelers}</td>
                    <td className="px-3 sm:px-6 py-3 sm:py-4 text-sm font-medium text-card-foreground">{formatINR(b.totalAmount)}</td>
                    <td className="px-3 sm:px-6 py-3 sm:py-4"><StatusBadge status={b.status} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}
