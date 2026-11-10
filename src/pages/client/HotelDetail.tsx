import { useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { ArrowLeft, Star, Users } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Skeleton } from '@/components/ui/skeleton';
import BookingDialog from '@/components/booking/BookingDialog';
import PaymentDialog from '@/components/booking/PaymentDialog';
import { EmptyState, ErrorState } from '@/components/QueryState';
import { ApiError } from '@/lib/api/client';
import type { Booking, RoomAvailability } from '@/lib/api/bookings';
import { formatMinor } from '@/lib/format';
import { useAvailability, useHotel } from '@/hooks/useBookings';

const iso = (d: Date) => d.toISOString().slice(0, 10);
const plus = (days: number) => iso(new Date(Date.now() + days * 86_400_000));

export default function HotelDetail() {
  const { ref } = useParams();
  const hotel = useHotel(ref);
  const [form, setForm] = useState({ check_in: plus(14), check_out: plus(16), guests: '2', rooms: '1' });
  const [search, setSearch] = useState<{ check_in: string; check_out: string; guests: number; rooms: number } | null>(null);
  const [formError, setFormError] = useState('');
  const avail = useAvailability(ref, search);
  const [choice, setChoice] = useState<RoomAvailability | null>(null);
  const [created, setCreated] = useState<Booking | null>(null);
  const [paying, setPaying] = useState(false);
  const [done, setDone] = useState<Booking | null>(null);

  if (hotel.isLoading) return <div className="space-y-4" role="status" aria-label="Loading"><Skeleton className="h-8 w-64" /><Skeleton className="h-48 rounded-xl" /></div>;
  if (hotel.isError || !hotel.data) {
    const nf = hotel.error instanceof ApiError && hotel.error.status === 404;
    return <div className="space-y-4"><Back />{nf ? <EmptyState title="Hotel not found" hint="It may no longer be available." /> : <ErrorState message="We couldn't load this hotel." onRetry={() => hotel.refetch()} />}</div>;
  }
  const h = hotel.data;

  const run = (e: React.FormEvent) => {
    e.preventDefault();
    const guests = Number(form.guests), rooms = Number(form.rooms);
    if (!form.check_in || !form.check_out || form.check_out <= form.check_in) return setFormError('Check-out must be after check-in');
    if (!Number.isInteger(guests) || guests < 1 || !Number.isInteger(rooms) || rooms < 1 || rooms > 10) return setFormError('Enter valid guests (1+) and rooms (1-10)');
    setFormError(''); setDone(null);
    setSearch({ check_in: form.check_in, check_out: form.check_out, guests, rooms });
  };

  return (
    <div className="space-y-6 pb-24 lg:pb-0">
      <Back />
      <div>
        <h1 className="text-3xl font-display font-bold text-foreground">{h.name}</h1>
        <p className="text-muted-foreground flex items-center gap-2">{h.destination_name}{h.address ? ` · ${h.address}` : ''}
          {h.star_rating && <span className="flex">{Array.from({ length: h.star_rating }, (_, k) => <Star key={k} className="w-3.5 h-3.5 fill-warning text-warning" />)}<span className="sr-only">{h.star_rating} stars</span></span>}</p>
      </div>
      {h.description && <p className="text-foreground/90">{h.description}</p>}
      {h.amenities.length > 0 && <ul className="flex flex-wrap gap-2" aria-label="Amenities">{h.amenities.map(a => <li key={a} className="text-xs bg-primary/10 text-primary px-3 py-1 rounded-full">{a}</li>)}</ul>}
      {h.source === 'seed' && <p className="text-xs text-muted-foreground">Illustrative listing: fictional property with placeholder prices.</p>}

      <form onSubmit={run} className="bg-card rounded-xl border border-border/50 shadow-card p-4 grid grid-cols-2 md:grid-cols-5 gap-3 items-end" aria-label="Check availability" noValidate>
        <div className="space-y-1"><Label htmlFor="av-in">Check-in</Label><Input id="av-in" type="date" value={form.check_in} min={iso(new Date())} onChange={e => setForm({ ...form, check_in: e.target.value })} /></div>
        <div className="space-y-1"><Label htmlFor="av-out">Check-out</Label><Input id="av-out" type="date" value={form.check_out} onChange={e => setForm({ ...form, check_out: e.target.value })} /></div>
        <div className="space-y-1"><Label htmlFor="av-g">Guests</Label><Input id="av-g" inputMode="numeric" value={form.guests} onChange={e => setForm({ ...form, guests: e.target.value })} /></div>
        <div className="space-y-1"><Label htmlFor="av-r">Rooms</Label><Input id="av-r" inputMode="numeric" value={form.rooms} onChange={e => setForm({ ...form, rooms: e.target.value })} /></div>
        <Button type="submit" className="gradient-primary text-primary-foreground">Check availability</Button>
        {formError && <p role="alert" className="col-span-full text-sm text-destructive">{formError}</p>}
      </form>

      {done && <div role="status" className="rounded-xl border border-success/30 bg-success/10 p-4 text-sm">Booking <strong>{done.reference}</strong> is confirmed. <Link to="/dashboard/bookings" className="text-primary underline">View my bookings</Link></div>}
      {avail.isFetching && <p role="status" className="text-sm text-muted-foreground">Checking availability…</p>}
      {avail.isError && <ErrorState message={avail.error instanceof ApiError ? avail.error.message : "We couldn't check availability."} onRetry={() => avail.refetch()} />}
      <ul className="grid grid-cols-1 md:grid-cols-2 gap-4" aria-label="Room options">
        {(search ? avail.data?.options : h.room_types.map(r => ({ room_type: r, nights: 0, available_rooms: r.total_rooms, price_per_night_minor: r.price_per_night_minor, total_minor: 0, can_book: false, reason: 'Choose dates to see availability' })))?.map(o => (
          <li key={o.room_type.id} className="bg-card rounded-xl border border-border/50 shadow-card p-4 space-y-2" aria-label={o.room_type.name}>
            <div className="flex justify-between gap-2"><h3 className="font-semibold">{o.room_type.name}</h3><span className="text-sm">{formatMinor(o.room_type.price_per_night_minor, o.room_type.currency)}<span className="text-xs text-muted-foreground"> / night</span></span></div>
            <p className="text-xs text-muted-foreground flex items-center gap-1"><Users className="w-3.5 h-3.5" />Sleeps {o.room_type.capacity}</p>
            {search && <p className="text-sm">{o.nights} night{o.nights === 1 ? '' : 's'} · <strong>{formatMinor(o.total_minor, o.room_type.currency)}</strong> for {search.rooms} room{search.rooms === 1 ? '' : 's'}</p>}
            {o.reason && <p className={`text-xs ${o.can_book ? '' : 'text-muted-foreground'}`}>{o.reason}</p>}
            {search && o.can_book && <p className="text-xs text-success">{o.available_rooms} room{o.available_rooms === 1 ? '' : 's'} available</p>}
            <Button size="sm" className="gradient-primary text-primary-foreground" disabled={!search || !o.can_book} onClick={() => setChoice(o)}>Book</Button>
          </li>
        ))}
      </ul>

      <BookingDialog hotel={h} option={choice} stay={search ?? { check_in: '', check_out: '', guests: 1, rooms: 1 }} onClose={() => setChoice(null)}
        onCreated={b => { setChoice(null); setCreated(b); setPaying(true); }} />
      <PaymentDialog booking={created} open={paying} onOpenChange={setPaying} onPaid={b => { setDone(b); avail.refetch(); }} />
      {created && !paying && !done && <p className="text-sm text-muted-foreground">Rooms are held for booking {created.reference}. <Button variant="link" className="px-1" onClick={() => setPaying(true)}>Continue to payment</Button> or find it in <Link className="underline" to="/dashboard/bookings">My bookings</Link>.</p>}
    </div>
  );
}

function Back() {
  return <Link to="/dashboard/hotels" className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground"><ArrowLeft className="w-4 h-4" />All hotels</Link>;
}
