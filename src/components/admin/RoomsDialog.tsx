import { useState } from 'react';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { ApiError } from '@/lib/api/client';
import type { Hotel, RoomType } from '@/lib/api/bookings';
import { formatMinor } from '@/lib/format';
import { minorToRupees, rupeesToMinor } from '@/lib/forms';
import { useInventory, useSaveRoom } from '@/hooks/useBookings';

const errMsg = (e: unknown) => (e instanceof ApiError ? e.message : 'Something went wrong');
const blank = { name: '', capacity: '2', price: '', total: '5', active: true };

/** Room types of one hotel, plus per-night inventory overrides (blackouts, extra stock). The server refuses to lower stock below booked rooms. */
export default function RoomsDialog({ hotel, onClose }: { hotel: Hotel | null; onClose: () => void }) {
  const save = useSaveRoom();
  const inv = useInventory();
  const [editing, setEditing] = useState<RoomType | null>(null);
  const [f, setF] = useState(blank);
  const [invFor, setInvFor] = useState<RoomType | null>(null);
  const [range, setRange] = useState({ start: '', end: '', total: '0' });
  if (!hotel) return null;

  const startEdit = (r: RoomType | null) => { setEditing(r); setF(r ? { name: r.name, capacity: String(r.capacity), price: minorToRupees(r.price_per_night_minor), total: String(r.total_rooms), active: r.is_active } : blank); };
  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    const price = rupeesToMinor(f.price);
    const cap = Number(f.capacity), total = Number(f.total);
    if (f.name.trim().length < 2 || price == null || price < 0 || !Number.isInteger(cap) || cap < 1 || cap > 12 || !Number.isInteger(total) || total < 0) { toast.error('Check the room details (name, capacity 1-12, price, rooms)'); return; }
    save.mutate({ hotelId: hotel.id, id: editing?.id, data: { name: f.name.trim(), capacity: cap, price_per_night_minor: price, total_rooms: total, is_active: f.active } },
      { onSuccess: () => { toast.success(editing ? 'Room updated' : 'Room added'); startEdit(null); }, onError: x => toast.error(errMsg(x)) });
  };
  const applyInventory = (e: React.FormEvent) => {
    e.preventDefault();
    if (!invFor || !range.start || !range.end) { toast.error('Choose a start and end date'); return; }
    inv.mutate({ id: invFor.id, start: range.start, end: range.end, total: Number(range.total) }, { onSuccess: r => toast.success(`Inventory set for ${r.nights} night(s)`), onError: x => toast.error(errMsg(x)) });
  };

  return (
    <Dialog open onOpenChange={o => !o && onClose()}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader><DialogTitle className="font-display">Rooms · {hotel.name}</DialogTitle><DialogDescription>Room types, prices and nightly inventory.</DialogDescription></DialogHeader>
        <ul className="space-y-2" aria-label="Room types">
          {hotel.room_types.length === 0 && <li className="text-sm text-muted-foreground">No room types yet.</li>}
          {hotel.room_types.map(r => (
            <li key={r.id} className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-border/50 p-3 text-sm">
              <span><strong>{r.name}</strong> · sleeps {r.capacity} · {formatMinor(r.price_per_night_minor, r.currency)}/night · {r.total_rooms} rooms{r.is_active ? '' : ' · inactive'}</span>
              <span className="flex gap-2"><Button size="sm" variant="outline" onClick={() => startEdit(r)}>Edit</Button><Button size="sm" variant="outline" onClick={() => { setInvFor(r); setRange({ start: '', end: '', total: String(r.total_rooms) }); }}>Inventory</Button></span>
            </li>
          ))}
        </ul>
        <form onSubmit={submit} className="grid grid-cols-2 sm:grid-cols-5 gap-3 items-end border-t border-border/50 pt-4" aria-label={editing ? 'Edit room' : 'Add room'}>
          <div className="space-y-1 col-span-2"><Label htmlFor="r-name">Room name</Label><Input id="r-name" value={f.name} onChange={e => setF({ ...f, name: e.target.value })} /></div>
          <div className="space-y-1"><Label htmlFor="r-cap">Sleeps</Label><Input id="r-cap" inputMode="numeric" value={f.capacity} onChange={e => setF({ ...f, capacity: e.target.value })} /></div>
          <div className="space-y-1"><Label htmlFor="r-price">Price / night (₹)</Label><Input id="r-price" inputMode="decimal" value={f.price} onChange={e => setF({ ...f, price: e.target.value })} /></div>
          <div className="space-y-1"><Label htmlFor="r-total">Rooms</Label><Input id="r-total" inputMode="numeric" value={f.total} onChange={e => setF({ ...f, total: e.target.value })} /></div>
          <div className="flex items-center gap-2 col-span-2"><Switch id="r-act" checked={f.active} onCheckedChange={v => setF({ ...f, active: v })} /><Label htmlFor="r-act">Active</Label></div>
          <div className="col-span-2 sm:col-span-3 flex gap-2 justify-end">{editing && <Button type="button" variant="outline" onClick={() => startEdit(null)}>Cancel edit</Button>}
            <Button type="submit" disabled={save.isPending} className="gradient-primary text-primary-foreground">{editing ? 'Save room' : 'Add room'}</Button></div>
        </form>
        {invFor && (
          <form onSubmit={applyInventory} className="grid grid-cols-2 sm:grid-cols-4 gap-3 items-end border-t border-border/50 pt-4" aria-label={`Inventory for ${invFor.name}`}>
            <p className="col-span-full text-sm font-medium">Inventory: {invFor.name}</p>
            <div className="space-y-1"><Label htmlFor="i-s">From</Label><Input id="i-s" type="date" value={range.start} onChange={e => setRange({ ...range, start: e.target.value })} /></div>
            <div className="space-y-1"><Label htmlFor="i-e">To (inclusive)</Label><Input id="i-e" type="date" value={range.end} onChange={e => setRange({ ...range, end: e.target.value })} /></div>
            <div className="space-y-1"><Label htmlFor="i-t">Rooms available</Label><Input id="i-t" inputMode="numeric" value={range.total} onChange={e => setRange({ ...range, total: e.target.value })} /></div>
            <Button type="submit" disabled={inv.isPending}>Apply</Button>
            <p className="col-span-full text-xs text-muted-foreground">Use 0 to close the dates. You cannot go below the rooms already booked.</p>
          </form>
        )}
        <div className="flex justify-end"><Button variant="outline" onClick={onClose}>Close</Button></div>
      </DialogContent>
    </Dialog>
  );
}
