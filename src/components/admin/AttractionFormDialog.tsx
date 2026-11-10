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
import type { Attraction, Category, OpeningHours } from '@/lib/api/catalog';
import { DAYS, hoursToText, parseDayHours } from '@/lib/format';
import { imageList, minorToRupees, numField, rupeesToMinor, splitList } from '@/lib/forms';
import { useSaveAttraction } from '@/hooks/useCatalog';

const hoursField = z.string().superRefine((v, ctx) => {
  try { parseDayHours(v); } catch (e) { ctx.addIssue({ code: 'custom', message: (e as Error).message }); }
});
const schema = z.object({
  name: z.string().trim().min(2, 'At least 2 characters').max(140),
  categoryId: z.string().min(1, 'Choose a category'),
  description: z.string().max(5000),
  latitude: numField({ label: 'Latitude', min: -90, max: 90, required: true }),
  longitude: numField({ label: 'Longitude', min: -180, max: 180, required: true }),
  minutes: numField({ label: 'Duration', min: 5, max: 1440, int: true, required: true }),
  cost: numField({ label: 'Cost', min: 0, max: 10_000_000 }),
  images: imageList,
  isOutdoor: z.boolean(), isPublished: z.boolean(),
  hours: z.object(Object.fromEntries(DAYS.map(d => [d, hoursField])) as Record<(typeof DAYS)[number], typeof hoursField>),
});
type Values = z.infer<typeof schema>;

const blankHours = Object.fromEntries(DAYS.map(d => [d, ''])) as Values['hours'];
const blank: Values = { name: '', categoryId: '', description: '', latitude: '', longitude: '', minutes: '90', cost: '', images: '', isOutdoor: false, isPublished: false, hours: blankHours };

const fromAttraction = (a: Attraction): Values => ({
  name: a.name, categoryId: a.category.id, description: a.description, latitude: String(a.latitude), longitude: String(a.longitude),
  minutes: String(a.typical_duration_minutes), cost: minorToRupees(a.estimated_cost_minor), images: a.images.join('\n'),
  isOutdoor: a.is_outdoor, isPublished: a.is_published,
  hours: Object.fromEntries(DAYS.map(d => [d, hoursToText(a.opening_hours, d)])) as Values['hours'],
});

function buildHours(h: Values['hours']): OpeningHours | null {
  const out: OpeningHours = {};
  for (const d of DAYS) { const spans = parseDayHours(h[d]); if (spans !== undefined) out[d] = spans; }
  return Object.keys(out).length ? out : null; // nothing entered = unknown, never assumed
}

export default function AttractionFormDialog({ open, onOpenChange, destinationId, attraction, categories }: {
  open: boolean; onOpenChange: (o: boolean) => void; destinationId: string; attraction: Attraction | null; categories: Category[];
}) {
  const save = useSaveAttraction();
  const { register, handleSubmit, reset, watch, setValue, formState: { errors } } = useForm<Values>({ resolver: zodResolver(schema), defaultValues: blank });
  useEffect(() => { if (open) reset(attraction ? fromAttraction(attraction) : blank); }, [open, attraction, reset]);
  const v = watch();

  const onSubmit = (f: Values) => {
    const data = {
      name: f.name, category_id: f.categoryId, description: f.description,
      latitude: Number(f.latitude), longitude: Number(f.longitude), typical_duration_minutes: Number(f.minutes),
      estimated_cost_minor: rupeesToMinor(f.cost), images: splitList(f.images),
      is_outdoor: f.isOutdoor, is_published: f.isPublished, opening_hours: buildHours(f.hours),
    };
    save.mutate({ id: attraction?.id, data: attraction ? data : { ...data, destination_id: destinationId } }, {
      onSuccess: () => { toast.success(attraction ? 'Attraction updated' : 'Attraction created'); onOpenChange(false); },
      onError: e => toast.error(e instanceof ApiError ? e.message : 'Could not save attraction'),
    });
  };
  const err = (m?: string) => m && <p className="text-xs text-destructive" role="alert">{m}</p>;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="font-display">{attraction ? 'Edit Attraction' : 'Add Attraction'}</DialogTitle>
          <DialogDescription>Leave opening hours blank if they are not verified; they are never assumed.</DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" noValidate>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="space-y-2"><Label htmlFor="a-name">Name</Label><Input id="a-name" {...register('name')} />{err(errors.name?.message)}</div>
            <div className="space-y-2">
              <Label htmlFor="a-cat">Category</Label>
              <Select value={v.categoryId || undefined} onValueChange={x => setValue('categoryId', x, { shouldValidate: true })}>
                <SelectTrigger id="a-cat"><SelectValue placeholder="Select a category" /></SelectTrigger>
                <SelectContent>{categories.map(c => <SelectItem key={c.id} value={c.id}>{c.name}</SelectItem>)}</SelectContent>
              </Select>
              {err(errors.categoryId?.message)}
            </div>
            <div className="space-y-2"><Label htmlFor="a-lat">Latitude</Label><Input id="a-lat" inputMode="decimal" {...register('latitude')} />{err(errors.latitude?.message)}</div>
            <div className="space-y-2"><Label htmlFor="a-lng">Longitude</Label><Input id="a-lng" inputMode="decimal" {...register('longitude')} />{err(errors.longitude?.message)}</div>
            <div className="space-y-2"><Label htmlFor="a-min">Typical visit (minutes)</Label><Input id="a-min" inputMode="numeric" {...register('minutes')} />{err(errors.minutes?.message)}</div>
            <div className="space-y-2"><Label htmlFor="a-cost">Entry cost (₹, blank = unknown)</Label><Input id="a-cost" inputMode="decimal" {...register('cost')} />{err(errors.cost?.message)}</div>
          </div>
          <div className="space-y-2"><Label htmlFor="a-desc">Description</Label><Textarea id="a-desc" rows={3} {...register('description')} /></div>
          <div className="space-y-2"><Label htmlFor="a-img">Image URLs (one per line)</Label><Textarea id="a-img" rows={2} {...register('images')} />{err(errors.images?.message)}</div>
          <details className="rounded-lg border border-border/50 p-3">
            <summary className="cursor-pointer text-sm font-medium">Opening hours (optional)</summary>
            <p className="text-xs text-muted-foreground my-2">Format: 09:00-17:00 (several ranges separated by commas), “closed”, or blank for unknown.</p>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {DAYS.map(d => (
                <div key={d} className="space-y-1">
                  <Label htmlFor={`h-${d}`} className="uppercase text-xs">{d}</Label>
                  <Input id={`h-${d}`} {...register(`hours.${d}`)} />
                  {err(errors.hours?.[d]?.message)}
                </div>
              ))}
            </div>
          </details>
          <div className="flex flex-wrap gap-6">
            <div className="flex items-center gap-3"><Switch id="a-out" checked={v.isOutdoor} onCheckedChange={x => setValue('isOutdoor', x)} /><Label htmlFor="a-out">Outdoor</Label></div>
            <div className="flex items-center gap-3"><Switch id="a-pub" checked={v.isPublished} onCheckedChange={x => setValue('isPublished', x)} /><Label htmlFor="a-pub">Published</Label></div>
          </div>
          <div className="flex justify-end gap-3">
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>Cancel</Button>
            <Button type="submit" disabled={save.isPending} className="gradient-primary text-primary-foreground">{save.isPending ? 'Saving…' : attraction ? 'Save Changes' : 'Create'}</Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
