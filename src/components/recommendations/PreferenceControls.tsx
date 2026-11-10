import { useEffect, useState } from 'react';
import { RotateCcw, Save, SlidersHorizontal } from 'lucide-react';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Slider } from '@/components/ui/slider';
import { Switch } from '@/components/ui/switch';
import { ApiError } from '@/lib/api/client';
import type { Feature, Priority, RecommendationRequest, Strategy } from '@/lib/api/recommendations';
import { buildRequest, fromSaved, NONE, type Controls } from '@/lib/recoControls';
import { usersApi, type Preferences } from '@/lib/api/users';
import { rupeesToMinor, splitList, toNum } from '@/lib/forms';
import { useSavePreferences } from '@/hooks/useUsers';

const FEATURES: [Feature, string][] = [['interest', 'Interests'], ['budget', 'Budget'], ['season', 'Season'], ['climate', 'Climate'], ['duration', 'Trip length'], ['style', 'Travel style']];
const PRIORITIES: [Priority, string][] = [['ignore', 'Ignore'], ['low', 'Low'], ['normal', 'Normal'], ['high', 'High']];
const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
const CLIMATES = ['any', 'tropical', 'temperate', 'cold', 'arid'];
const STYLES = ['budget', 'comfort', 'luxury', 'adventure', 'relaxed'];

export default function PreferenceControls({ saved, onApply }: { saved: Preferences | undefined; onApply: (req: RecommendationRequest) => void }) {
  const [c, setC] = useState<Controls>(() => fromSaved(saved));
  const [touched, setTouched] = useState(false);
  const savePrefs = useSavePreferences();
  useEffect(() => { if (!touched) setC(fromSaved(saved)); }, [saved, touched]);
  const set = <K extends keyof Controls>(k: K, v: Controls[K]) => { setTouched(true); setC(prev => ({ ...prev, [k]: v })); };

  const apply = (e: React.FormEvent) => { e.preventDefault(); onApply(buildRequest(c, saved)); };
  const reset = () => { setTouched(false); setC(fromSaved(saved)); onApply(buildRequest(fromSaved(saved), saved)); };
  const saveAsPreferences = () => {
    if (!saved) return;
    const next: Preferences = {
      ...saved, budget_per_day_minor: rupeesToMinor(c.budget), trip_duration_days: toNum(c.days),
      preferred_climate: c.climate === 'any' ? null : c.climate, travel_style: c.style === NONE ? null : c.style,
      interests: splitList(c.interests).map(s => s.toLowerCase()),
    };
    savePrefs.mutate(next, {
      onSuccess: () => { toast.success('Saved as your travel preferences'); setTouched(false); },
      onError: e => toast.error(e instanceof ApiError ? e.message : 'Could not save preferences'),
    });
  };

  return (
    <form onSubmit={apply} className="bg-card rounded-xl border border-border/50 shadow-card p-4 sm:p-6 space-y-4" aria-label="Recommendation preferences">
      <div className="flex items-center gap-2 font-display font-semibold text-card-foreground"><SlidersHorizontal className="w-4 h-4 text-primary" />Tune your recommendations</div>
      <p className="text-xs text-muted-foreground">Starts from your saved preferences. Changes here apply to this search only unless you save them.</p>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        <div className="space-y-2"><Label htmlFor="rc-interests">Interests</Label><Input id="rc-interests" placeholder="history, food, adventure" value={c.interests} onChange={e => set('interests', e.target.value)} /></div>
        <div className="space-y-2"><Label htmlFor="rc-budget">Budget per day (₹)</Label><Input id="rc-budget" inputMode="decimal" value={c.budget} onChange={e => set('budget', e.target.value)} /></div>
        <div className="space-y-2"><Label htmlFor="rc-days">Trip length (days)</Label><Input id="rc-days" inputMode="numeric" value={c.days} onChange={e => set('days', e.target.value)} /></div>
        <div className="space-y-2">
          <Label htmlFor="rc-month">Travel month</Label>
          <Select value={c.month} onValueChange={v => set('month', v)}>
            <SelectTrigger id="rc-month"><SelectValue /></SelectTrigger>
            <SelectContent><SelectItem value={NONE}>Any month</SelectItem>{MONTHS.map((m, i) => <SelectItem key={m} value={String(i + 1)}>{m}</SelectItem>)}</SelectContent>
          </Select>
        </div>
        <div className="space-y-2">
          <Label htmlFor="rc-climate">Climate</Label>
          <Select value={c.climate} onValueChange={v => set('climate', v)}>
            <SelectTrigger id="rc-climate"><SelectValue /></SelectTrigger>
            <SelectContent>{CLIMATES.map(x => <SelectItem key={x} value={x} className="capitalize">{x === 'any' ? 'No preference' : x}</SelectItem>)}</SelectContent>
          </Select>
        </div>
        <div className="space-y-2">
          <Label htmlFor="rc-style">Travel style</Label>
          <Select value={c.style} onValueChange={v => set('style', v)}>
            <SelectTrigger id="rc-style"><SelectValue /></SelectTrigger>
            <SelectContent><SelectItem value={NONE}>No preference</SelectItem>{STYLES.map(x => <SelectItem key={x} value={x} className="capitalize">{x}</SelectItem>)}</SelectContent>
          </Select>
        </div>
      </div>

      <details className="rounded-lg border border-border/50 p-3">
        <summary className="cursor-pointer text-sm font-medium">How much does each factor matter?</summary>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 mt-3">
          {FEATURES.map(([f, label]) => (
            <div key={f} className="space-y-2">
              <Label htmlFor={`rc-p-${f}`}>{label} importance</Label>
              <Select value={c.priorities[f] ?? 'normal'} onValueChange={v => set('priorities', { ...c.priorities, [f]: v as Priority })}>
                <SelectTrigger id={`rc-p-${f}`}><SelectValue /></SelectTrigger>
                <SelectContent>{PRIORITIES.map(([v, l]) => <SelectItem key={v} value={v}>{l}</SelectItem>)}</SelectContent>
              </Select>
            </div>
          ))}
        </div>
      </details>

      <details className="rounded-lg border border-border/50 p-3">
        <summary className="cursor-pointer text-sm font-medium">Variety and method</summary>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mt-3">
          <div className="space-y-3">
            <div className="flex items-center gap-3"><Switch id="rc-div" checked={c.diversify} onCheckedChange={v => set('diversify', v)} /><Label htmlFor="rc-div">Mix in variety</Label></div>
            <div className="space-y-1">
              <Label htmlFor="rc-lambda" className="text-xs text-muted-foreground">Relevance ({Math.round(c.lambda * 100)}%) vs variety ({Math.round((1 - c.lambda) * 100)}%)</Label>
              <Slider id="rc-lambda" aria-label="Relevance versus variety" min={0} max={1} step={0.05} value={[c.lambda]} disabled={!c.diversify} onValueChange={v => set('lambda', v[0])} />
            </div>
          </div>
          <div className="space-y-2">
            <Label htmlFor="rc-strategy">Method</Label>
            <Select value={c.strategy} onValueChange={v => set('strategy', v as Strategy)}>
              <SelectTrigger id="rc-strategy"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="weighted">Personalised (all factors)</SelectItem>
                <SelectItem value="cosine">Interests only</SelectItem>
                <SelectItem value="popularity">Popular with others</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>
      </details>

      <div className="flex flex-wrap gap-3">
        <Button type="submit" className="gradient-primary text-primary-foreground">Get recommendations</Button>
        <Button type="button" variant="outline" className="gap-2" onClick={reset}><RotateCcw className="w-4 h-4" />Use my saved preferences</Button>
        <Button type="button" variant="outline" className="gap-2" onClick={saveAsPreferences} disabled={!saved || savePrefs.isPending}><Save className="w-4 h-4" />Save as my preferences</Button>
      </div>
    </form>
  );
}
