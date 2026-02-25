import { useState } from 'react';
import { bookings as initialBookings, Booking, formatINR } from '@/data/mockData';
import { Button } from '@/components/ui/button';
import StatusBadge from '@/components/StatusBadge';
import { Check, X, Search } from 'lucide-react';
import { Input } from '@/components/ui/input';
import { motion } from 'framer-motion';
import { toast } from 'sonner';

export default function ManageBookings() {
  const [allBookings, setAllBookings] = useState<Booking[]>(initialBookings);
  const [search, setSearch] = useState('');

  const filtered = allBookings.filter(b =>
    b.clientName.toLowerCase().includes(search.toLowerCase()) ||
    b.packageName.toLowerCase().includes(search.toLowerCase())
  );

  const updateStatus = (id: string, status: 'approved' | 'rejected') => {
    setAllBookings(prev => prev.map(b =>
      b.id === id ? { ...b, status, paymentStatus: status === 'approved' ? 'paid' as const : 'refunded' as const } : b
    ));
    toast.success(`Booking ${status} successfully`);
  };

  return (
    <div className="space-y-6 pb-24 lg:pb-0">
      <div>
        <h1 className="text-2xl font-display font-bold text-foreground">Manage Bookings</h1>
        <p className="text-sm text-muted-foreground mt-1">Approve or reject client booking requests</p>
      </div>

      <div className="relative max-w-sm">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
        <Input placeholder="Search bookings..." value={search} onChange={e => setSearch(e.target.value)} className="pl-9" />
      </div>

      <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}
        className="bg-card rounded-xl border border-border/50 shadow-card overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-border/50">
                <th className="text-left text-xs font-medium text-muted-foreground px-3 sm:px-6 py-3">Client</th>
                <th className="text-left text-xs font-medium text-muted-foreground px-3 sm:px-6 py-3 hidden sm:table-cell">Package</th>
                <th className="text-left text-xs font-medium text-muted-foreground px-3 sm:px-6 py-3 hidden lg:table-cell">Travelers</th>
                <th className="text-left text-xs font-medium text-muted-foreground px-3 sm:px-6 py-3 hidden lg:table-cell">Date</th>
                <th className="text-left text-xs font-medium text-muted-foreground px-3 sm:px-6 py-3">Amount</th>
                <th className="text-left text-xs font-medium text-muted-foreground px-3 sm:px-6 py-3">Status</th>
                <th className="text-left text-xs font-medium text-muted-foreground px-3 sm:px-6 py-3">Actions</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map(b => (
                <motion.tr key={b.id} initial={{ opacity: 0 }} animate={{ opacity: 1 }}
                  className="border-t border-border/30 hover:bg-muted/30 transition-colors">
                  <td className="px-3 sm:px-6 py-3 sm:py-4">
                    <p className="text-sm font-medium text-card-foreground truncate max-w-[100px] sm:max-w-none">{b.clientName}</p>
                    <p className="text-xs text-muted-foreground sm:hidden truncate max-w-[100px]">{b.packageName}</p>
                    <p className="text-xs text-muted-foreground hidden sm:block">{b.clientEmail}</p>
                  </td>
                  <td className="px-3 sm:px-6 py-3 sm:py-4 text-sm text-card-foreground hidden sm:table-cell">{b.packageName}</td>
                  <td className="px-3 sm:px-6 py-3 sm:py-4 text-sm text-card-foreground hidden lg:table-cell">{b.travelers}</td>
                  <td className="px-3 sm:px-6 py-3 sm:py-4 text-sm text-muted-foreground hidden lg:table-cell">{b.travelDate}</td>
                  <td className="px-3 sm:px-6 py-3 sm:py-4 text-sm font-medium text-card-foreground whitespace-nowrap">{formatINR(b.totalAmount)}</td>
                  <td className="px-3 sm:px-6 py-3 sm:py-4"><StatusBadge status={b.status} /></td>
                  <td className="px-3 sm:px-6 py-3 sm:py-4">
                    {b.status === 'pending' && (
                      <div className="flex gap-1 sm:gap-2">
                        <Button size="icon" variant="outline" className="h-7 w-7 sm:h-8 sm:w-auto sm:px-3 text-success hover:bg-success/10 gap-1"
                          onClick={() => updateStatus(b.id, 'approved')}>
                          <Check className="w-3 h-3" /> <span className="hidden sm:inline">Approve</span>
                        </Button>
                        <Button size="icon" variant="outline" className="h-7 w-7 sm:h-8 sm:w-auto sm:px-3 text-destructive hover:bg-destructive/10 gap-1"
                          onClick={() => updateStatus(b.id, 'rejected')}>
                          <X className="w-3 h-3" /> <span className="hidden sm:inline">Reject</span>
                        </Button>
                      </div>
                    )}
                  </td>
                </motion.tr>
              ))}
            </tbody>
          </table>
        </div>
      </motion.div>
    </div>
  );
}
