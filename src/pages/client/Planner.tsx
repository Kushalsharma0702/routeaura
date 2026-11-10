import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Loader2, Wand2 } from 'lucide-react';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Textarea } from '@/components/ui/textarea';
import { ErrorState } from '@/components/QueryState';
import { ApiError } from '@/lib/api/client';
import type { TripRequest } from '@/lib/api/itineraries';
import { numField, rupeesToMinor, splitList, toNum } from '@/lib/forms';
import { useDestinations } from '@/hooks/useCatalog';
import { useGenerate } from '@/hooks/useItineraries';
import { usePreferences } from '@/hooks/useUsers';

const STYLES = ['budget', 'comfort', 'luxury', 'adventure', 'relaxed'];
const STAYS = ['hotel', 'hostel', 'resort', 'homestay'];
const NONE = 'none';

const schema = z.object({
  destination: z.string().min(1, 'Choose a destination'),
  days: numField({ label: 'Days', min: 1, max: 14, int: true }),
  startDate: z.string(), endDate: z.string(),
  travelers: numField({ label: 'Travelers', min: 1, max: 20, int: true, required: true }),
  budget: numField({ label: 'Budget', min: 0, max: 100_000_000 }),
  interests: z.string(), style: z.string(), stay: z.string(), prompt: z.string().max(1000),
  startName: z.string().max(120), startLat: numField({ label: 'Latitude', min: -90, max: 90 }), startLng: numField({ label: 'Longitude', min: -180, max: 180 }),
}).superRefine((v, ctx) => {
  if (!v.days && !(v.startDate && v.endDate) && !v.prompt.trim()) ctx.addIssue({ code: 'custom', path: ['days'], message: 'Enter the number of days or both dates' });
  if (v.endDate && !v.startDate) ctx.addIssue({ code: 'custom', path: ['startDate'], message: 'Start date is required with an end date' });
  if (v.startDate && v.endDate && v.endDate < v.startDate) ctx.addIssue({ code: 'custom', path: ['endDate'], message: 'End date must not be before the start date' });
  const hasStart = [v.startName, v.startLat, v.startLng].filter(Boolean).length;
  if (hasStart && hasStart < 3) ctx.addIssue({ code: 'custom', path: ['startName'], message: 'Give the start place a name, latitude and longitude, or clear all three' });
});
type Values = z.infer<typeof schema>;
const blank: Values = { destination: '', days: '3', startDate: '', endDate: '', travelers: '1', budget: '', interests: '', style: NONE, stay: NONE, prompt: '', startName: '', startLat: '', startLng: '' };

export default function Planner() {
  const navigate = useNavigate();
  const dests = useDestinations({ page: 1, page_size: 100, sort: 'name' });
  const prefs = usePreferences();
  const generate = useGenerate();
  const [seconds, setSeconds] = useState(0);
  const { register, handleSubmit, reset, setValue, watch, formState: { errors } } = useForm<Values>({ resolver: zodResolver(schema), defaultValues: blank });
  const v = watch();

  useEffect(() => {
    if (prefs.data) reset(prev => ({ ...prev, interests: prefs.data.interests.join(', '), style: prefs.data.travel_style ?? NONE, stay: prefs.data.accommodation_preference ?? NONE,
      travelers: prefs.data.group_size ? String(prefs.data.group_size) : prev.travelers, days: prefs.data.trip_duration_days ? String(prefs.data.trip_duration_days) : prev.days }));
  }, [prefs.data, reset]);
  useEffect(() => {
    if (!generate.isPending) { setSeconds(0); return; }
    const t = setInterval(() => setSeconds(s => s + 1), 1000);
    return () => clearInterval(t);
  }, [generate.isPending]);

  const onSubmit = (f: Values) => {
    const req: TripRequest = {
      destination_id: f.destination, travelers: Number(f.travelers),
      ...(f.startDate && f.endDate ? { start_date: f.startDate, end_date: f.endDate } : f.startDate ? { start_date: f.startDate, days: toNum(f.days) ?? undefined } : { days: toNum(f.days) ?? undefined }),
      ...(f.budget ? { budget_total_minor: rupeesToMinor(f.budget) ?? undefined } : {}),
      interests: splitList(f.interests).map(s => s.toLowerCase()),
      ...(f.style !== NONE ? { travel_style: f.style } : {}), ...(f.stay !== NONE ? { accommodation_preference: f.stay } : {}),
      ...(f.prompt.trim() ? { prompt: f.prompt.trim() } : {}),
      ...(f.startName && f.startLat && f.startLng ? { start_location: { name: f.startName, lat: Number(f.startLat), lng: Number(f.startLng) } } : {}),
    };
    generate.mutate(req, {
      onSuccess: it => { toast.success('Itinerary created'); navigate(`/dashboard/itineraries/${it.id}`); },
      onError: e => toast.error(e instanceof ApiError ? e.message : 'Could not create the itinerary'),
    });
  };
  const err = (m?: string) => m && <p className="text-xs text-destructive" role="alert">{m}</p>;

  return (
    <div className="space-y-6 pb-24 lg:pb-0 max-w-3xl">
      <div>
        <h1 className="text-2xl font-display font-bold text-foreground flex items-center gap-2"><Wand2 className="w-6 h-6 text-primary" />Plan a trip</h1>
        <p className="text-sm text-muted-foreground mt-1">We pick and order attractions with the recommendation engine, then check time, budget and opening-hour constraints in code.</p>
      </div>
      {dests.isError && <ErrorState message="We couldn't load destinations." onRetry={() => dests.refetch()} />}

      <form onSubmit={handleSubmit(onSubmit)} className="bg-card rounded-xl border border-border/50 shadow-card p-4 sm:p-6 space-y-5" noValidate aria-label="Trip planner">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div className="space-y-2 sm:col-span-2">
            <Label htmlFor="t-dest">Destination</Label>
            <Select value={v.destination || undefined} onValueChange={x => setValue('destination', x, { shouldValidate: true })}>
              <SelectTrigger id="t-dest"><SelectValue placeholder={dests.isLoading ? 'Loading…' : 'Choose a destination'} /></SelectTrigger>
              <SelectContent>{dests.data?.items.map(d => <SelectItem key={d.id} value={d.id}>{d.name}, {d.country}</SelectItem>)}</SelectContent>
            </Select>
            {err(errors.destination?.message)}
          </div>
          <div className="space-y-2"><Label htmlFor="t-days">Days</Label><Input id="t-days" inputMode="numeric" {...register('days')} />{err(errors.days?.message)}</div>
          <div className="space-y-2"><Label htmlFor="t-trav">Travelers</Label><Input id="t-trav" inputMode="numeric" {...register('travelers')} />{err(errors.travelers?.message)}</div>
          <div className="space-y-2"><Label htmlFor="t-start">Start date (optional)</Label><Input id="t-start" type="date" {...register('startDate')} />{err(errors.startDate?.message)}</div>
          <div className="space-y-2"><Label htmlFor="t-end">End date (optional)</Label><Input id="t-end" type="date" {...register('endDate')} />{err(errors.endDate?.message)}</div>
          <div className="space-y-2"><Label htmlFor="t-budget">Total budget (₹, optional)</Label><Input id="t-budget" inputMode="decimal" {...register('budget')} />{err(errors.budget?.message)}</div>
          <div className="space-y-2"><Label htmlFor="t-int">Interests</Label><Input id="t-int" placeholder="history, food, adventure" {...register('interests')} /></div>
          <div className="space-y-2">
            <Label htmlFor="t-style">Travel style</Label>
            <Select value={v.style} onValueChange={x => setValue('style', x)}>
              <SelectTrigger id="t-style"><SelectValue /></SelectTrigger>
              <SelectContent><SelectItem value={NONE}>No preference</SelectItem>{STYLES.map(s => <SelectItem key={s} value={s} className="capitalize">{s}</SelectItem>)}</SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label htmlFor="t-stay">Accommodation</Label>
            <Select value={v.stay} onValueChange={x => setValue('stay', x)}>
              <SelectTrigger id="t-stay"><SelectValue /></SelectTrigger>
              <SelectContent><SelectItem value={NONE}>No preference</SelectItem>{STAYS.map(s => <SelectItem key={s} value={s} className="capitalize">{s}</SelectItem>)}</SelectContent>
            </Select>
          </div>
        </div>
        <details className="rounded-lg border border-border/50 p-3">
          <summary className="cursor-pointer text-sm font-medium">Starting point and free-text request (optional)</summary>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mt-3">
            <div className="space-y-2"><Label htmlFor="t-sn">Start place</Label><Input id="t-sn" placeholder="Hotel name" {...register('startName')} />{err(errors.startName?.message)}</div>
            <div className="space-y-2"><Label htmlFor="t-sla">Latitude</Label><Input id="t-sla" inputMode="decimal" {...register('startLat')} />{err(errors.startLat?.message)}</div>
            <div className="space-y-2"><Label htmlFor="t-slo">Longitude</Label><Input id="t-slo" inputMode="decimal" {...register('startLng')} />{err(errors.startLng?.message)}</div>
          </div>
          <div className="space-y-2 mt-4">
            <Label htmlFor="t-prompt">Describe your trip in your own words</Label>
            <Textarea id="t-prompt" rows={3} placeholder="Five days for two, history and local food…" {...register('prompt')} />
            <p className="text-xs text-muted-foreground">Used only when an AI provider is configured; otherwise the form fields above are used and you will be told.</p>
          </div>
        </details>
        <Button type="submit" disabled={generate.isPending} className="gradient-primary text-primary-foreground gap-2">
          {generate.isPending ? <><Loader2 className="w-4 h-4 animate-spin" />Planning…</> : <><Wand2 className="w-4 h-4" />Create itinerary</>}
        </Button>
        {generate.isPending && (
          <div role="status" aria-live="polite" className="rounded-lg bg-muted/50 p-3 text-sm text-muted-foreground">
            Ranking attractions, planning days and checking constraints… {seconds}s
            <p className="text-xs mt-1">The step-by-step log with timings is shown on the itinerary when it is ready.</p>
          </div>
        )}
      </form>
    </div>
  );
}
