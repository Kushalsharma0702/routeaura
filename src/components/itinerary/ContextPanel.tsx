import { useState } from 'react';
import { CloudRain, Clock, Wallet, XCircle } from 'lucide-react';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { ApiError } from '@/lib/api/client';
import type { Proposal } from '@/lib/api/context';
import type { Itinerary } from '@/lib/api/itineraries';
import { rupeesToMinor } from '@/lib/forms';
import { useAdapt, useApproveProposal, useContextStatus, useProposals, useRefreshContext, useReport, useRejectProposal } from '@/hooks/useRouting';

const errMsg = (e: unknown) => (e instanceof ApiError ? e.message : 'Something went wrong. Please try again.');
const SOURCE_LABEL: Record<string, string> = { user_reported: 'reported by you', verified_hours: 'verified opening hours' };

function ProposalCard({ p, itineraryId, onDone }: { p: Proposal; itineraryId: string; onDone: () => void }) {
  const approve = useApproveProposal(itineraryId);
  const reject = useRejectProposal(itineraryId);
  const pending = p.status === 'pending';
  const issues = p.preview.after?.violations ?? [];
  return (
    <li className="rounded-xl border border-border/50 p-4 space-y-2 text-sm" aria-label={`Suggestion: ${p.trigger.type}`}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="font-medium capitalize">{p.trigger.type.replace('_', ' ')} · day {p.trigger.day}</span>
        <span className={`text-xs px-2 py-0.5 rounded-full ${pending ? 'bg-warning/15 text-warning' : p.status === 'approved' ? 'bg-success/15 text-success' : 'bg-muted text-muted-foreground'}`}>{p.status}</span>
      </div>
      <p className="text-xs text-muted-foreground">Evidence: {p.trigger.evidence} · source: {SOURCE_LABEL[p.trigger.source] ?? p.trigger.source}</p>
      <ul className="space-y-1">{p.changes.map(c => (
        <li key={c.activity_id}>{c.action === 'replace' ? <>Replace <strong>{c.from}</strong> with <strong>{c.to}</strong></> : c.action === 'move' ? <>Move <strong>{c.name}</strong> to day {c.to_day}</> : <>Remove <strong>{c.name}</strong></>}
          <span className="block text-xs text-muted-foreground">{c.reason}</span></li>))}</ul>
      {issues.length > 0 && <ul className="text-xs text-destructive">{issues.map(v => <li key={v.message}>• {v.message}</li>)}</ul>}
      {pending && (
        <div className="flex gap-2 pt-1">
          <Button size="sm" className="gradient-primary text-primary-foreground" disabled={approve.isPending}
            onClick={() => approve.mutate(p.id, { onSuccess: () => { toast.success('Change applied'); onDone(); }, onError: e => toast.error(errMsg(e)) })}>Approve change</Button>
          <Button size="sm" variant="outline" disabled={reject.isPending}
            onClick={() => reject.mutate(p.id, { onSuccess: () => toast.success('Suggestion dismissed'), onError: e => toast.error(errMsg(e)) })}>Reject</Button>
        </div>
      )}
    </li>
  );
}

export default function ContextPanel({ it }: { it: Itinerary }) {
  const status = useContextStatus(it.id);
  const refresh = useRefreshContext(it.id);
  const report = useReport(it.id);
  const adapt = useAdapt(it.id);
  const proposals = useProposals(it.id);
  const all = it.day_plans.flatMap(d => d.activities);
  const [closed, setClosed] = useState('');
  const [delayDay, setDelayDay] = useState('1');
  const [delayTime, setDelayTime] = useState('14:00');
  const [spent, setSpent] = useState('');
  const [lastNotes, setLastNotes] = useState<string[]>([]);
  const s = status.data;

  const submit = (r: Parameters<typeof report.mutate>[0], ok: string) => report.mutate(r, { onSuccess: () => toast.success(ok), onError: e => toast.error(errMsg(e)) });
  const check = () => adapt.mutate(undefined, {
    onSuccess: res => { setLastNotes(res.notes); toast.success(res.proposals.length ? `${res.proposals.length} suggestion(s) ready for your review` : 'No changes suggested'); },
    onError: e => toast.error(errMsg(e)),
  });

  return (
    <section aria-label="Conditions and adaptation" className="space-y-4">
      <div className="bg-card rounded-xl border border-border/50 shadow-card p-4 space-y-3">
        <h3 className="font-display font-semibold flex items-center gap-2"><CloudRain className="w-4 h-4 text-primary" />Conditions and adaptation</h3>
        {status.isLoading && <p role="status" className="text-sm text-muted-foreground">Loading…</p>}
        {s && (
          <>
            <p className="text-xs text-muted-foreground">Weather source: <strong>{s.weather_configured ? s.weather_provider : 'not configured'}</strong>. Suggestions are never applied without your approval; stale data (older than {s.max_age_minutes} min) is ignored.</p>
            <ul className="text-xs text-muted-foreground space-y-1">{s.notes.map(n => <li key={n}>• {n}</li>)}</ul>
            {s.snapshots.filter(x => x.kind === 'weather').length > 0 && (
              <ul className="text-xs space-y-1" aria-label="Weather by day">{s.snapshots.filter(x => x.kind === 'weather').map(x => (
                <li key={x.id}>Day {x.day_number}: {x.payload.precip_prob == null ? 'rain chance unknown' : `${x.payload.precip_prob}% rain`}{x.payload.temp_max_c != null ? `, high ${x.payload.temp_max_c}°C` : ''} · {x.source}, {x.age_minutes} min ago {x.fresh ? '' : '(stale: not used)'}</li>))}</ul>
            )}
            <div className="flex flex-wrap gap-3">
              <Button variant="outline" disabled={!s.weather_configured || s.needs_dates || refresh.isPending}
                onClick={() => refresh.mutate(undefined, { onSuccess: () => toast.success('Weather refreshed'), onError: e => toast.error(errMsg(e)) })}>Refresh weather</Button>
              <Button className="gradient-primary text-primary-foreground" disabled={adapt.isPending} onClick={check}>{adapt.isPending ? 'Checking…' : 'Check conditions'}</Button>
            </div>
            {!s.weather_configured && <p className="text-xs text-muted-foreground">Weather checks are unavailable until a provider is configured. You can still report problems below.</p>}
          </>
        )}
        <details className="rounded-lg border border-border/50 p-3">
          <summary className="cursor-pointer text-sm font-medium">Tell us what is happening</summary>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-3">
            <div className="space-y-2">
              <Label htmlFor="rp-closed" className="flex items-center gap-1.5"><XCircle className="w-3.5 h-3.5" />Place is closed</Label>
              <Select value={closed || undefined} onValueChange={setClosed}>
                <SelectTrigger id="rp-closed"><SelectValue placeholder="Choose an activity" /></SelectTrigger>
                <SelectContent>{all.map(a => <SelectItem key={a.id} value={a.id}>{a.attraction.name}</SelectItem>)}</SelectContent>
              </Select>
              <Button size="sm" variant="outline" disabled={!closed || report.isPending} onClick={() => submit({ type: 'closure', activity_id: closed }, 'Closure reported')}>Report closure</Button>
            </div>
            <div className="space-y-2">
              <Label htmlFor="rp-day" className="flex items-center gap-1.5"><Clock className="w-3.5 h-3.5" />I am running late</Label>
              <div className="flex gap-2">
                <Select value={delayDay} onValueChange={setDelayDay}>
                  <SelectTrigger id="rp-day" aria-label="Day"><SelectValue /></SelectTrigger>
                  <SelectContent>{it.day_plans.map(d => <SelectItem key={d.day_number} value={String(d.day_number)}>Day {d.day_number}</SelectItem>)}</SelectContent>
                </Select>
                <Input type="time" aria-label="Current time" value={delayTime} onChange={e => setDelayTime(e.target.value)} />
              </div>
              <Button size="sm" variant="outline" disabled={report.isPending} onClick={() => {
                const [h, m] = delayTime.split(':').map(Number);
                submit({ type: 'delay', day_number: Number(delayDay), current_time_min: h * 60 + m, completed_activity_ids: [] }, 'Delay reported');
              }}>Report delay</Button>
            </div>
            <div className="space-y-2">
              <Label htmlFor="rp-spent" className="flex items-center gap-1.5"><Wallet className="w-3.5 h-3.5" />Spent so far (₹)</Label>
              <Input id="rp-spent" inputMode="decimal" value={spent} onChange={e => setSpent(e.target.value)} />
              <Button size="sm" variant="outline" disabled={!spent || report.isPending} onClick={() => submit({ type: 'spent', spent_minor: rupeesToMinor(spent) ?? 0 }, 'Spending reported')}>Report spending</Button>
            </div>
          </div>
        </details>
      </div>

      {lastNotes.length > 0 && <ul className="text-xs text-muted-foreground space-y-1" aria-label="Notes from the last check">{lastNotes.map(n => <li key={n}>• {n}</li>)}</ul>}
      {proposals.data && proposals.data.length === 0 && <p className="text-sm text-muted-foreground">No suggestions yet.</p>}
      <ul className="space-y-3" aria-label="Suggestions">{proposals.data?.map(p => <ProposalCard key={p.id} p={p} itineraryId={it.id} onDone={() => status.refetch()} />)}</ul>
    </section>
  );
}
