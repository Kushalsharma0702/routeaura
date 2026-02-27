/**
 * Admin Dashboard Page
 * Central control panel for administrators with:
 * - Key metrics (users, bookings, revenue, active trips)
 * - Monthly booking trends chart
 * - Destination popularity pie chart
 * - Recent bookings table
 * 
 * This gives admins a bird's eye view of the entire platform
 */
import { Users, BookOpen, DollarSign, Plane } from 'lucide-react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts';
import StatCard from '@/components/StatCard';
import StatusBadge from '@/components/StatusBadge';
import { bookings, monthlyBookingsData, destinationData, demoUsers, formatINR } from '@/data/mockData';
import { motion } from 'framer-motion';
import { useIsMobile } from '@/hooks/use-mobile';

export default function AdminDashboard() {
  const isMobile = useIsMobile();
  
  // Calculate key metrics for the dashboard
  const clients = demoUsers.filter(u => u.role === 'client');
  const totalRevenue = bookings.filter(b => b.paymentStatus === 'paid').reduce((s, b) => s + b.totalAmount, 0);
  const activeTrips = bookings.filter(b => b.status === 'approved').length;

  return (
    <div className="space-y-8 pb-24 lg:pb-0">
      <div>
        <h1 className="text-2xl font-display font-bold text-foreground">Admin Dashboard</h1>
        <p className="text-muted-foreground text-sm mt-1">Overview of your travel management system</p>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard title="Total Users" value={clients.length} icon={Users} trend="+12% this month" trendUp variant="primary" />
        <StatCard title="Total Bookings" value={bookings.length} icon={BookOpen} trend="+8% this month" trendUp variant="accent" />
        <StatCard title="Revenue" value={formatINR(totalRevenue)} icon={DollarSign} trend="+15% this month" trendUp variant="success" />
        <StatCard title="Active Trips" value={activeTrips} icon={Plane} variant="warning" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }}
          className="lg:col-span-2 bg-card rounded-xl border border-border/50 p-4 sm:p-6 shadow-card">
          <h3 className="text-base font-display font-semibold text-card-foreground mb-4">Monthly Bookings</h3>
          <ResponsiveContainer width="100%" height={280}>
            <LineChart data={monthlyBookingsData}>
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(200 20% 85%)" />
              {!isMobile && <XAxis dataKey="month" tick={{ fontSize: 12 }} stroke="hsl(200 15% 45%)" />}
              <YAxis tick={{ fontSize: 12 }} stroke="hsl(200 15% 45%)" width={30} />
              <Tooltip contentStyle={{ borderRadius: '8px', border: '1px solid hsl(200 20% 85%)', fontSize: '12px' }} />
              <Line type="monotone" dataKey="bookings" stroke="hsl(180 50% 35%)" strokeWidth={2.5} dot={{ fill: 'hsl(180 50% 35%)', r: 4 }} />
            </LineChart>
          </ResponsiveContainer>
        </motion.div>

        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.3 }}
          className="bg-card rounded-xl border border-border/50 p-4 sm:p-6 shadow-card">
          <h3 className="text-base font-display font-semibold text-card-foreground mb-4">Destination Popularity</h3>
          <ResponsiveContainer width="100%" height={200}>
            <PieChart>
              <Pie data={destinationData} cx="50%" cy="50%" innerRadius={50} outerRadius={80} dataKey="value" paddingAngle={4}>
                {destinationData.map((entry, i) => (
                  <Cell key={i} fill={entry.fill} />
                ))}
              </Pie>
              <Tooltip contentStyle={{ borderRadius: '8px', fontSize: '12px' }} />
            </PieChart>
          </ResponsiveContainer>
          <div className="space-y-2 mt-2">
            {destinationData.map(d => (
              <div key={d.name} className="flex items-center justify-between text-sm">
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 rounded-full" style={{ backgroundColor: d.fill }} />
                  <span className="text-muted-foreground">{d.name}</span>
                </div>
                <span className="font-medium text-card-foreground">{d.value}%</span>
              </div>
            ))}
          </div>
        </motion.div>
      </div>

      {/* Recent Bookings Table */}
      <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.4 }}
        className="bg-card rounded-xl border border-border/50 shadow-card overflow-hidden">
        <div className="p-4 sm:p-6 pb-4">
          <h3 className="text-base font-display font-semibold text-card-foreground">Recent Bookings</h3>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-t border-border/50">
                <th className="text-left text-xs font-medium text-muted-foreground px-4 sm:px-6 py-3">Client</th>
                <th className="text-left text-xs font-medium text-muted-foreground px-4 sm:px-6 py-3">Package</th>
                <th className="text-left text-xs font-medium text-muted-foreground px-4 sm:px-6 py-3 hidden sm:table-cell">Date</th>
                <th className="text-left text-xs font-medium text-muted-foreground px-4 sm:px-6 py-3">Amount</th>
                <th className="text-left text-xs font-medium text-muted-foreground px-4 sm:px-6 py-3">Status</th>
                <th className="text-left text-xs font-medium text-muted-foreground px-4 sm:px-6 py-3 hidden sm:table-cell">Payment</th>
              </tr>
            </thead>
            <tbody>
              {bookings.map(b => (
                <tr key={b.id} className="border-t border-border/30 hover:bg-muted/30 transition-colors">
                  <td className="px-4 sm:px-6 py-4">
                    <div>
                      <p className="text-sm font-medium text-card-foreground">{b.clientName}</p>
                      <p className="text-xs text-muted-foreground hidden sm:block">{b.clientEmail}</p>
                    </div>
                  </td>
                  <td className="px-4 sm:px-6 py-4 text-sm text-card-foreground">{b.packageName}</td>
                  <td className="px-4 sm:px-6 py-4 text-sm text-muted-foreground hidden sm:table-cell">{b.travelDate}</td>
                  <td className="px-4 sm:px-6 py-4 text-sm font-medium text-card-foreground">{formatINR(b.totalAmount)}</td>
                  <td className="px-4 sm:px-6 py-4"><StatusBadge status={b.status} /></td>
                  <td className="px-4 sm:px-6 py-4 hidden sm:table-cell"><StatusBadge status={b.paymentStatus} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </motion.div>
    </div>
  );
}
