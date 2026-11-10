import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Calendar, ListChecks, MapPin, Pencil, Plus, Search, Tags, Trash2 } from 'lucide-react';
import { motion } from 'framer-motion';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import CategoriesDialog from '@/components/admin/CategoriesDialog';
import ConfirmDialog from '@/components/admin/ConfirmDialog';
import DestinationFormDialog from '@/components/admin/DestinationFormDialog';
import { EmptyState, ErrorState, GridSkeleton, Pager } from '@/components/QueryState';
import { ApiError } from '@/lib/api/client';
import type { Destination } from '@/lib/api/catalog';
import { seasonLabel } from '@/lib/format';
import { useAdminDestinations, useCategories, useDeleteDestination } from '@/hooks/useCatalog';
import { useDebounced } from '@/hooks/useDebounced';

const PAGE_SIZE = 9;

export default function ManageDestinations() {
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<Destination | null>(null);
  const [catsOpen, setCatsOpen] = useState(false);
  const [toDelete, setToDelete] = useState<Destination | null>(null);
  const q = useDebounced(search.trim());
  useEffect(() => setPage(1), [q]);

  const { data, isLoading, isError, refetch } = useAdminDestinations({ q: q || undefined, page, page_size: PAGE_SIZE });
  const categories = useCategories();
  const del = useDeleteDestination();

  const openForm = (d: Destination | null) => { setEditing(d); setFormOpen(true); };

  return (
    <div className="space-y-6 pb-24 lg:pb-0">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-display font-bold text-foreground">Destinations</h1>
          <p className="text-sm text-muted-foreground mt-1">{data ? `${data.total} travel destination${data.total === 1 ? '' : 's'}` : 'Loading…'}</p>
        </div>
        <div className="flex gap-3">
          <Button variant="outline" className="gap-2" onClick={() => setCatsOpen(true)}><Tags className="w-4 h-4" /> Categories</Button>
          <Button className="gradient-primary text-primary-foreground gap-2" onClick={() => openForm(null)}><Plus className="w-4 h-4" /> Add Destination</Button>
        </div>
      </div>

      <div className="relative max-w-sm">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
        <Input aria-label="Search destinations" placeholder="Search destinations…" value={search} className="pl-9" onChange={e => setSearch(e.target.value)} />
      </div>

      {isLoading && <GridSkeleton count={6} height="h-80" />}
      {isError && <ErrorState message="We couldn't load destinations." onRetry={() => refetch()} />}
      {data?.items.length === 0 && (
        <EmptyState title={q ? 'No destinations match your search' : 'No destinations yet'} hint={q ? undefined : 'Create the first destination to get started.'} />
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {data?.items.map((dest, i) => (
          <motion.div key={dest.id} initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.04 }}
            className="bg-card rounded-xl border border-border/50 shadow-card overflow-hidden flex flex-col">
            <div className="relative h-44 overflow-hidden bg-muted">
              {dest.images[0]
                ? <img src={dest.images[0]} alt="" loading="lazy" className="w-full h-full object-cover" />
                : <div className="w-full h-full gradient-primary" />}
              <div className="absolute inset-0 bg-gradient-to-t from-foreground/70 to-transparent" />
              <span className={`absolute top-3 right-3 text-xs px-2.5 py-1 rounded-full font-medium ${dest.is_published ? 'bg-success/90 text-white' : 'bg-background/90 text-foreground'}`}>
                {dest.is_published ? 'Published' : 'Draft'}
              </span>
              <div className="absolute bottom-4 left-4 text-primary-foreground">
                <h3 className="font-display font-semibold text-lg flex items-center gap-1.5"><MapPin className="w-4 h-4" />{dest.name}</h3>
                <p className="text-xs opacity-80">{[dest.region, dest.country].filter(Boolean).join(', ')}</p>
              </div>
            </div>
            <div className="p-4 space-y-3 flex-1">
              <div className="flex items-center gap-2 text-xs text-muted-foreground">
                <Calendar className="w-3.5 h-3.5" /><span>Best: {seasonLabel(dest.best_season_start_month, dest.best_season_end_month)}</span>
                <span className="ml-auto">{dest.attraction_count} attraction{dest.attraction_count === 1 ? '' : 's'}</span>
              </div>
              <div className="flex flex-wrap gap-1.5">
                {dest.categories.map(c => <span key={c.id} className="text-xs bg-primary/15 text-primary border border-primary/20 px-2.5 py-1 rounded-full font-medium">{c.name}</span>)}
              </div>
            </div>
            <div className="flex gap-2 p-4 pt-0">
              <Button size="sm" variant="outline" className="gap-1.5 flex-1" onClick={() => openForm(dest)}><Pencil className="w-3.5 h-3.5" />Edit</Button>
              <Button size="sm" variant="outline" className="gap-1.5 flex-1" asChild>
                <Link to={`/admin/destinations/${dest.id}/attractions`}><ListChecks className="w-3.5 h-3.5" />Attractions</Link>
              </Button>
              <Button size="icon" variant="outline" aria-label={`Delete ${dest.name}`} onClick={() => setToDelete(dest)}><Trash2 className="w-4 h-4 text-destructive" /></Button>
            </div>
          </motion.div>
        ))}
      </div>
      {data && <Pager page={page} pageSize={PAGE_SIZE} total={data.total} onPage={setPage} />}

      <DestinationFormDialog open={formOpen} onOpenChange={setFormOpen} destination={editing} categories={categories.data ?? []} />
      <CategoriesDialog open={catsOpen} onOpenChange={setCatsOpen} />
      <ConfirmDialog open={!!toDelete} onOpenChange={o => !o && setToDelete(null)}
        title={`Delete ${toDelete?.name}?`} description="The destination and its attractions will be hidden from travelers. This can be restored only from the database."
        onConfirm={() => toDelete && del.mutate(toDelete.id, {
          onSuccess: () => { toast.success('Destination deleted'); setToDelete(null); },
          onError: e => toast.error(e instanceof ApiError ? e.message : 'Could not delete destination'),
        })} />
    </div>
  );
}
