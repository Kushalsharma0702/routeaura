import { useEffect } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Switch } from '@/components/ui/switch';
import { Textarea } from '@/components/ui/textarea';
import { ApiError } from '@/lib/api/client';
import type { Category, Destination } from '@/lib/api/catalog';
import { imageList, minorToRupees, numField, rupeesToMinor, splitList, toNum } from '@/lib/forms';
import { useSaveDestination } from '@/hooks/useCatalog';

const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
const CLIMATES = ['tropical', 'temperate', 'cold', 'arid', 'any'];
const NONE = 'none';

const schema = z.object({
  name: z.string().trim().min(2, 'At least 2 characters').max(120),
  country: z.string().trim().min(2, 'At least 2 characters').max(80),
  region: z.string().trim().max(80),
  description: z.string().max(5000),
  latitude: numField({ label: 'Latitude', min: -90, max: 90, required: true }),
  longitude: numField({ label: 'Longitude', min: -180, max: 180, required: true }),
  cost: numField({ label: 'Cost', min: 0, max: 10_000_000 }),
  days: numField({ label: 'Days', min: 1, max: 60, int: true }),
  seasonStart: z.string(), seasonEnd: z.string(),
  climate: z.string(), climateNotes: z.string().max(300), accessibility: z.string().max(500),
  images: imageList,
  isPublished: z.boolean(),
  categoryIds: z.array(z.string()),
}).refine(v => (v.seasonStart === NONE) === (v.seasonEnd === NONE), { message: 'Set both season months, or neither', path: ['seasonEnd'] });
type Values = z.infer<typeof schema>;

const blank: Values = {
  name: '', country: '', region: '', description: '', latitude: '', longitude: '', cost: '', days: '',
  seasonStart: NONE, seasonEnd: NONE, climate: NONE, climateNotes: '', accessibility: '', images: '',
  isPublished: false, categoryIds: [],
};

const fromDestination = (d: Destination): Values => ({
  name: d.name, country: d.country, region: d.region ?? '', description: d.description,
  latitude: String(d.latitude), longitude: String(d.longitude), cost: minorToRupees(d.estimated_cost_per_day_minor),
  days: d.recommended_duration_days?.toString() ?? '',
  seasonStart: d.best_season_start_month?.toString() ?? NONE, seasonEnd: d.best_season_end_month?.toString() ?? NONE,
  climate: d.climate ?? NONE, climateNotes: d.climate_notes ?? '', accessibility: d.accessibility_notes ?? '',
  images: d.images.join('\n'), isPublished: d.is_published, categoryIds: d.categories.map(c => c.id),
});

export default function DestinationFormDialog({ open, onOpenChange, destination, categories }: {
  open: boolean; onOpenChange: (o: boolean) => void; destination: Destination | null; categories: Category[];
}) {
  const save = useSaveDestination();
  const { register, handleSubmit, reset, watch, setValue, formState: { errors } } = useForm<Values>({
    resolver: zodResolver(schema), defaultValues: blank,
  });
  useEffect(() => { if (open) reset(destination ? fromDestination(destination) : blank); }, [open, destination, reset]);
  const v = watch();

  const onSubmit = (f: Values) => {
    const data = {
      name: f.name, country: f.country, region: f.region || null, description: f.description,
      latitude: Number(f.latitude), longitude: Number(f.longitude),
      estimated_cost_per_day_minor: rupeesToMinor(f.cost), recommended_duration_days: toNum(f.days),
      best_season_start_month: f.seasonStart === NONE ? null : Number(f.seasonStart),
      best_season_end_month: f.seasonEnd === NONE ? null : Number(f.seasonEnd),
      climate: f.climate === NONE ? null : f.climate, climate_notes: f.climateNotes || null,
      accessibility_notes: f.accessibility || null, images: splitList(f.images),
      is_published: f.isPublished, category_ids: f.categoryIds,
    };
    save.mutate({ id: destination?.id, data }, {
      onSuccess: () => { toast.success(destination ? 'Destination updated' : 'Destination created'); onOpenChange(false); },
      onError: e => toast.error(e instanceof ApiError ? e.message : 'Could not save destination'),
    });
  };

  const err = (k: keyof Values) => errors[k] && <p className="text-xs text-destructive" role="alert">{String(errors[k]?.message)}</p>;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="font-display">{destination ? 'Edit Destination' : 'Add New Destination'}</DialogTitle>
          <DialogDescription>Costs and durations are estimates. Coordinates must be valid latitude/longitude.</DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" noValidate>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="space-y-2"><Label htmlFor="d-name">Name</Label><Input id="d-name" {...register('name')} />{err('name')}</div>
            <div className="space-y-2"><Label htmlFor="d-country">Country</Label><Input id="d-country" {...register('country')} />{err('country')}</div>
            <div className="space-y-2"><Label htmlFor="d-region">Region</Label><Input id="d-region" {...register('region')} /></div>
            <div className="space-y-2"><Label htmlFor="d-days">Recommended days</Label><Input id="d-days" inputMode="numeric" {...register('days')} />{err('days')}</div>
            <div className="space-y-2"><Label htmlFor="d-lat">Latitude</Label><Input id="d-lat" inputMode="decimal" placeholder="26.9124" {...register('latitude')} />{err('latitude')}</div>
            <div className="space-y-2"><Label htmlFor="d-lng">Longitude</Label><Input id="d-lng" inputMode="decimal" placeholder="75.7873" {...register('longitude')} />{err('longitude')}</div>
            <div className="space-y-2"><Label htmlFor="d-cost">Estimated cost per day (₹)</Label><Input id="d-cost" inputMode="decimal" {...register('cost')} />{err('cost')}</div>
            <div className="space-y-2">
              <Label htmlFor="d-climate">Climate</Label>
              <Select value={v.climate} onValueChange={x => setValue('climate', x)}>
                <SelectTrigger id="d-climate"><SelectValue /></SelectTrigger>
                <SelectContent><SelectItem value={NONE}>Not set</SelectItem>{CLIMATES.map(c => <SelectItem key={c} value={c} className="capitalize">{c}</SelectItem>)}</SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="d-s1">Best season from</Label>
              <Select value={v.seasonStart} onValueChange={x => setValue('seasonStart', x)}>
                <SelectTrigger id="d-s1"><SelectValue /></SelectTrigger>
                <SelectContent><SelectItem value={NONE}>Not set</SelectItem>{MONTHS.map((m, i) => <SelectItem key={m} value={String(i + 1)}>{m}</SelectItem>)}</SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="d-s2">Best season to</Label>
              <Select value={v.seasonEnd} onValueChange={x => setValue('seasonEnd', x)}>
                <SelectTrigger id="d-s2"><SelectValue /></SelectTrigger>
                <SelectContent><SelectItem value={NONE}>Not set</SelectItem>{MONTHS.map((m, i) => <SelectItem key={m} value={String(i + 1)}>{m}</SelectItem>)}</SelectContent>
              </Select>
              {err('seasonEnd')}
            </div>
          </div>
          <div className="space-y-2"><Label htmlFor="d-desc">Description</Label><Textarea id="d-desc" rows={3} {...register('description')} />{err('description')}</div>
          <div className="space-y-2"><Label htmlFor="d-cn">Climate notes</Label><Input id="d-cn" {...register('climateNotes')} /></div>
          <div className="space-y-2"><Label htmlFor="d-acc">Accessibility notes</Label><Input id="d-acc" {...register('accessibility')} /></div>
          <div className="space-y-2"><Label htmlFor="d-img">Image URLs (one per line)</Label><Textarea id="d-img" rows={3} placeholder="https://…" {...register('images')} />{err('images')}</div>
          <fieldset className="space-y-2">
            <legend className="text-sm font-medium">Categories</legend>
            {categories.length === 0 && <p className="text-xs text-muted-foreground">No categories yet. Create some with “Categories”.</p>}
            <div className="grid grid-cols-2 gap-2">
              {categories.map(c => (
                <label key={c.id} className="flex items-center gap-2 text-sm">
                  <Checkbox checked={v.categoryIds.includes(c.id)}
                    onCheckedChange={on => setValue('categoryIds', on ? [...v.categoryIds, c.id] : v.categoryIds.filter(i => i !== c.id))} />
                  {c.name}
                </label>
              ))}
            </div>
          </fieldset>
          <div className="flex items-center gap-3">
            <Switch id="d-pub" checked={v.isPublished} onCheckedChange={x => setValue('isPublished', x)} />
            <Label htmlFor="d-pub">Published (visible to travelers)</Label>
          </div>
          <div className="flex justify-end gap-3">
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>Cancel</Button>
            <Button type="submit" disabled={save.isPending} className="gradient-primary text-primary-foreground">
              {save.isPending ? 'Saving…' : destination ? 'Save Changes' : 'Create'}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
