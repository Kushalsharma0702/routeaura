import { useEffect, useState } from 'react';
import { Search } from 'lucide-react';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { useCategories, useDestinations } from '@/hooks/useCatalog';
import { useDebounced } from '@/hooks/useDebounced';
import DestinationCard from '@/components/catalog/DestinationCard';
import { EmptyState, ErrorState, GridSkeleton, Pager } from '@/components/QueryState';

const PAGE_SIZE = 9;
const ALL = 'all';
const CLIMATES = ['tropical', 'temperate', 'cold', 'arid'];
const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];

export default function BrowseDestinations() {
  const [search, setSearch] = useState('');
  const [category, setCategory] = useState(ALL);
  const [climate, setClimate] = useState(ALL);
  const [month, setMonth] = useState(ALL);
  const [sort, setSort] = useState('name');
  const [page, setPage] = useState(1);
  const q = useDebounced(search.trim());
  useEffect(() => setPage(1), [q, category, climate, month, sort]);

  const cats = useCategories();
  const { data, isLoading, isError, isFetching, refetch } = useDestinations({
    q: q || undefined, category: category === ALL ? undefined : category,
    climate: climate === ALL ? undefined : climate, month: month === ALL ? undefined : Number(month),
    sort, page, page_size: PAGE_SIZE,
  });
  const filtersActive = !!q || category !== ALL || climate !== ALL || month !== ALL;

  return (
    <div className="space-y-6 pb-24 lg:pb-0">
      <div>
        <h1 className="text-2xl font-display font-bold text-foreground">Destinations</h1>
        <p className="text-sm text-muted-foreground mt-1">Explore places to visit across the world</p>
      </div>

      <div className="flex flex-col lg:flex-row gap-3">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
          <Input aria-label="Search destinations" placeholder="Search destinations…" value={search} className="pl-9"
            onChange={e => setSearch(e.target.value)} />
        </div>
        <Select value={category} onValueChange={setCategory}>
          <SelectTrigger className="w-full lg:w-48" aria-label="Category"><SelectValue placeholder="Category" /></SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>All categories</SelectItem>
            {cats.data?.map(c => <SelectItem key={c.id} value={c.slug}>{c.name}</SelectItem>)}
          </SelectContent>
        </Select>
        <Select value={climate} onValueChange={setClimate}>
          <SelectTrigger className="w-full lg:w-40" aria-label="Climate"><SelectValue placeholder="Climate" /></SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>Any climate</SelectItem>
            {CLIMATES.map(c => <SelectItem key={c} value={c} className="capitalize">{c}</SelectItem>)}
          </SelectContent>
        </Select>
        <Select value={month} onValueChange={setMonth}>
          <SelectTrigger className="w-full lg:w-44" aria-label="Month of travel"><SelectValue placeholder="Month" /></SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>Any month</SelectItem>
            {MONTHS.map((m, i) => <SelectItem key={m} value={String(i + 1)}>{m}</SelectItem>)}
          </SelectContent>
        </Select>
        <Select value={sort} onValueChange={setSort}>
          <SelectTrigger className="w-full lg:w-44" aria-label="Sort by"><SelectValue placeholder="Sort" /></SelectTrigger>
          <SelectContent>
            <SelectItem value="name">Name (A–Z)</SelectItem>
            <SelectItem value="cost">Cost: low to high</SelectItem>
            <SelectItem value="-cost">Cost: high to low</SelectItem>
            <SelectItem value="newest">Newest</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {isLoading && <GridSkeleton count={PAGE_SIZE} />}
      {isError && <ErrorState message="We couldn't load destinations." onRetry={() => refetch()} />}
      {data && data.items.length === 0 && (
        <EmptyState title={filtersActive ? 'No destinations match your filters' : 'No destinations yet'}
          hint={filtersActive ? 'Try removing a filter or searching for something else.' : 'Check back soon.'} />
      )}
      {data && data.items.length > 0 && (
        <>
          <p className="text-sm text-muted-foreground" aria-live="polite">{data.total} destination{data.total === 1 ? '' : 's'}{isFetching ? ' · updating…' : ''}</p>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {data.items.map((d, i) => <DestinationCard key={d.id} dest={d} index={i} />)}
          </div>
          <Pager page={page} pageSize={PAGE_SIZE} total={data.total} onPage={setPage} />
        </>
      )}
    </div>
  );
}
