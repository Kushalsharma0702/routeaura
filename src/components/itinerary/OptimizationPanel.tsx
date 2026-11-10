import { useState } from 'react';
import { ArrowRight, Check, Route as RouteIcon, TriangleAlert } from 'lucide-react';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { Slider } from '@/components/ui/slider';
import { Switch } from '@/components/ui/switch';
import { ApiError } from '@/lib/api/client';
import type { Itinerary } from '@/lib/api/itineraries';
import type { Optimization, Weights } from '@/lib/api/optimization';
import { formatDistance } from '@/lib/format';
import { useApplyOptimization, useOptimizationHistory, useOptimize } from '@/hooks/useRouting';
import ItineraryMap, { type MapRoute } from '@/components/itinerary/ItineraryMap';
import { dayColor } from '@/lib/mapColors';

const errMsg = (e: unknown) => (e instanceof ApiError ? e.message : 'Something went wrong. Please try again.');
const DEFAULTS: Pick<Weights, 'distance' | 'time' | 'cost' | 'preference'> = { distance: 1, time: 1, cost: 0.5, preference: 1 };
const LABELS: Record<keyof typeof DEFAULTS, string> = { distance: 'Travel distance', time: 'Travel time', cost: 'Travel cost', preference: 'Keep my preferences' };

const routesOf = (view: Optimization['before'], dashed: boolean): MapRoute[] =>
  view.days.filter(d => d.stops.length).map(d => ({ key: `${dashed ? 'o' : 'n'}${d.day}`, color: dashed ? '#64748b' : dayColor(d.day), dashed, title: `Day ${d.day}`, stops: d.stops }));

function Metric({ label, before, after, fmt }: { label: string; before: number; after: number; fmt: (n: number) => string }) {
  const better = after < before;
  return (
    <div className="rounded-lg border border-border/50 p-3 text-sm">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="font-semibold flex items-center gap-1.5">{fmt(before)} <ArrowRight className="w-3.5 h-3.5 text-muted-foreground" /> <span className={better ? 'text-success' : ''}>{fmt(after)}</span></p>
    </div>
  );
}

export default function OptimizationPanel({ it }: { it: Itinerary }) {
  const [w, setW] = useState(DEFAULTS);
  const [improve, setImprove] = useState(false);
  const [result, setResult] = useState<Optimization | null>(null);
  const optimize = useOptimize(it.id);
  const apply = useApplyOptimization(it.id);
  const history = useOptimizationHistory(it.id);
  const start = it.start_location ?? { name: `${it.destination.name} centre`, lat: it.destination.latitude, lng: it.destination.longitude };
  const hasActivities = it.day_plans.some(d => d.activities.length > 0);

  const run = () => optimize.mutate({ weights: w, improve }, { onSuccess: setResult, onError: e => toast.error(errMsg(e)) });
  const applyIt = () => result && apply.mutate(result.id, {
    onSuccess: () => { toast.success('Optimized route applied'); setResult(null); },
    onError: e => toast.error(errMsg(e)),
  });
  const o = result;
  const canApply = !!o && !o.applied && o.status !== 'infeasible' && o.after !== null;

  return (
    <section aria-label="Route optimization" className="space-y-4">
      <div className="bg-card rounded-xl border border-border/50 shadow-card p-4 space-y-4">
        <h3 className="font-display font-semibold flex items-center gap-2"><RouteIcon className="w-4 h-4 text-primary" />Optimize the route</h3>
        <p className="text-xs text-muted-foreground">Finds a better visiting order and day split with Google OR-Tools. It is a preview: nothing changes until you apply it. Activities you added or locked are always kept.</p>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {(Object.keys(DEFAULTS) as (keyof typeof DEFAULTS)[]).map(k => (
            <div key={k} className="space-y-1">
              <Label htmlFor={`w-${k}`} className="text-xs">{LABELS[k]} (weight {w[k].toFixed(1)})</Label>
              <Slider id={`w-${k}`} aria-label={`${LABELS[k]} weight`} min={0} max={5} step={0.1} value={[w[k]]} onValueChange={v => setW({ ...w, [k]: v[0] })} />
            </div>
          ))}
        </div>
        <div className="flex flex-wrap items-center gap-4">
          <div className="flex items-center gap-2"><Switch id="opt-improve" checked={improve} onCheckedChange={setImprove} /><Label htmlFor="opt-improve" className="text-sm">Search longer (not repeatable)</Label></div>
          <Button onClick={run} disabled={!hasActivities || optimize.isPending} className="gradient-primary text-primary-foreground">{optimize.isPending ? 'Optimizing…' : 'Preview optimization'}</Button>
          {!hasActivities && <span className="text-xs text-muted-foreground">Add activities first.</span>}
        </div>
      </div>

      {o && (
        <div className="bg-card rounded-xl border border-border/50 shadow-card p-4 space-y-4" aria-label="Optimization result">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h4 className="font-semibold">{o.status === 'optimized' ? 'Optimized plan' : o.status === 'relaxed' ? 'Relaxed plan (constraints could not all be met)' : 'No feasible plan'}</h4>
            <span className="text-xs text-muted-foreground">Travel data: {o.routing.source}{o.routing.live_traffic ? ' (live traffic)' : ' (no live traffic)'} · solved in {o.solver_ms} ms</span>
          </div>
          {o.routing.source === 'estimate' && <p className="text-xs text-muted-foreground flex gap-1.5"><TriangleAlert className="w-3.5 h-3.5 shrink-0 mt-0.5" />Travel times are estimates (straight-line distance with a detour factor), not road routing. Configure a routing provider for real road times.</p>}
          {o.after && o.delta && (
            <>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <Metric label={`Distance (${o.delta.distance_pct})`} before={o.before.metrics.distance_m} after={o.after.metrics.distance_m} fmt={formatDistance} />
                <Metric label={`Travel time (${o.delta.travel_pct})`} before={o.before.metrics.travel_min} after={o.after.metrics.travel_min} fmt={n => `${n} min`} />
                <Metric label="Constraint violations" before={o.before.metrics.violations.length} after={o.after.metrics.violations.length} fmt={n => String(n)} />
              </div>
              <ItineraryMap start={start} routes={[...routesOf(o.before, true), ...routesOf(o.after, false)]} />
              <p className="text-xs text-muted-foreground">Dashed grey: current order · coloured: optimized order. Lines join stops in order; they are not roads.</p>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
                {([['Current', o.before], ['Optimized', o.after]] as const).map(([title, view]) => (
                  <div key={title}><p className="font-medium mb-1">{title}</p>
                    <ol className="space-y-1 text-xs">{view.days.map(d => <li key={d.day}><strong>Day {d.day}:</strong> {d.stops.length ? d.stops.map(s => s.name).join(' → ') : '—'}</li>)}</ol></div>
                ))}
              </div>
            </>
          )}
          <ul className="text-sm space-y-1" aria-label="What changed">{o.changes.map(c => <li key={c} className="flex gap-2"><Check className="w-4 h-4 text-success shrink-0 mt-0.5" />{c}</li>)}</ul>
          {o.dropped.length > 0 && <ul className="text-xs text-muted-foreground space-y-1">{o.dropped.map(d => <li key={d.id}>Would remove {d.name}: {d.reason}</li>)}</ul>}
          {o.notes.filter(n => !n.includes('great-circle')).length > 0 && <ul className="text-xs text-muted-foreground space-y-1">{o.notes.filter(n => !n.includes('great-circle')).map(n => <li key={n}>• {n}</li>)}</ul>}
          {o.after && o.after.metrics.violations.length > 0 && <ul role="alert" className="text-xs text-destructive space-y-1">{o.after.metrics.violations.map(v => <li key={v.message}>• {v.message}</li>)}</ul>}
          <div className="flex gap-3">
            <Button onClick={applyIt} disabled={!canApply || apply.isPending} className="gradient-primary text-primary-foreground">{apply.isPending ? 'Applying…' : 'Apply this route'}</Button>
            <Button variant="outline" onClick={() => setResult(null)}>Discard preview</Button>
          </div>
        </div>
      )}

      {history.data && history.data.length > 0 && (
        <div className="text-xs text-muted-foreground space-y-1" aria-label="Optimization history">
          <p className="font-medium text-foreground text-sm">Earlier optimizations</p>
          <ul>{history.data.slice(0, 5).map(h => <li key={h.id}>{new Date(h.created_at).toLocaleString()} · {h.status} · {h.delta ? `${h.delta.distance_pct} distance, ${h.delta.travel_pct} travel time` : 'no change'} · {h.applied ? 'applied' : 'not applied'}</li>)}</ul>
        </div>
      )}
    </section>
  );
}
