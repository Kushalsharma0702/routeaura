import { useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { AlertTriangle, ArrowDown, ArrowLeft, ArrowUp, Bot, Check, Clock, Cpu, History, Lock, LockOpen, Plus, RefreshCw, Save, Trash2, Wallet } from 'lucide-react';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Skeleton } from '@/components/ui/skeleton';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import ConfirmDialog from '@/components/admin/ConfirmDialog';
import ContextPanel from '@/components/itinerary/ContextPanel';
import ItineraryMap from '@/components/itinerary/ItineraryMap';
import { dayColor } from '@/lib/mapColors';
import OptimizationPanel from '@/components/itinerary/OptimizationPanel';
import { EmptyState, ErrorState } from '@/components/QueryState';
import { ApiError } from '@/lib/api/client';
import { itinerariesApi, type Activity, type DayPlan, type Itinerary } from '@/lib/api/itineraries';
import { formatDistance, formatDuration, formatMinor } from '@/lib/format';
import { rupeesToMinor, splitList } from '@/lib/forms';
import { useAttractions } from '@/hooks/useCatalog';
import { useDeleteItinerary, useItinerary, useItineraryMutation, useVersions } from '@/hooks/useItineraries';

const errMsg = (e: unknown) => (e instanceof ApiError ? e.message : 'Something went wrong. Please try again.');
const HOURS_LABEL = { verified_open: 'Open (verified)', verified_closed: 'Closed (verified)', unknown: 'Opening hours not verified' } as const;

function ActivityCard({ a, it, onRemove, onMove, onDuration, onLock, busy }: {
  a: Activity; it: Itinerary; busy: boolean; onRemove: () => void; onMove: (dir: -1 | 1) => void; onDuration: (m: number) => void; onLock: () => void;
}) {
  const day = it.day_plans[a.day_number - 1];
  return (
    <li className="bg-card rounded-xl border border-border/50 shadow-card p-4 space-y-2" aria-label={a.attraction.name}>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-xs text-muted-foreground flex items-center gap-1"><Clock className="w-3.5 h-3.5" /><time>{a.start_time}</time>–<time>{a.end_time}</time> · {formatDuration(a.duration_min)}{a.source === 'user' && <span className="ml-1 px-1.5 rounded bg-primary/10 text-primary">added by you</span>}</p>
          <h4 className="font-semibold text-card-foreground">{a.attraction.name}</h4>
          <p className="text-xs text-muted-foreground">{a.attraction.category} · {a.attraction.is_outdoor ? 'Outdoor' : 'Indoor'}</p>
        </div>
        <div className="flex gap-1 shrink-0">
          <Button size="icon" variant="ghost" aria-label={`Move ${a.attraction.name} earlier`} disabled={busy || a.position === 1} onClick={() => onMove(-1)}><ArrowUp className="w-4 h-4" /></Button>
          <Button size="icon" variant="ghost" aria-label={`Move ${a.attraction.name} later`} disabled={busy || a.position === day.activities.length} onClick={() => onMove(1)}><ArrowDown className="w-4 h-4" /></Button>
          <Button size="icon" variant="ghost" aria-label={a.locked ? `Unlock ${a.attraction.name}` : `Lock ${a.attraction.name} (keep in optimizations)`} aria-pressed={a.locked} disabled={busy} onClick={onLock}>{a.locked ? <Lock className="w-4 h-4 text-primary" /> : <LockOpen className="w-4 h-4" />}</Button>
          <Button size="icon" variant="ghost" aria-label={`Remove ${a.attraction.name}`} disabled={busy} onClick={onRemove}><Trash2 className="w-4 h-4 text-destructive" /></Button>
        </div>
      </div>
      <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
        {a.travel_min > 0 && <span>~{a.travel_min} min / {formatDistance(a.travel_m)} from previous stop ({a.travel_source})</span>}
        <span>{a.cost_minor == null ? 'Entry fee unknown (not included in totals)' : `${formatMinor(a.cost_minor)} per person · ${formatMinor(a.cost_total_minor)} total`}</span>
        <span>{HOURS_LABEL[a.hours_status]}</span>
        {a.wait_min > 0 && <span>Wait {a.wait_min} min for opening</span>}
      </div>
      {a.explanation.llm?.rationale && <p className="text-xs text-card-foreground"><Bot className="w-3.5 h-3.5 inline mr-1" />{a.explanation.llm.rationale}</p>}
      <ul className="text-xs space-y-1">
        {(a.explanation.reasons ?? []).slice(0, 2).map(r => <li key={r} className="flex gap-1.5"><Check className="w-3.5 h-3.5 text-success shrink-0 mt-0.5" />{r}</li>)}
        {(a.explanation.cautions ?? []).slice(0, 1).map(r => <li key={r} className="flex gap-1.5 text-muted-foreground"><AlertTriangle className="w-3.5 h-3.5 text-warning shrink-0 mt-0.5" />{r}</li>)}
      </ul>
      <div className="flex items-center gap-2">
        <Label htmlFor={`dur-${a.id}`} className="text-xs">Visit length (min)</Label>
        <Input id={`dur-${a.id}`} className="h-8 w-20" type="number" min={5} max={1440} defaultValue={a.duration_min} disabled={busy}
          onBlur={e => { const n = Number(e.target.value); if (n >= 5 && n <= 1440 && n !== a.duration_min) onDuration(n); }} />
      </div>
    </li>
  );
}

function AddActivityDialog({ it, open, onOpenChange, onAdd }: { it: Itinerary; open: boolean; onOpenChange: (o: boolean) => void; onAdd: (attractionId: string, day: number) => void }) {
  const [attraction, setAttraction] = useState('');
  const [day, setDay] = useState('1');
  const { data, isLoading } = useAttractions({ destination_id: it.destination.id, page_size: 100 }, open);
  const used = new Set(it.day_plans.flatMap(d => d.activities.map(a => a.attraction.id)));
  const options = data?.items.filter(a => !used.has(a.id)) ?? [];
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader><DialogTitle>Add an attraction</DialogTitle><DialogDescription>Only published attractions of {it.destination.name} that are not already in the trip.</DialogDescription></DialogHeader>
        <div className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="add-att">Attraction</Label>
            <Select value={attraction || undefined} onValueChange={setAttraction}>
              <SelectTrigger id="add-att"><SelectValue placeholder={isLoading ? 'Loading…' : options.length ? 'Choose an attraction' : 'Everything is already added'} /></SelectTrigger>
              <SelectContent>{options.map(a => <SelectItem key={a.id} value={a.id}>{a.name}</SelectItem>)}</SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label htmlFor="add-day">Day</Label>
            <Select value={day} onValueChange={setDay}>
              <SelectTrigger id="add-day"><SelectValue /></SelectTrigger>
              <SelectContent>{Array.from({ length: it.days }, (_, i) => <SelectItem key={i} value={String(i + 1)}>Day {i + 1}</SelectItem>)}</SelectContent>
            </Select>
          </div>
          <Button disabled={!attraction} className="gradient-primary text-primary-foreground" onClick={() => { onAdd(attraction, Number(day)); setAttraction(''); onOpenChange(false); }}>Add to trip</Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

function RegenerateDialog({ it, open, onOpenChange, onSubmit }: { it: Itinerary; open: boolean; onOpenChange: (o: boolean) => void; onSubmit: (b: { interests?: string[]; budget_total_minor?: number }) => void }) {
  const [interests, setInterests] = useState(it.interests.join(', '));
  const [budget, setBudget] = useState(it.budget_total_minor != null ? String(it.budget_total_minor / 100) : '');
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader><DialogTitle>Regenerate itinerary</DialogTitle><DialogDescription>Replaces all activities. Your current version stays in the history and can be restored.</DialogDescription></DialogHeader>
        <div className="space-y-4">
          <div className="space-y-2"><Label htmlFor="rg-int">Interests</Label><Input id="rg-int" value={interests} onChange={e => setInterests(e.target.value)} /></div>
          <div className="space-y-2"><Label htmlFor="rg-bud">Total budget (₹)</Label><Input id="rg-bud" inputMode="decimal" value={budget} onChange={e => setBudget(e.target.value)} /></div>
          <Button className="gradient-primary text-primary-foreground" onClick={() => { onSubmit({ interests: splitList(interests).map(s => s.toLowerCase()), ...(budget ? { budget_total_minor: rupeesToMinor(budget) ?? undefined } : {}) }); onOpenChange(false); }}>Regenerate</Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

export default function ItineraryDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const q = useItinerary(id);
  const it = q.data;
  const versions = useVersions(id, it?.current_version);
  const del = useDeleteItinerary();
  const [addOpen, setAddOpen] = useState(false);
  const [regenOpen, setRegenOpen] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [title, setTitle] = useState<string | null>(null);

  const run = <V,>(fn: (v: V) => Promise<Itinerary>) => useItineraryMutation<V>(id ?? '', fn); // eslint-disable-line react-hooks/rules-of-hooks
  const update = run((b: Parameters<typeof itinerariesApi.update>[1]) => itinerariesApi.update(id!, b));
  const regenerate = run((b: Parameters<typeof itinerariesApi.regenerate>[1]) => itinerariesApi.regenerate(id!, b));
  const add = run((b: Parameters<typeof itinerariesApi.addActivity>[1]) => itinerariesApi.addActivity(id!, b));
  const remove = run((aid: string) => itinerariesApi.removeActivity(id!, aid));
  const patch = run((v: { aid: string; duration_min: number }) => itinerariesApi.updateActivity(id!, v.aid, { duration_min: v.duration_min }));
  const lock = run((v: { aid: string; locked: boolean }) => itinerariesApi.updateActivity(id!, v.aid, { locked: v.locked }));
  const reorder = run((days: { day_number: number; activity_ids: string[] }[]) => itinerariesApi.reorder(id!, days));
  const restore = run((version: number) => itinerariesApi.restore(id!, version));
  const busy = [update, regenerate, add, remove, patch, lock, reorder, restore].some(m => m.isPending);
  const done = (msg: string) => ({ onSuccess: () => toast.success(msg), onError: (e: unknown) => toast.error(errMsg(e)) });

  if (q.isLoading) return <div className="space-y-4" role="status" aria-label="Loading"><Skeleton className="h-10 w-72" /><Skeleton className="h-64 rounded-xl" /></div>;
  if (q.isError || !it) {
    const nf = q.error instanceof ApiError && q.error.status === 404;
    return <div className="space-y-4"><Link to="/dashboard/itineraries" className="inline-flex items-center gap-1.5 text-sm text-muted-foreground"><ArrowLeft className="w-4 h-4" />My trips</Link>
      {nf ? <EmptyState title="Trip not found" hint="It may have been deleted." /> : <ErrorState message="We couldn't load this trip." onRetry={() => q.refetch()} />}</div>;
  }

  const moveWithin = (day: DayPlan, a: Activity, dir: -1 | 1) => {
    const ids = day.activities.map(x => x.id);
    const i = ids.indexOf(a.id);
    [ids[i], ids[i + dir]] = [ids[i + dir], ids[i]];
    reorder.mutate(it.day_plans.map(d => ({ day_number: d.day_number, activity_ids: d.day_number === day.day_number ? ids : d.activities.map(x => x.id) })), done('Order updated'));
  };
  const b = it.budget;
  const ai = it.generation_source === 'llm';

  return (
    <div className="space-y-6 pb-24 lg:pb-0">
      <Link to="/dashboard/itineraries" className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground"><ArrowLeft className="w-4 h-4" />My trips</Link>

      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="space-y-1 min-w-0">
          <Label htmlFor="trip-title" className="sr-only">Trip title</Label>
          <Input id="trip-title" className="text-2xl font-display font-bold h-auto py-1 border-transparent hover:border-input focus-visible:border-input" value={title ?? it.title}
            onChange={e => setTitle(e.target.value)} onBlur={() => { if (title !== null && title.trim() && title !== it.title) update.mutate({ title: title.trim() }, done('Title saved')); setTitle(null); }} />
          <p className="text-sm text-muted-foreground">{it.destination.name} · {it.days} days · {it.traveler_count} traveler{it.traveler_count === 1 ? '' : 's'}{it.start_date ? ` · from ${it.start_date}` : ''}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant={it.status === 'saved' ? 'secondary' : 'default'} className="gap-2" disabled={busy}
            onClick={() => update.mutate({ status: it.status === 'saved' ? 'draft' : 'saved' }, done(it.status === 'saved' ? 'Moved back to drafts' : 'Itinerary saved'))}>
            <Save className="w-4 h-4" />{it.status === 'saved' ? 'Saved' : 'Save itinerary'}
          </Button>
          <Button variant="outline" className="gap-2" disabled={busy} onClick={() => setRegenOpen(true)}><RefreshCw className="w-4 h-4" />Regenerate</Button>
          <Button variant="outline" className="gap-2" disabled={busy} onClick={() => setAddOpen(true)}><Plus className="w-4 h-4" />Add attraction</Button>
          <Button variant="outline" size="icon" aria-label="Delete itinerary" onClick={() => setConfirmDelete(true)}><Trash2 className="w-4 h-4 text-destructive" /></Button>
        </div>
      </div>

      <div className="rounded-xl border border-border/50 bg-muted/40 p-4 text-sm space-y-2">
        <p className="flex items-center gap-2 font-medium">{ai ? <Bot className="w-4 h-4 text-primary" /> : <Cpu className="w-4 h-4 text-primary" />}
          {ai ? `Day groupings suggested by an AI model (${it.generation_info.llm?.model}); times and costs computed by the app.` : 'Generated by the app’s deterministic planner (no AI model was used).'}</p>
        <ul className="text-xs text-muted-foreground space-y-1">{(it.generation_info.notes ?? []).filter(n => !n.startsWith('This itinerary was generated by the app')).map(n => <li key={n}>• {n}</li>)}</ul>
        <details><summary className="text-xs cursor-pointer text-primary">How this was generated</summary>
          <ol className="mt-2 text-xs space-y-1">{(it.generation_info.steps ?? []).map(s => <li key={s.step}>{s.status === 'ok' ? '✓' : '✗'} {s.step.replace(/_/g, ' ')} · {s.ms} ms · {s.detail}</li>)}</ol>
          {it.generation_info.travel_times && <p className="text-xs mt-2">Travel times: {it.generation_info.travel_times}.</p>}
        </details>
      </div>

      {it.violations.length > 0 && (
        <div role="alert" className="rounded-xl border border-destructive/30 bg-destructive/5 p-4 text-sm space-y-1">
          <p className="font-medium flex items-center gap-2"><AlertTriangle className="w-4 h-4 text-destructive" />This itinerary has {it.violations.length} issue{it.violations.length === 1 ? '' : 's'}</p>
          <ul className="text-xs space-y-1">{it.violations.map(v => <li key={v.message}>• {v.message}</li>)}</ul>
        </div>
      )}

      <section aria-label="Budget breakdown" className="bg-card rounded-xl border border-border/50 shadow-card p-4 space-y-2">
        <h2 className="font-display font-semibold flex items-center gap-2"><Wallet className="w-4 h-4 text-primary" />Budget breakdown</h2>
        <dl className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-sm">
          <div><dt className="text-xs text-muted-foreground">Activities (known fees)</dt><dd className="font-semibold">{formatMinor(b.activities_minor)}</dd></div>
          <div><dt className="text-xs text-muted-foreground">Living estimate</dt><dd className="font-semibold">{b.living_estimate_minor == null ? 'Not available' : formatMinor(b.living_estimate_minor)}</dd></div>
          <div><dt className="text-xs text-muted-foreground">Estimated total</dt><dd className="font-semibold">{formatMinor(b.total_estimate_minor)}</dd></div>
          <div><dt className="text-xs text-muted-foreground">Your budget</dt><dd className={`font-semibold ${b.within_budget === false ? 'text-destructive' : ''}`}>{b.budget_minor == null ? 'Not set' : `${formatMinor(b.budget_minor)} (${b.deviation_pct! > 0 ? '+' : ''}${b.deviation_pct}%)`}</dd></div>
        </dl>
        <p className="text-xs text-muted-foreground">{b.unknown_cost_items > 0 ? `${b.unknown_cost_items} activit${b.unknown_cost_items === 1 ? 'y has' : 'ies have'} no known entry fee and ${b.unknown_cost_items === 1 ? 'is' : 'are'} not included. ` : ''}{b.note}</p>
      </section>

      <Tabs defaultValue="day-1">
        <TabsList className="flex flex-wrap h-auto">{it.day_plans.map(d => <TabsTrigger key={d.day_number} value={`day-${d.day_number}`}>Day {d.day_number}{d.date ? ` · ${d.date}` : ''}</TabsTrigger>)}</TabsList>
        {it.day_plans.map(d => (
          <TabsContent key={d.day_number} value={`day-${d.day_number}`} className="mt-4 space-y-3">
            {d.activities.length === 0 && <EmptyState title="Nothing planned for this day" hint="Use “Add attraction” to fill it." />}
            <ol className="space-y-3">
              {d.activities.map(a => <ActivityCard key={a.id} a={a} it={it} busy={busy} onRemove={() => remove.mutate(a.id, done('Activity removed'))}
                onMove={dir => moveWithin(d, a, dir)} onDuration={m => patch.mutate({ aid: a.id, duration_min: m }, done('Visit length updated'))} onLock={() => lock.mutate({ aid: a.id, locked: !a.locked }, done(a.locked ? 'Activity unlocked' : 'Activity locked: optimizations will keep it'))} />)}
            </ol>
            {d.activities.length > 0 && <p className="text-xs text-muted-foreground">Lunch is scheduled around {d.lunch_start_min == null ? '13:00' : `${String(Math.floor(d.lunch_start_min / 60)).padStart(2, '0')}:${String(d.lunch_start_min % 60).padStart(2, '0')}`} · day ends at {d.ends_at}</p>}
          </TabsContent>
        ))}
      </Tabs>

      <Tabs defaultValue="map">
        <TabsList>
          <TabsTrigger value="map">Map</TabsTrigger>
          <TabsTrigger value="optimize">Optimize route</TabsTrigger>
          <TabsTrigger value="conditions">Conditions</TabsTrigger>
        </TabsList>
        <TabsContent value="map" className="mt-4 space-y-2">
          {it.day_plans.some(d => d.activities.length > 0)
            ? <ItineraryMap start={it.start_location ?? { name: `${it.destination.name} centre`, lat: it.destination.latitude, lng: it.destination.longitude }}
                routes={it.day_plans.filter(d => d.activities.length).map(d => ({ key: `d${d.day_number}`, color: dayColor(d.day_number), title: `Day ${d.day_number}`,
                  stops: d.activities.map(a => ({ id: a.id, name: a.attraction.name, lat: a.attraction.latitude, lng: a.attraction.longitude })) }))} />
            : <EmptyState title="Nothing to show on the map" hint="Add activities to see the route." />}
          <p className="text-xs text-muted-foreground">Lines join stops in visiting order; they are not road routes. Travel times: {(it.generation_info.routing as { source?: string } | undefined)?.source ?? 'estimate'}.</p>
        </TabsContent>
        <TabsContent value="optimize" className="mt-4"><OptimizationPanel it={it} /></TabsContent>
        <TabsContent value="conditions" className="mt-4"><ContextPanel it={it} /></TabsContent>
      </Tabs>

      <section aria-label="Version history" className="bg-card rounded-xl border border-border/50 shadow-card p-4 space-y-2">
        <h2 className="font-display font-semibold flex items-center gap-2"><History className="w-4 h-4 text-primary" />Version history</h2>
        {versions.isLoading && <p className="text-sm text-muted-foreground">Loading…</p>}
        <ul className="space-y-2">
          {versions.data?.map(v => (
            <li key={v.version} className="flex items-center justify-between gap-3 text-sm">
              <span>v{v.version} · {v.summary} <time className="text-xs text-muted-foreground ml-2" dateTime={v.created_at}>{new Date(v.created_at).toLocaleString()}</time></span>
              {v.version === it.current_version ? <span className="text-xs text-muted-foreground">current</span>
                : <Button size="sm" variant="outline" disabled={busy} onClick={() => restore.mutate(v.version, done(`Restored version ${v.version}`))}>Restore</Button>}
            </li>
          ))}
        </ul>
      </section>

      <AddActivityDialog it={it} open={addOpen} onOpenChange={setAddOpen} onAdd={(aid, day) => add.mutate({ attraction_id: aid, day_number: day }, done('Attraction added'))} />
      {regenOpen && <RegenerateDialog it={it} open={regenOpen} onOpenChange={setRegenOpen} onSubmit={body => regenerate.mutate(body, done('Itinerary regenerated'))} />}
      <ConfirmDialog open={confirmDelete} onOpenChange={setConfirmDelete} title="Delete this trip?" description="It will be removed from your trips."
        onConfirm={() => del.mutate(it.id, { onSuccess: () => { toast.success('Trip deleted'); navigate('/dashboard/itineraries'); }, onError: e => toast.error(errMsg(e)) })} />
    </div>
  );
}
