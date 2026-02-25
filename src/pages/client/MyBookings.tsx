import { useState } from 'react';
import { bookings as initialBookings, formatINR } from '@/data/mockData';
import { useAuth } from '@/contexts/AuthContext';
import StatusBadge from '@/components/StatusBadge';
import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { motion } from 'framer-motion';
import { toast } from 'sonner';

export default function MyBookings() {
  const { user } = useAuth();
  const [allBookings, setAllBookings] = useState(initialBookings);
  const myBookings = allBookings.filter(b => b.clientId === user?.id);

  const upcoming = myBookings.filter(b => b.status === 'approved' || b.status === 'pending');
  const past = myBookings.filter(b => b.status === 'rejected');

  const handleCancel = (id: string) => {
    setAllBookings(prev => prev.map(b => b.id === id ? { ...b, status: 'rejected' as const, paymentStatus: 'refunded' as const } : b));
    toast.success('Booking cancelled');
  };

  const renderBookings = (list: typeof myBookings) => (
    <div className="space-y-4">
      {list.length === 0 && (
        <p className="text-center text-muted-foreground py-12">No bookings found</p>
      )}
      {list.map((b, i) => (
        <motion.div key={b.id} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.05 }}
          whileHover={{ y: -1, transition: { duration: 0.2 } }}
          className="bg-card rounded-xl border border-border/50 shadow-card p-4 sm:p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-3 sm:gap-4">
          <div className="space-y-1">
            <h3 className="font-semibold text-card-foreground text-sm sm:text-base">{b.packageName}</h3>
            <div className="flex flex-wrap items-center gap-2 sm:gap-3 text-xs text-muted-foreground">
              <span>📅 {b.travelDate}</span>
              <span>👥 {b.travelers} travelers</span>
              <span className="font-display font-bold text-primary">💰 {formatINR(b.totalAmount)}</span>
            </div>
          </div>
          <div className="flex items-center gap-2 sm:gap-3">
            <StatusBadge status={b.status} />
            <StatusBadge status={b.paymentStatus} />
            {b.status === 'pending' && (
              <Button size="sm" variant="outline" className="text-destructive hover:bg-destructive/10"
                onClick={() => handleCancel(b.id)}>Cancel</Button>
            )}
          </div>
        </motion.div>
      ))}
    </div>
  );

  return (
    <div className="space-y-6 pb-24 lg:pb-0">
      <div>
        <h1 className="text-2xl font-display font-bold text-foreground">My Bookings</h1>
        <p className="text-sm text-muted-foreground mt-1">Track and manage your travel bookings</p>
      </div>

      <Tabs defaultValue="upcoming">
        <TabsList>
          <TabsTrigger value="upcoming">Upcoming ({upcoming.length})</TabsTrigger>
          <TabsTrigger value="past">Past ({past.length})</TabsTrigger>
          <TabsTrigger value="all">All ({myBookings.length})</TabsTrigger>
        </TabsList>
        <TabsContent value="upcoming" className="mt-4">{renderBookings(upcoming)}</TabsContent>
        <TabsContent value="past" className="mt-4">{renderBookings(past)}</TabsContent>
        <TabsContent value="all" className="mt-4">{renderBookings(myBookings)}</TabsContent>
      </Tabs>
    </div>
  );
}
