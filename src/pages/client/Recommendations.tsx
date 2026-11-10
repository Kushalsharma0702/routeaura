import { useState } from 'react';
import { Link } from 'react-router-dom';
import { BookmarkX, Sparkles } from 'lucide-react';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { EmptyState, ErrorState, Pager } from '@/components/QueryState';
import PreferenceControls from '@/components/recommendations/PreferenceControls';
import RecommendationList from '@/components/recommendations/RecommendationList';
import { ApiError } from '@/lib/api/client';
import type { RecommendationRequest } from '@/lib/api/recommendations';
import { formatMinor } from '@/lib/format';
import { useCategories } from '@/hooks/useCatalog';
import { useInteraction, useRunHistory, useSavedItems } from '@/hooks/useRecommendations';
import { usePreferences } from '@/hooks/useUsers';

const ALL = 'all';

function SavedTab() {
  const { data, isLoading, isError, refetch } = useSavedItems();
  const interaction = useInteraction();
  if (isLoading) return <p role="status" className="text-sm text-muted-foreground">Loading saved places…</p>;
  if (isError) return <ErrorState message="We couldn't load your saved places." onRetry={() => refetch()} />;
  if (!data?.items.length) return <EmptyState title="Nothing saved yet" hint="Use Save on a recommendation to keep it here." />;
  return (
    <ul className="grid grid-cols-1 md:grid-cols-2 gap-3">
      {data.items.map(s => {
        const place = s.destination ?? s.attraction!;
        const href = `/dashboard/destinations/${s.destination ? s.destination.slug : s.attraction!.destination_id}`;
        return (
          <li key={place.id} className="bg-card rounded-xl border border-border/50 shadow-card p-4 flex items-center gap-3">
            <div className="flex-1 min-w-0">
              <Link to={href} className="font-semibold text-card-foreground hover:underline">{place.name}</Link>
              <p className="text-xs text-muted-foreground capitalize">
                {s.item_type}{s.destination ? ` · ~${formatMinor(s.destination.estimated_cost_per_day_minor, s.destination.currency)}/day` : ` · ${s.attraction!.category.name}`}
              </p>
            </div>
            <Button size="sm" variant="outline" className="gap-1.5" disabled={interaction.isPending}
              onClick={() => interaction.mutate({ kind: s.item_type, id: place.id, type: 'unsave', source: 'saved' }, {
                onSuccess: () => toast.success('Removed from saved'), onError: e => toast.error(e instanceof ApiError ? e.message : 'Could not update'),
              })}><BookmarkX className="w-4 h-4" />Remove</Button>
          </li>
        );
      })}
    </ul>
  );
}

function HistoryTab() {
  const [page, setPage] = useState(1);
  const { data, isLoading, isError, refetch } = useRunHistory(page);
  if (isLoading) return <p role="status" className="text-sm text-muted-foreground">Loading history…</p>;
  if (isError) return <ErrorState message="We couldn't load your recommendation history." onRetry={() => refetch()} />;
  if (!data?.items.length) return <EmptyState title="No history yet" hint="Every set of recommendations you generate is recorded here." />;
  return (
    <div className="space-y-3">
      <ul className="space-y-3">
        {data.items.map(r => (
          <li key={r.run_id} className="bg-card rounded-xl border border-border/50 shadow-card p-4 text-sm">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span className="font-medium capitalize">{r.kind} recommendations</span>
              <time className="text-xs text-muted-foreground" dateTime={r.created_at}>{new Date(r.created_at).toLocaleString()}</time>
            </div>
            <p className="text-xs text-muted-foreground mt-1">{r.strategy.replace('_', ' ')} · {r.returned_count} shown of {r.total_candidates} · model {r.model_version}</p>
            {r.top_items.length > 0 && <p className="mt-2">Top: {r.top_items.join(', ')}</p>}
          </li>
        ))}
      </ul>
      <Pager page={page} pageSize={data.page_size} total={data.total} onPage={setPage} />
    </div>
  );
}

export default function Recommendations() {
  const prefs = usePreferences();
  const categories = useCategories();
  const [request, setRequest] = useState<RecommendationRequest>({});
  const [category, setCategory] = useState(ALL);
  const [outdoor, setOutdoor] = useState(false);

  const destReq: RecommendationRequest = { ...request, filters: { ...(category !== ALL ? { category } : {}) } };
  const attrReq: RecommendationRequest = { ...request, filters: { ...(category !== ALL ? { category } : {}), ...(outdoor ? { outdoor: true } : {}) } };

  return (
    <div className="space-y-6 pb-24 lg:pb-0">
      <div>
        <h1 className="text-2xl font-display font-bold text-foreground flex items-center gap-2"><Sparkles className="w-6 h-6 text-primary" />Recommended for you</h1>
        <p className="text-sm text-muted-foreground mt-1">Places ranked against your preferences, with the reasons shown for each one.</p>
      </div>

      {prefs.isError && <ErrorState message="We couldn't load your saved preferences. You can still set them below." onRetry={() => prefs.refetch()} />}
      <PreferenceControls saved={prefs.data} onApply={setRequest} />

      <Tabs defaultValue="destinations">
        <TabsList className="flex flex-wrap h-auto">
          <TabsTrigger value="destinations">Destinations</TabsTrigger>
          <TabsTrigger value="attractions">Attractions</TabsTrigger>
          <TabsTrigger value="saved">Saved</TabsTrigger>
          <TabsTrigger value="history">History</TabsTrigger>
        </TabsList>

        <div className="flex flex-wrap items-center gap-4 mt-4">
          <Select value={category} onValueChange={setCategory}>
            <SelectTrigger className="w-52" aria-label="Filter by category"><SelectValue placeholder="Category" /></SelectTrigger>
            <SelectContent><SelectItem value={ALL}>All categories</SelectItem>{categories.data?.map(c => <SelectItem key={c.id} value={c.slug}>{c.name}</SelectItem>)}</SelectContent>
          </Select>
          <div className="flex items-center gap-2"><Switch id="reco-outdoor" checked={outdoor} onCheckedChange={setOutdoor} /><Label htmlFor="reco-outdoor" className="text-sm">Outdoor attractions only</Label></div>
        </div>

        <TabsContent value="destinations" className="mt-4"><RecommendationList kind="destination" request={destReq} /></TabsContent>
        <TabsContent value="attractions" className="mt-4"><RecommendationList kind="attraction" request={attrReq} /></TabsContent>
        <TabsContent value="saved" className="mt-4"><SavedTab /></TabsContent>
        <TabsContent value="history" className="mt-4"><HistoryTab /></TabsContent>
      </Tabs>
    </div>
  );
}
