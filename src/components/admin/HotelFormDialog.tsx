import { useEffect } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Switch } from '@/components/ui/switch';
import { Textarea } from '@/components/ui/textarea';
import { ApiError } from '@/lib/api/client';
import type { Hotel } from '@/lib/api/bookings';
import type { Destination } from '@/lib/api/catalog';
import { imageList, numField, splitList, toNum } from '@/lib/forms';
import { useSaveHotel } from '@/hooks/useBookings';

const schema = z.object({
  destinationId: z.string().min(1, 'Choose a destination'),
  name: z.string().trim().min(2, 'At least 2 characters').max(140),
  description: z.string().max(5000), address: z.string().max(240),
  latitude: numField({ label: 'Latitude', min: -90, max: 90, required: true }),
  longitude: numField({ label: 'Longitude', min: -180, max: 180, required: true }),
  stars: numField({ label: 'Stars', min: 1, max: 5, int: true }),
  amenities: z.string(), images: imageList, isPublished: z.boolean(),
});
type Values = z.infer<typeof schema>;
const blank: Values = { destinationId: '', name: '', description: '', address: '', latitude: '', longitude: '', stars: '', amenities: '', images: '', isPublished: false };

export default function HotelFormDialog({ open, onOpenChange, hotel, destinations }: { open: boolean; onOpenChange: (o: boolean) => void; hotel: Hotel | null; destinations: Destination[] }) {
  const save = useSaveHotel();
  const { register, handleSubmit, reset, watch, setValue, formState: { errors } } = useForm<Values>({ resolver: zodResolver(schema), defaultValues: blank });
  useEffect(() => {
    if (!open) return;
    reset(hotel ? { destinationId: hotel.destination_id, name: hotel.name, description: hotel.description, address: hotel.address ?? '', latitude: String(hotel.latitude), longitude: String(hotel.longitude),
      stars: hotel.star_rating?.toString() ?? '', amenities: hotel.amenities.join(', '), images: hotel.images.join('\n'), isPublished: hotel.is_published } : blank);
  }, [open, hotel, reset]);
  const v = watch();
  const err = (m?: string) => m && <p className="text-xs text-destructive" role="alert">{m}</p>;

  const onSubmit = (f: Values) => save.mutate({
    id: hotel?.id,
    data: { destination_id: f.destinationId, name: f.name, description: f.description, address: f.address || null, latitude: Number(f.latitude), longitude: Number(f.longitude),
      star_rating: toNum(f.stars), amenities: splitList(f.amenities), images: splitList(f.images), is_published: f.isPublished },
  }, { onSuccess: () => { toast.success(hotel ? 'Hotel updated' : 'Hotel created'); onOpenChange(false); }, onError: e => toast.error(e instanceof ApiError ? e.message : 'Could not save the hotel') });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader><DialogTitle className="font-display">{hotel ? 'Edit hotel' : 'Add hotel'}</DialogTitle><DialogDescription>Rooms and inventory are managed after the hotel is saved.</DialogDescription></DialogHeader>
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" noValidate>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="space-y-2"><Label htmlFor="h-name">Name</Label><Input id="h-name" {...register('name')} />{err(errors.name?.message)}</div>
            <div className="space-y-2"><Label htmlFor="h-dest">Destination</Label>
              <Select value={v.destinationId || undefined} onValueChange={x => setValue('destinationId', x, { shouldValidate: true })}><SelectTrigger id="h-dest"><SelectValue placeholder="Choose a destination" /></SelectTrigger>
                <SelectContent>{destinations.map(d => <SelectItem key={d.id} value={d.id}>{d.name}</SelectItem>)}</SelectContent></Select>{err(errors.destinationId?.message)}</div>
            <div className="space-y-2"><Label htmlFor="h-lat">Latitude</Label><Input id="h-lat" inputMode="decimal" {...register('latitude')} />{err(errors.latitude?.message)}</div>
            <div className="space-y-2"><Label htmlFor="h-lng">Longitude</Label><Input id="h-lng" inputMode="decimal" {...register('longitude')} />{err(errors.longitude?.message)}</div>
            <div className="space-y-2"><Label htmlFor="h-stars">Stars (1-5)</Label><Input id="h-stars" inputMode="numeric" {...register('stars')} />{err(errors.stars?.message)}</div>
            <div className="space-y-2"><Label htmlFor="h-addr">Address</Label><Input id="h-addr" {...register('address')} /></div>
          </div>
          <div className="space-y-2"><Label htmlFor="h-desc">Description</Label><Textarea id="h-desc" rows={3} {...register('description')} /></div>
          <div className="space-y-2"><Label htmlFor="h-am">Amenities (comma separated)</Label><Input id="h-am" {...register('amenities')} /></div>
          <div className="space-y-2"><Label htmlFor="h-img">Image URLs (one per line)</Label><Textarea id="h-img" rows={2} {...register('images')} />{err(errors.images?.message)}</div>
          <div className="flex items-center gap-3"><Switch id="h-pub" checked={v.isPublished} onCheckedChange={x => setValue('isPublished', x)} /><Label htmlFor="h-pub">Published (bookable by travelers)</Label></div>
          <div className="flex justify-end gap-3"><Button type="button" variant="outline" onClick={() => onOpenChange(false)}>Cancel</Button>
            <Button type="submit" disabled={save.isPending} className="gradient-primary text-primary-foreground">{save.isPending ? 'Saving…' : hotel ? 'Save changes' : 'Create'}</Button></div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
