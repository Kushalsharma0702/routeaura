import { Link } from 'react-router-dom';
import { ArrowRight, Sparkles } from 'lucide-react';
import { EmptyState, ErrorState, GridSkeleton } from '@/components/QueryState';
import RecommendationCard from '@/components/recommendations/RecommendationCard';
import { useRecommendations } from '@/hooks/useRecommendations';

/** Dashboard teaser: the top 3 destinations for the signed-in traveler (live API data). */
export default function RecommendationsSection() {
  const { data, isLoading, isError, refetch } = useRecommendations('destination', { page: 1, page_size: 3 });
  return (
    <section aria-labelledby="reco-h" className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 id="reco-h" className="text-lg font-display font-semibold text-foreground flex items-center gap-2"><Sparkles className="w-5 h-5 text-primary" />Recommended for you</h2>
        <Link to="/dashboard/recommendations" className="text-sm text-primary hover:underline inline-flex items-center gap-1">Tune &amp; see more <ArrowRight className="w-4 h-4" /></Link>
      </div>
      {isLoading && <GridSkeleton count={3} height="h-80" />}
      {isError && <ErrorState message="We couldn't load recommendations right now." onRetry={() => refetch()} />}
      {data && data.items.length === 0 && <EmptyState title="No recommendations yet" hint="Once destinations are published they will appear here." />}
      {data && data.strategy === 'popularity_fallback' && data.items.length > 0 && (
        <p className="text-sm text-muted-foreground">Showing popular places. <Link to="/dashboard/profile" className="text-primary hover:underline">Set your preferences</Link> for personalised picks.</p>
      )}
      {data && data.items.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {data.items.map((item, i) => <RecommendationCard key={item.recommendation_item_id} item={item} index={i} compact />)}
        </div>
      )}
    </section>
  );
}
