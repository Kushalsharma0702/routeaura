import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Info } from 'lucide-react';
import { EmptyState, ErrorState, GridSkeleton, Pager } from '@/components/QueryState';
import RecommendationCard from '@/components/recommendations/RecommendationCard';
import type { Kind, RecommendationRequest } from '@/lib/api/recommendations';
import { useRecommendations } from '@/hooks/useRecommendations';

const PAGE_SIZE = 6;

const STRATEGY_TEXT: Record<string, string> = {
  weighted: 'Personalised using all of your preferences', cosine: 'Ranked by interest similarity only',
  popularity: 'Ranked by popularity among travelers', popularity_fallback: 'Popular places (no preferences yet)',
};

/** Fetches and renders one page of recommendations for the given request; owns paging and hidden items. */
export default function RecommendationList({ kind, request }: { kind: Kind; request: RecommendationRequest }) {
  const [page, setPage] = useState(1);
  const [hidden, setHidden] = useState<Set<string>>(new Set());
  const key = JSON.stringify(request);
  useEffect(() => { setPage(1); setHidden(new Set()); }, [key]);

  const { data, isLoading, isError, isFetching, refetch } = useRecommendations(kind, { ...request, page, page_size: PAGE_SIZE });
  const visible = data?.items.filter(i => !hidden.has(i.recommendation_item_id)) ?? [];

  return (
    <div className="space-y-4">
      {isLoading && <GridSkeleton count={PAGE_SIZE} height="h-96" />}
      {isError && <ErrorState message="We couldn't generate recommendations." onRetry={() => refetch()} />}
      {data && (
        <>
          <div className="text-sm text-muted-foreground flex flex-wrap items-center gap-x-3 gap-y-1" aria-live="polite">
            <span>{STRATEGY_TEXT[data.strategy] ?? data.strategy}{data.diversified ? ' · with variety' : ''}</span>
            <span>{data.total_candidates} candidate{data.total_candidates === 1 ? '' : 's'}</span>
            {isFetching && <span>updating…</span>}
          </div>
          {data.notes.length > 0 && (
            <ul className="rounded-lg border border-border/50 bg-muted/40 p-3 text-xs text-muted-foreground space-y-1" aria-label="Notes about these recommendations">
              {data.notes.map(n => <li key={n} className="flex gap-2"><Info className="w-3.5 h-3.5 shrink-0 mt-0.5" />{n}</li>)}
              {data.strategy === 'popularity_fallback' && (
                <li className="pl-5"><Link to="/dashboard/profile" className="text-primary hover:underline">Set your travel preferences</Link> to get personalised results.</li>
              )}
            </ul>
          )}
          {visible.length === 0 && (
            <EmptyState title={data.items.length === 0 ? 'No recommendations found' : 'You have hidden everything on this page'}
              hint={data.items.length === 0 ? 'Try relaxing a filter or changing your preferences.' : 'Go to another page or adjust your preferences.'} />
          )}
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
            {visible.map((item, i) => (
              <RecommendationCard key={item.recommendation_item_id} item={item} index={i}
                onDismissed={id => setHidden(h => new Set(h).add(id))}
                onRestored={id => setHidden(h => { const n = new Set(h); n.delete(id); return n; })} />
            ))}
          </div>
          <Pager page={page} pageSize={PAGE_SIZE} total={data.total_candidates} onPage={setPage} />
          <p className="text-xs text-muted-foreground">{data.disclaimer}</p>
        </>
      )}
    </div>
  );
}
