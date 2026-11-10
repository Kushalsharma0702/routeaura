import { useRef, useState } from 'react';
import { CreditCard, TriangleAlert } from 'lucide-react';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Label } from '@/components/ui/label';
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group';
import { ApiError } from '@/lib/api/client';
import type { Booking } from '@/lib/api/bookings';
import { formatMinor } from '@/lib/format';
import { usePay } from '@/hooks/useBookings';

const METHODS = [
  { id: 'dev_card_ok', label: 'Test card: approved', hint: 'Always succeeds' },
  { id: 'dev_card_declined', label: 'Test card: declined', hint: 'Simulates a declined payment' },
];

/**
 * Payment step using the DEVELOPMENT payment simulator. No card details are collected: only an opaque test token is
 * sent, and no real money moves. The idempotency key lives for the lifetime of the dialog so retries never double-charge.
 */
export default function PaymentDialog({ booking, open, onOpenChange, onPaid }: { booking: Booking | null; open: boolean; onOpenChange: (o: boolean) => void; onPaid?: (b: Booking) => void }) {
  const [method, setMethod] = useState('dev_card_ok');
  const [error, setError] = useState('');
  const key = useRef<string | null>(null);
  const pay = usePay();
  if (!booking) return null;

  const submit = () => {
    setError('');
    key.current ??= crypto.randomUUID();
    pay.mutate({ id: booking.id, method, key: key.current }, {
      onSuccess: b => { toast.success(`Booking ${b.reference} confirmed`); key.current = null; onPaid?.(b); onOpenChange(false); },
      onError: e => {
        if (e instanceof ApiError && e.status === 402) key.current = null;           // a decline is final for that key; a retry is a new attempt
        setError(e instanceof ApiError ? e.message : 'Payment failed. Please try again.');
      },
    });
  };

  return (
    <Dialog open={open} onOpenChange={o => { if (!pay.isPending) onOpenChange(o); }}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle className="font-display flex items-center gap-2"><CreditCard className="w-5 h-5" />Pay {formatMinor(booking.total_minor, booking.currency)}</DialogTitle>
          <DialogDescription>{booking.hotel_name} · {booking.check_in} to {booking.check_out} · reference {booking.reference}</DialogDescription>
        </DialogHeader>
        <div role="note" className="rounded-lg border border-warning/30 bg-warning/10 p-3 text-xs flex gap-2"><TriangleAlert className="w-4 h-4 shrink-0 text-warning mt-0.5" />
          <span><strong>Development payment simulator.</strong> No real payment is processed and no money moves. Do not enter card details anywhere in this app.</span></div>
        <RadioGroup value={method} onValueChange={setMethod} className="space-y-2" aria-label="Test payment method">
          {METHODS.map(m => (
            <div key={m.id} className="flex items-center gap-3 rounded-lg border border-border/50 p-3">
              <RadioGroupItem id={`pm-${m.id}`} value={m.id} /><Label htmlFor={`pm-${m.id}`} className="flex-1 cursor-pointer">{m.label}<span className="block text-xs text-muted-foreground font-normal">{m.hint}</span></Label>
            </div>
          ))}
        </RadioGroup>
        {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
        <div className="flex justify-end gap-3">
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={pay.isPending}>Pay later</Button>
          <Button className="gradient-primary text-primary-foreground" onClick={submit} disabled={pay.isPending}>{pay.isPending ? 'Processing…' : `Pay ${formatMinor(booking.total_minor, booking.currency)}`}</Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
