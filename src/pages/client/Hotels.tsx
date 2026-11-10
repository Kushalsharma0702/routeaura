import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Search, Star } from 'lucide-react';
import { motion } from 'framer-motion';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { EmptyState, ErrorState, GridSkeleton, Pager } from '@/components/QueryState';
import { formatMinor } from '@/lib/format';
import { useDestinations } from '@/hooks/useCatalog';
import { useDebounced } from '@/hooks/useDebounced';
import { useHotels } from '@/hooks/useBookings';

const ALL = 'all';
const PAGE_SIZE = 9;

export default function Hotels() {
  const [search, setSearch] = useState('');
  const [destination, setDestination] = useState(ALL);
  const [stars, setStars] = useState(ALL);
  const [sort, setSort] = useState('name');
  const [page, setPage] = useState(1);
  const q = useDebounced(search.trim());
  useEffect(() => setPage(1), [q, destination, stars, sort]);
  const dests = useDestinations({ page: 1, page_size: 100, sort: 'name' });
  const { data, isLoading, isError, refetch } = useHotels({
    q: q || undefined, destination: destination === ALL ? undefined : destination, min_stars: stars === ALL ? undefined : Number(stars), sort, page, page_size: PAGE_SIZE,
  });
  const filtered = !!q || destination !== ALL || stars !== ALL;

  return (
    <div className="space-y-6 pb-24 lg:pb-0">
      <div><h1 className="text-2xl font-display font-bold text-foreground">Hotels</h1><p className="text-sm text-muted-foreground mt-1">Find a place to stay and book it</p></div>
      <div className="flex flex-col lg:flex-row gap-3">
        <div className="relative flex-1 max-w-sm"><Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
          <Input aria-label="Search hotels" placeholder="Search hotels…" value={search} className="pl-9" onChange={e => setSearch(e.target.value)} /></div>
        <Select value={destination} onValueChange={setDestination}><SelectTrigger className="w-full lg:w-48" aria-label="Destination"><SelectValue placeholder="Destination" /></SelectTrigger>
          <SelectContent><SelectItem value={ALL}>All destinations</SelectItem>{dests.data?.items.map(d => <SelectItem key={d.id} value={d.slug}>{d.name}</SelectItem>)}</SelectContent></Select>
        <Select value={stars} onValueChange={setStars}><SelectTrigger className="w-full lg:w-40" aria-label="Minimum stars"><SelectValue /></SelectTrigger>
          <SelectContent><SelectItem value={ALL}>Any rating</SelectItem>{[3, 4, 5].map(s => <SelectItem key={s} value={String(s)}>{s}★ and up</SelectItem>)}</SelectContent></Select>
        <Select value={sort} onValueChange={setSort}><SelectTrigger className="w-full lg:w-44" aria-label="Sort by"><SelectValue /></SelectTrigger>
          <SelectContent><SelectItem value="name">Name (A–Z)</SelectItem><SelectItem value="price">Price: low to high</SelectItem><SelectItem value="stars">Rating: high to low</SelectItem></SelectContent></Select>
      </div>
      {isLoading && <GridSkeleton count={PAGE_SIZE} height="h-64" />}
      {isError && <ErrorState message="We couldn't load hotels." onRetry={() => refetch()} />}
      {data?.items.length === 0 && <EmptyState title={filtered ? 'No hotels match your filters' : 'No hotels yet'} hint={filtered ? 'Try removing a filter.' : 'Check back soon.'} />}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {data?.items.map((h, i) => (
          <motion.div key={h.id} initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: Math.min(i, 8) * 0.04 }}>
            <Link to={`/dashboard/hotels/${h.slug}`} aria-label={`${h.name}, ${h.destination_name}`} className="block bg-card rounded-xl border border-border/50 shadow-card hover:shadow-card-hover transition-shadow overflow-hidden">
              <div className="relative h-32 gradient-primary flex items-end p-4 overflow-hidden">{h.images[0] && <img src={h.images[0]} alt="" loading="lazy" className="absolute inset-0 w-full h-full object-cover" />}<div className="absolute inset-0 bg-gradient-to-t from-foreground/70 to-transparent" /><span className="relative text-primary-foreground font-display font-semibold">{h.name}</span></div>
              <div className="p-4 space-y-2">
                <p className="text-sm text-muted-foreground">{h.destination_name}</p>
                <p className="flex items-center gap-1 text-sm">{h.star_rating ? Array.from({ length: h.star_rating }, (_, k) => <Star key={k} className="w-3.5 h-3.5 fill-warning text-warning" />) : null}<span className="sr-only">{h.star_rating} star hotel</span></p>
                <p className="text-sm">{h.from_price_minor == null ? 'No rooms listed' : <>From <strong>{formatMinor(h.from_price_minor, h.currency)}</strong> per night</>}</p>
                {h.source === 'seed' && <p className="text-[11px] text-muted-foreground">Illustrative listing with placeholder pricing.</p>}
              </div>
            </Link>
          </motion.div>
        ))}
      </div>
      {data && <Pager page={page} pageSize={PAGE_SIZE} total={data.total} onPage={setPage} />}
    </div>
  );
}
