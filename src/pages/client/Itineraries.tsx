import { useState } from 'react';
import { Link } from 'react-router-dom';
import { CalendarDays, Plus, Trash2, Users } from 'lucide-react';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import ConfirmDialog from '@/components/admin/ConfirmDialog';
import { EmptyState, ErrorState, GridSkeleton, Pager } from '@/components/QueryState';
import { ApiError } from '@/lib/api/client';
import type { ItinerarySummary } from '@/lib/api/itineraries';
import { useDeleteItinerary, useItineraries } from '@/hooks/useItineraries';

export default function Itineraries() {
  const [page, setPage] = useState(1);
  const [toDelete, setToDelete] = useState<ItinerarySummary | null>(null);
  const { data, isLoading, isError, refetch } = useItineraries(page);
  const del = useDeleteItinerary();
  return (
    <div className="space-y-6 pb-24 lg:pb-0">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-display font-bold text-foreground">My trips</h1>
          <p className="text-sm text-muted-foreground mt-1">{data ? `${data.total} itinerar${data.total === 1 ? 'y' : 'ies'}` : 'Loading…'}</p>
        </div>
        <Button asChild className="gradient-primary text-primary-foreground gap-2"><Link to="/dashboard/planner"><Plus className="w-4 h-4" />Plan a trip</Link></Button>
      </div>
      {isLoading && <GridSkeleton count={3} height="h-40" />}
      {isError && <ErrorState message="We couldn't load your trips." onRetry={() => refetch()} />}
      {data?.items.length === 0 && <EmptyState title="No trips yet" hint="Plan your first trip and it will appear here." />}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {data?.items.map(it => (
          <article key={it.id} className="bg-card rounded-xl border border-border/50 shadow-card p-5 space-y-3" aria-label={it.title}>
            <div className="flex items-start justify-between gap-2">
              <Link to={`/dashboard/itineraries/${it.id}`} className="font-display font-semibold text-card-foreground hover:underline">{it.title}</Link>
              <span className={`text-xs px-2 py-0.5 rounded-full ${it.status === 'saved' ? 'bg-success/15 text-success' : 'bg-muted text-muted-foreground'}`}>{it.status === 'saved' ? 'Saved' : 'Draft'}</span>
            </div>
            <p className="text-sm text-muted-foreground">{it.destination_name}</p>
            <div className="flex flex-wrap gap-x-4 text-xs text-muted-foreground">
              <span className="flex items-center gap-1"><CalendarDays className="w-3.5 h-3.5" />{it.days} days{it.start_date ? ` · ${it.start_date}` : ''}</span>
              <span className="flex items-center gap-1"><Users className="w-3.5 h-3.5" />{it.traveler_count}</span>
              <span>{it.activity_count} activities</span>
              <span>{it.generation_source === 'llm' ? 'AI-assisted' : 'App planner'}</span>
            </div>
            <div className="flex gap-2">
              <Button size="sm" variant="outline" asChild><Link to={`/dashboard/itineraries/${it.id}`}>Open</Link></Button>
              <Button size="icon" variant="outline" aria-label={`Delete ${it.title}`} onClick={() => setToDelete(it)}><Trash2 className="w-4 h-4 text-destructive" /></Button>
            </div>
          </article>
        ))}
      </div>
      {data && <Pager page={page} pageSize={data.page_size} total={data.total} onPage={setPage} />}
      <ConfirmDialog open={!!toDelete} onOpenChange={o => !o && setToDelete(null)} title={`Delete ${toDelete?.title}?`} description="The itinerary will be removed from your trips."
        onConfirm={() => toDelete && del.mutate(toDelete.id, {
          onSuccess: () => { toast.success('Itinerary deleted'); setToDelete(null); },
          onError: e => toast.error(e instanceof ApiError ? e.message : 'Could not delete'),
        })} />
    </div>
  );
}
