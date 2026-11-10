import { Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Calendar, Clock, MapPin, Wallet } from 'lucide-react';
import type { Destination } from '@/lib/api/catalog';
import { formatDistance, formatMinor, seasonLabel } from '@/lib/format';

export default function DestinationCard({ dest, index = 0 }: { dest: Destination; index?: number }) {
  return (
    <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: Math.min(index, 8) * 0.04 }}
      whileHover={{ y: -4, transition: { duration: 0.2 } }}>
      <Link to={`/dashboard/destinations/${dest.slug}`} aria-label={`${dest.name}, ${dest.country}`}
        className="group block bg-card rounded-xl border border-border/50 shadow-card overflow-hidden hover:shadow-card-hover transition-shadow">
        <div className="relative h-48 overflow-hidden bg-muted">
          {dest.images[0]
            ? <img src={dest.images[0]} alt="" loading="lazy" className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500" />
            : <div className="w-full h-full gradient-primary flex items-center justify-center"><MapPin className="w-10 h-10 text-primary-foreground/70" /></div>}
          <div className="absolute inset-0 bg-gradient-to-t from-foreground/70 to-transparent" />
          <div className="absolute bottom-4 left-4 right-4 text-primary-foreground">
            <h3 className="font-display font-semibold text-lg flex items-center gap-1.5"><MapPin className="w-4 h-4" />{dest.name}</h3>
            <p className="text-xs opacity-80">{[dest.region, dest.country].filter(Boolean).join(', ')}</p>
          </div>
          {dest.distance_m != null && (
            <span className="absolute top-3 right-3 text-xs bg-background/90 text-foreground rounded-full px-2.5 py-1">{formatDistance(dest.distance_m)} away</span>
          )}
        </div>
        <div className="p-4 space-y-3">
          <p className="text-sm text-muted-foreground line-clamp-2">{dest.description}</p>
          <div className="grid grid-cols-2 gap-2 text-xs text-muted-foreground">
            <span className="flex items-center gap-1.5"><Calendar className="w-3.5 h-3.5" />{seasonLabel(dest.best_season_start_month, dest.best_season_end_month)}</span>
            <span className="flex items-center gap-1.5"><Clock className="w-3.5 h-3.5" />{dest.recommended_duration_days ? `${dest.recommended_duration_days} days` : 'Flexible'}</span>
            <span className="flex items-center gap-1.5 col-span-2"><Wallet className="w-3.5 h-3.5" />~{formatMinor(dest.estimated_cost_per_day_minor, dest.currency)} / day <em className="opacity-70">(estimate)</em></span>
          </div>
          <div className="flex flex-wrap gap-1.5">
            {dest.categories.map(c => (
              <span key={c.id} className="text-xs bg-primary/15 text-primary border border-primary/20 px-2.5 py-1 rounded-full font-medium">{c.name}</span>
            ))}
          </div>
        </div>
      </Link>
    </motion.div>
  );
}
