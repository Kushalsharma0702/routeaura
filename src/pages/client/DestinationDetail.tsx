import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { ArrowLeft, Bookmark, BookmarkCheck, Calendar, Clock, MapPin, Sparkles, Sun, ThumbsUp, Wallet } from 'lucide-react';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Skeleton } from '@/components/ui/skeleton';
import ImageGallery from '@/components/ImageGallery';
import { EmptyState, ErrorState } from '@/components/QueryState';
import { ApiError } from '@/lib/api/client';
import { useAttractions, useCategories, useDestination } from '@/hooks/useCatalog';
import { useInteraction, useItemState } from '@/hooks/useRecommendations';
import { formatDistance, formatDuration, formatMinor, seasonLabel } from '@/lib/format';

const RADII = ['all', '5', '10', '25', '50'];

export default function DestinationDetail() {
  const { ref } = useParams();
  const dest = useDestination(ref);
  const [radius, setRadius] = useState('all');
  const [category, setCategory] = useState('all');
  const d = dest.data;
  const allCategories = useCategories();
  const state = useItemState('destination', d?.id);
  const interaction = useInteraction();
  const viewedId = d?.id;
  // one 'view' signal per visit; the server also de-duplicates repeated views within minutes
  useEffect(() => { if (viewedId) interaction.mutate({ kind: 'destination', id: viewedId, type: 'view', source: 'detail' }); // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [viewedId]);
  const toggle = (type: 'save' | 'unsave' | 'like' | 'reaction_clear') =>
    interaction.mutate({ kind: 'destination', id: d!.id, type, source: 'detail' }, { onError: () => toast.error('Could not update. Please try again.') });

  const attractions = useAttractions({
    destination_id: d?.id, category: category === 'all' ? undefined : category, page_size: 50,
    ...(radius !== 'all' && d ? { lat: d.latitude, lng: d.longitude, radius_km: Number(radius), sort: 'distance' } : {}),
  }, !!d);

  if (dest.isLoading) return <div className="space-y-4" role="status" aria-label="Loading"><Skeleton className="h-8 w-48" /><Skeleton className="h-64 rounded-xl" /><Skeleton className="h-40 rounded-xl" /></div>;
  if (dest.isError) {
    const notFound = dest.error instanceof ApiError && dest.error.status === 404;
    return notFound
      ? <div className="space-y-4"><BackLink /><EmptyState title="Destination not found" hint="It may have been removed or is not published." /></div>
      : <div className="space-y-4"><BackLink /><ErrorState message="We couldn't load this destination." onRetry={() => dest.refetch()} /></div>;
  }
  if (!d) return null;

  return (
    <div className="space-y-6 pb-24 lg:pb-0">
      <BackLink />
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-3xl font-display font-bold text-foreground flex items-center gap-2"><MapPin className="w-6 h-6 text-primary" />{d.name}</h1>
          <p className="text-muted-foreground">{[d.region, d.country].filter(Boolean).join(', ')}</p>
        </div>
        <div className="flex gap-2">
          <Button variant={state.data?.saved ? 'secondary' : 'outline'} className="gap-2" aria-pressed={!!state.data?.saved} disabled={interaction.isPending || !state.data}
            onClick={() => toggle(state.data?.saved ? 'unsave' : 'save')}>
            {state.data?.saved ? <BookmarkCheck className="w-4 h-4" /> : <Bookmark className="w-4 h-4" />}{state.data?.saved ? 'Saved' : 'Save'}
          </Button>
          <Button variant={state.data?.liked ? 'secondary' : 'outline'} className="gap-2" aria-pressed={!!state.data?.liked} disabled={interaction.isPending || !state.data}
            onClick={() => toggle(state.data?.liked ? 'reaction_clear' : 'like')}>
            <ThumbsUp className="w-4 h-4" />{state.data?.liked ? 'Liked' : 'Like'}
          </Button>
        </div>
      </div>

      {d.images.length > 0 && <ImageGallery images={d.images} title={d.name} />}
      <p className="text-foreground/90 leading-relaxed">{d.description}</p>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <Fact icon={Calendar} label="Best time" value={seasonLabel(d.best_season_start_month, d.best_season_end_month)} />
        <Fact icon={Clock} label="Suggested stay" value={d.recommended_duration_days ? `${d.recommended_duration_days} days` : 'Flexible'} />
        <Fact icon={Wallet} label="Typical daily cost" value={formatMinor(d.estimated_cost_per_day_minor, d.currency)} note="estimate" />
        <Fact icon={Sun} label="Climate" value={d.climate ?? 'Not set'} capitalize />
      </div>
      {(d.climate_notes || d.accessibility_notes) && (
        <div className="text-sm text-muted-foreground space-y-1">
          {d.climate_notes && <p><strong className="text-foreground">Climate:</strong> {d.climate_notes}</p>}
          {d.accessibility_notes && <p><strong className="text-foreground">Accessibility:</strong> {d.accessibility_notes}</p>}
        </div>
      )}
      <div className="flex flex-wrap gap-2">
        {d.categories.map(c => <span key={c.id} className="text-xs bg-primary/10 text-primary px-3 py-1 rounded-full">{c.name}</span>)}
      </div>
      {d.source !== 'provider' && (
        <p className="text-xs text-muted-foreground">Costs, durations and coordinates are curated estimates, not live data.</p>
      )}

      <section aria-labelledby="attractions-h" className="space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <h2 id="attractions-h" className="text-xl font-display font-semibold flex items-center gap-2"><Sparkles className="w-5 h-5 text-primary" />Attractions ({d.attraction_count})</h2>
          <div className="flex gap-3">
            <Select value={category} onValueChange={setCategory}>
              <SelectTrigger className="w-44" aria-label="Attraction category"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All categories</SelectItem>
                {allCategories.data?.map(c => <SelectItem key={c.id} value={c.slug}>{c.name}</SelectItem>)}
              </SelectContent>
            </Select>
            <Select value={radius} onValueChange={setRadius}>
              <SelectTrigger className="w-44" aria-label="Distance from centre"><SelectValue /></SelectTrigger>
              <SelectContent>
                {RADII.map(r => <SelectItem key={r} value={r}>{r === 'all' ? 'Any distance' : `Within ${r} km of centre`}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
        </div>

        {attractions.isLoading && <div className="space-y-3" role="status" aria-label="Loading attractions">{[0, 1, 2].map(i => <Skeleton key={i} className="h-20 rounded-xl" />)}</div>}
        {attractions.isError && <ErrorState message="We couldn't load attractions." onRetry={() => attractions.refetch()} />}
        {attractions.data?.items.length === 0 && <EmptyState title="No attractions found" hint={radius !== 'all' || category !== 'all' ? 'Try a larger radius or another category.' : 'No attractions have been added yet.'} />}
        <ul className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {attractions.data?.items.map(a => (
            <li key={a.id} className="bg-card rounded-xl border border-border/50 shadow-card p-4 space-y-2">
              <div className="flex items-start justify-between gap-2">
                <h3 className="font-semibold text-card-foreground">{a.name}</h3>
                <span className="text-xs bg-primary/10 text-primary px-2 py-0.5 rounded-full shrink-0">{a.category.name}</span>
              </div>
              {a.description && <p className="text-sm text-muted-foreground line-clamp-2">{a.description}</p>}
              <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
                <span className="flex items-center gap-1"><Clock className="w-3.5 h-3.5" />{formatDuration(a.typical_duration_minutes)}</span>
                <span>{a.is_outdoor ? 'Outdoor' : 'Indoor'}</span>
                <span>Entry: {a.estimated_cost_minor == null ? 'unknown' : formatMinor(a.estimated_cost_minor, a.currency)}</span>
                {a.distance_m != null && <span className="font-medium text-foreground">{formatDistance(a.distance_m)} from centre</span>}
              </div>
              <p className="text-xs text-muted-foreground">Opening hours: {a.opening_hours ? 'available' : 'not verified'}</p>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}

function BackLink() {
  return <Link to="/dashboard/destinations" className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground"><ArrowLeft className="w-4 h-4" />All destinations</Link>;
}

function Fact({ icon: Icon, label, value, note, capitalize }: { icon: React.ElementType; label: string; value: string; note?: string; capitalize?: boolean }) {
  return (
    <div className="bg-card rounded-xl border border-border/50 shadow-card p-4">
      <div className="flex items-center gap-2 text-xs text-muted-foreground"><Icon className="w-4 h-4 text-primary" />{label}</div>
      <p className={`mt-1 font-semibold text-card-foreground ${capitalize ? 'capitalize' : ''}`}>{value}</p>
      {note && <p className="text-[11px] text-muted-foreground">{note}</p>}
    </div>
  );
}
