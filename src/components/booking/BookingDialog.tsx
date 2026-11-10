import { useEffect, useRef, useState } from 'react';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { useAuth } from '@/contexts/AuthContext';
import { ApiError } from '@/lib/api/client';
import type { Booking, Hotel, RoomAvailability } from '@/lib/api/bookings';
import { formatMinor } from '@/lib/format';
import { useCreateBooking } from '@/hooks/useBookings';

/** Step 1 of booking: reserve (hold) the rooms. One idempotency key per dialog session: double clicks and retries cannot create duplicates. */
export default function BookingDialog({ hotel, option, stay, onClose, onCreated }: {
  hotel: Hotel; option: RoomAvailability | null; stay: { check_in: string; check_out: string; guests: number; rooms: number };
  onClose: () => void; onCreated: (b: Booking) => void;
}) {
  const { user } = useAuth();
  const [name, setName] = useState(user?.name ?? '');
  const [phone, setPhone] = useState(user?.phone ?? '');
  const [error, setError] = useState('');
  const key = useRef<string | null>(null);
  const create = useCreateBooking();
  useEffect(() => { if (option) { key.current = crypto.randomUUID(); setError(''); } }, [option]);
  if (!option) return null;

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (name.trim().length < 2) { setError('Enter the guest name'); return; }
    setError('');
    create.mutate({ key: key.current!, body: { room_type_id: option.room_type.id, ...stay, guest_name: name.trim(), guest_phone: phone.trim() || undefined } }, {
      onSuccess: b => { toast.success(`Rooms held for ${b.reference}. Complete payment to confirm.`); onCreated(b); },
      onError: err => setError(err instanceof ApiError ? err.message : 'Could not create the booking. Please try again.'),
    });
  };

  return (
    <Dialog open onOpenChange={o => { if (!o && !create.isPending) onClose(); }}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle className="font-display">Reserve {option.room_type.name}</DialogTitle>
          <DialogDescription>{hotel.name} · {stay.check_in} to {stay.check_out} ({option.nights} night{option.nights === 1 ? '' : 's'}) · {stay.rooms} room{stay.rooms === 1 ? '' : 's'}, {stay.guests} guest{stay.guests === 1 ? '' : 's'}</DialogDescription>
        </DialogHeader>
        <form onSubmit={submit} className="space-y-4" noValidate>
          <div className="space-y-2"><Label htmlFor="bk-name">Guest name</Label><Input id="bk-name" value={name} onChange={e => setName(e.target.value)} autoComplete="name" /></div>
          <div className="space-y-2"><Label htmlFor="bk-phone">Phone (optional)</Label><Input id="bk-phone" value={phone} onChange={e => setPhone(e.target.value)} autoComplete="tel" /></div>
          <div className="rounded-lg bg-muted/50 p-3 text-sm flex justify-between"><span>Total</span><strong>{formatMinor(option.total_minor, option.room_type.currency)}</strong></div>
          <p className="text-xs text-muted-foreground">Rooms are held for a short time while you pay. Free cancellation up to 2 days before check-in.</p>
          {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
          <div className="flex justify-end gap-3">
            <Button type="button" variant="outline" onClick={onClose} disabled={create.isPending}>Cancel</Button>
            <Button type="submit" className="gradient-primary text-primary-foreground" disabled={create.isPending}>{create.isPending ? 'Reserving…' : 'Reserve rooms'}</Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
