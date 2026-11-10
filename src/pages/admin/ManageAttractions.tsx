import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { ArrowLeft, Clock, Pencil, Plus, Search, Trash2 } from 'lucide-react';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';
import AttractionFormDialog from '@/components/admin/AttractionFormDialog';
import ConfirmDialog from '@/components/admin/ConfirmDialog';
import { EmptyState, ErrorState, Pager } from '@/components/QueryState';
import { ApiError } from '@/lib/api/client';
import type { Attraction } from '@/lib/api/catalog';
import { formatDuration, formatMinor } from '@/lib/format';
import { useAdminAttractions, useAdminDestination, useCategories, useDeleteAttraction } from '@/hooks/useCatalog';
import { useDebounced } from '@/hooks/useDebounced';

const PAGE_SIZE = 10;

export default function ManageAttractions() {
  const { id } = useParams();
  const dest = useAdminDestination(id);
  const categories = useCategories();
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<Attraction | null>(null);
  const [toDelete, setToDelete] = useState<Attraction | null>(null);
  const q = useDebounced(search.trim());
  useEffect(() => setPage(1), [q]);
  const list = useAdminAttractions({ destination_id: id, q: q || undefined, page, page_size: PAGE_SIZE });
  const del = useDeleteAttraction();

  if (dest.isLoading) return <Skeleton className="h-40 rounded-xl" />;
  if (dest.isError || !dest.data) {
    const notFound = dest.error instanceof ApiError && dest.error.status === 404;
    return <div className="space-y-4"><Back />{notFound ? <EmptyState title="Destination not found" /> : <ErrorState onRetry={() => dest.refetch()} />}</div>;
  }

  return (
    <div className="space-y-6 pb-24 lg:pb-0">
      <Back />
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-display font-bold text-foreground">Attractions · {dest.data.name}</h1>
          <p className="text-sm text-muted-foreground mt-1">{list.data ? `${list.data.total} attraction${list.data.total === 1 ? '' : 's'}` : 'Loading…'}</p>
        </div>
        <Button className="gradient-primary text-primary-foreground gap-2" onClick={() => { setEditing(null); setFormOpen(true); }}><Plus className="w-4 h-4" /> Add Attraction</Button>
      </div>
      <div className="relative max-w-sm">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
        <Input aria-label="Search attractions" placeholder="Search attractions…" value={search} className="pl-9" onChange={e => setSearch(e.target.value)} />
      </div>

      {list.isLoading && <div className="space-y-3" role="status" aria-label="Loading">{[0, 1, 2].map(i => <Skeleton key={i} className="h-20 rounded-xl" />)}</div>}
      {list.isError && <ErrorState message="We couldn't load attractions." onRetry={() => list.refetch()} />}
      {list.data?.items.length === 0 && <EmptyState title={q ? 'No attractions match your search' : 'No attractions yet'} hint={q ? undefined : 'Add the first attraction for this destination.'} />}

      <ul className="space-y-3">
        {list.data?.items.map(a => (
          <li key={a.id} className="bg-card rounded-xl border border-border/50 shadow-card p-4 flex flex-col sm:flex-row sm:items-center gap-3">
            <div className="flex-1 min-w-0 space-y-1">
              <div className="flex flex-wrap items-center gap-2">
                <h3 className="font-semibold text-card-foreground">{a.name}</h3>
                <span className="text-xs bg-primary/10 text-primary px-2 py-0.5 rounded-full">{a.category.name}</span>
                <span className={`text-xs px-2 py-0.5 rounded-full ${a.is_published ? 'bg-success/15 text-success' : 'bg-muted text-muted-foreground'}`}>{a.is_published ? 'Published' : 'Draft'}</span>
              </div>
              <p className="text-xs text-muted-foreground flex flex-wrap gap-x-4">
                <span className="flex items-center gap-1"><Clock className="w-3 h-3" />{formatDuration(a.typical_duration_minutes)}</span>
                <span>{a.is_outdoor ? 'Outdoor' : 'Indoor'}</span>
                <span>Entry: {a.estimated_cost_minor == null ? 'unknown' : formatMinor(a.estimated_cost_minor, a.currency)}</span>
                <span>{a.latitude.toFixed(4)}, {a.longitude.toFixed(4)}</span>
              </p>
            </div>
            <div className="flex gap-2">
              <Button size="sm" variant="outline" className="gap-1.5" onClick={() => { setEditing(a); setFormOpen(true); }}><Pencil className="w-3.5 h-3.5" />Edit</Button>
              <Button size="icon" variant="outline" aria-label={`Delete ${a.name}`} onClick={() => setToDelete(a)}><Trash2 className="w-4 h-4 text-destructive" /></Button>
            </div>
          </li>
        ))}
      </ul>
      {list.data && <Pager page={page} pageSize={PAGE_SIZE} total={list.data.total} onPage={setPage} />}

      <AttractionFormDialog open={formOpen} onOpenChange={setFormOpen} destinationId={dest.data.id} attraction={editing} categories={categories.data ?? []} />
      <ConfirmDialog open={!!toDelete} onOpenChange={o => !o && setToDelete(null)} title={`Delete ${toDelete?.name}?`}
        description="This attraction will be hidden from travelers."
        onConfirm={() => toDelete && del.mutate(toDelete.id, {
          onSuccess: () => { toast.success('Attraction deleted'); setToDelete(null); },
          onError: e => toast.error(e instanceof ApiError ? e.message : 'Could not delete attraction'),
        })} />
    </div>
  );
}

function Back() {
  return <Link to="/admin/destinations" className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground"><ArrowLeft className="w-4 h-4" />All destinations</Link>;
}
