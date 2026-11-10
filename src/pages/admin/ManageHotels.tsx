import { useEffect, useState } from 'react';
import { BedDouble, Pencil, Plus, Search, Star, Trash2 } from 'lucide-react';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import ConfirmDialog from '@/components/admin/ConfirmDialog';
import HotelFormDialog from '@/components/admin/HotelFormDialog';
import RoomsDialog from '@/components/admin/RoomsDialog';
import { EmptyState, ErrorState, GridSkeleton, Pager } from '@/components/QueryState';
import { ApiError } from '@/lib/api/client';
import type { Hotel } from '@/lib/api/bookings';
import { formatMinor } from '@/lib/format';
import { useAdminHotels, useDeleteHotel } from '@/hooks/useBookings';
import { useDestinations } from '@/hooks/useCatalog';
import { useDebounced } from '@/hooks/useDebounced';

export default function ManageHotels() {
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);
  const q = useDebounced(search.trim());
  useEffect(() => setPage(1), [q]);
  const { data, isLoading, isError, refetch } = useAdminHotels({ q: q || undefined, page });
  const dests = useDestinations({ page: 1, page_size: 100, sort: 'name' });
  const del = useDeleteHotel();
  const [form, setForm] = useState<{ open: boolean; hotel: Hotel | null }>({ open: false, hotel: null });
  const [rooms, setRooms] = useState<Hotel | null>(null);
  const [toDelete, setToDelete] = useState<Hotel | null>(null);
  // keep the open rooms dialog in sync with refreshed data
  const roomsHotel = rooms ? data?.items.find(h => h.id === rooms.id) ?? rooms : null;

  return (
    <div className="space-y-6 pb-24 lg:pb-0">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div><h1 className="text-2xl font-display font-bold text-foreground">Hotels</h1><p className="text-sm text-muted-foreground mt-1">{data ? `${data.total} hotel${data.total === 1 ? '' : 's'}` : 'Loading…'}</p></div>
        <Button className="gradient-primary text-primary-foreground gap-2" onClick={() => setForm({ open: true, hotel: null })}><Plus className="w-4 h-4" />Add hotel</Button>
      </div>
      <div className="relative max-w-sm"><Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" /><Input aria-label="Search hotels" placeholder="Search hotels…" value={search} className="pl-9" onChange={e => setSearch(e.target.value)} /></div>
      {isLoading && <GridSkeleton count={4} height="h-40" />}
      {isError && <ErrorState message="We couldn't load hotels." onRetry={() => refetch()} />}
      {data?.items.length === 0 && <EmptyState title={q ? 'No hotels match your search' : 'No hotels yet'} hint={q ? undefined : 'Add the first hotel to enable bookings.'} />}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
        {data?.items.map(h => (
          <article key={h.id} aria-label={h.name} className="bg-card rounded-xl border border-border/50 shadow-card p-5 space-y-3">
            <div className="flex items-start justify-between gap-2">
              <div><h3 className="font-display font-semibold text-card-foreground">{h.name}</h3><p className="text-sm text-muted-foreground flex items-center gap-1">{h.destination_name}{h.star_rating ? <>· {h.star_rating}<Star className="w-3 h-3 fill-warning text-warning" /></> : null}</p></div>
              <span className={`text-xs px-2 py-0.5 rounded-full ${h.is_published ? 'bg-success/15 text-success' : 'bg-muted text-muted-foreground'}`}>{h.is_published ? 'Published' : 'Draft'}</span>
            </div>
            <p className="text-xs text-muted-foreground">{h.room_types.length} room type{h.room_types.length === 1 ? '' : 's'}{h.from_price_minor != null ? ` · from ${formatMinor(h.from_price_minor, h.currency)}/night` : ''}{h.source === 'seed' ? ' · seed data' : ''}</p>
            <div className="flex gap-2">
              <Button size="sm" variant="outline" className="gap-1.5" onClick={() => setForm({ open: true, hotel: h })}><Pencil className="w-3.5 h-3.5" />Edit</Button>
              <Button size="sm" variant="outline" className="gap-1.5" onClick={() => setRooms(h)}><BedDouble className="w-3.5 h-3.5" />Rooms</Button>
              <Button size="icon" variant="outline" aria-label={`Delete ${h.name}`} onClick={() => setToDelete(h)}><Trash2 className="w-4 h-4 text-destructive" /></Button>
            </div>
          </article>
        ))}
      </div>
      {data && <Pager page={page} pageSize={data.page_size} total={data.total} onPage={setPage} />}
      <HotelFormDialog open={form.open} onOpenChange={o => setForm(f => ({ ...f, open: o }))} hotel={form.hotel} destinations={dests.data?.items ?? []} />
      <RoomsDialog hotel={roomsHotel} onClose={() => setRooms(null)} />
      <ConfirmDialog open={!!toDelete} onOpenChange={o => !o && setToDelete(null)} title={`Delete ${toDelete?.name}?`} description="The hotel is hidden from travelers. Hotels with active bookings cannot be deleted."
        onConfirm={() => toDelete && del.mutate(toDelete.id, { onSuccess: () => { toast.success('Hotel deleted'); setToDelete(null); }, onError: e => toast.error(e instanceof ApiError ? e.message : 'Could not delete the hotel') })} />
    </div>
  );
}
