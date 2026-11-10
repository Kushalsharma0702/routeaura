import { useState } from 'react';
import { Link } from 'react-router-dom';
import { AlertTriangle, Bookmark, BookmarkCheck, Check, ChevronDown, EyeOff, HelpCircle, Info, MapPin, ThumbsDown, ThumbsUp } from 'lucide-react';
import { motion } from 'framer-motion';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@/components/ui/dropdown-menu';
import { ApiError } from '@/lib/api/client';
import type { FeedbackReason, RecommendationItem } from '@/lib/api/recommendations';
import { formatDistance, formatDuration, formatMinor, seasonLabel } from '@/lib/format';
import { useFeedback, useInteraction } from '@/hooks/useRecommendations';

const REASONS: [FeedbackReason, string][] = [
  ['not_my_interest', 'Not my interest'], ['too_expensive', 'Too expensive'], ['wrong_season', 'Wrong season'],
  ['wrong_climate', 'Wrong climate'], ['already_visited', 'Already visited'], ['other', 'Other'],
];
const STATUS_STYLE: Record<string, string> = {
  matched: 'bg-success/15 text-success', partial: 'bg-warning/15 text-warning', mismatch: 'bg-destructive/10 text-destructive',
  unknown: 'bg-muted text-muted-foreground', not_applicable: 'bg-muted text-muted-foreground',
};
const STATUS_LABEL: Record<string, string> = { matched: 'Good match', partial: 'Partial', mismatch: 'Poor match', unknown: 'No data', not_applicable: 'Not used' };
const errMsg = (e: unknown) => (e instanceof ApiError ? e.message : 'Something went wrong. Please try again.');

export default function RecommendationCard({ item, index = 0, compact = false, onDismissed, onRestored }: {
  item: RecommendationItem; index?: number; compact?: boolean;
  onDismissed?: (itemId: string) => void; onRestored?: (itemId: string) => void;
}) {
  const place = item.destination ?? item.attraction;
  const interaction = useInteraction();
  const feedback = useFeedback();
  const [rating, setRating] = useState(item.feedback);
  const [open, setOpen] = useState(false);
  if (!place) return null;

  const isDest = item.kind === 'destination';
  const href = `/dashboard/destinations/${isDest ? item.destination!.slug : item.attraction!.destination_id}`;
  const pct = Math.round(item.score * 100);
  const coverage = Math.round(item.confidence * 100);
  const used = item.components.filter(c => c.status !== 'not_applicable');
  const image = place.images[0];
  const act = (type: 'save' | 'unsave' | 'click' | 'dismiss' | 'restore') =>
    interaction.mutateAsync({ kind: item.kind, id: place.id, type, recommendationItemId: item.recommendation_item_id, source: 'recommendation' });

  const toggleSave = async () => {
    try { await act(item.saved ? 'unsave' : 'save'); toast.success(item.saved ? 'Removed from saved' : 'Saved'); }
    catch (e) { toast.error(errMsg(e)); }
  };
  const dismiss = async () => {
    try {
      await act('dismiss');
      onDismissed?.(item.recommendation_item_id);
      toast('Hidden from your recommendations', {
        action: { label: 'Undo', onClick: () => act('restore').then(() => onRestored?.(item.recommendation_item_id)).catch(e => toast.error(errMsg(e))) },
      });
    } catch (e) { toast.error(errMsg(e)); }
  };
  const rate = (r: 'relevant' | 'not_relevant', reasons: FeedbackReason[] = []) =>
    feedback.mutate({ itemId: item.recommendation_item_id, rating: r, reasons }, {
      onSuccess: () => { setRating(r); toast.success('Thanks, your feedback helps tune your recommendations'); },
      onError: e => toast.error(errMsg(e)),
    });

  return (
    <motion.article aria-label={`Recommendation ${item.rank}: ${place.name}`} initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}
      transition={{ delay: Math.min(index, 8) * 0.04 }}
      className="bg-card rounded-xl border border-border/50 shadow-card overflow-hidden flex flex-col">
      <Link to={href} onClick={() => { void act('click').catch(() => undefined); }} className="relative block h-40 bg-muted" aria-label={`Open ${place.name}`}>
        {image ? <img src={image} alt="" loading="lazy" className="w-full h-full object-cover" />
          : <div className="w-full h-full gradient-primary flex items-center justify-center"><MapPin className="w-9 h-9 text-primary-foreground/70" /></div>}
        <div className="absolute inset-0 bg-gradient-to-t from-foreground/70 to-transparent" />
        <span className="absolute top-3 left-3 text-xs font-semibold bg-background/90 text-foreground rounded-full px-2.5 py-1">#{item.rank}</span>
        <div className="absolute bottom-3 left-4 right-4 text-primary-foreground">
          <h3 className="font-display font-semibold text-lg leading-tight">{place.name}</h3>
          <p className="text-xs opacity-80">
            {isDest ? [item.destination!.region, item.destination!.country].filter(Boolean).join(', ') : item.attraction!.category.name}
          </p>
        </div>
      </Link>

      <div className="p-4 space-y-3 flex-1">
        <div>
          <div className="flex items-center justify-between text-sm">
            <span className="font-medium text-card-foreground flex items-center gap-1.5">
              Match {pct}%
              <span title="A relevance score used to rank places for you. It is not a probability that you will like a place." aria-label="About the match score">
                <HelpCircle className="w-3.5 h-3.5 text-muted-foreground" />
              </span>
            </span>
            {used.length > 0 && <span className="text-xs text-muted-foreground">Based on {coverage}% of your criteria</span>}
          </div>
          <div role="meter" aria-label="Match score" aria-valuemin={0} aria-valuemax={100} aria-valuenow={pct} className="mt-1.5 h-2 rounded-full bg-muted overflow-hidden">
            <div className="h-full rounded-full gradient-primary" style={{ width: `${pct}%` }} />
          </div>
        </div>

        <ul className="space-y-1.5 text-sm">
          {item.reasons.slice(0, compact ? 2 : 3).map(r => (
            <li key={r} className="flex gap-2 text-card-foreground"><Check className="w-4 h-4 text-success shrink-0 mt-0.5" />{r}</li>
          ))}
          {!compact && item.cautions.slice(0, 2).map(c => (
            <li key={c} className="flex gap-2 text-muted-foreground"><AlertTriangle className="w-4 h-4 text-warning shrink-0 mt-0.5" />{c}</li>
          ))}
          {!compact && item.missing.length > 0 && (
            <li className="flex gap-2 text-muted-foreground"><Info className="w-4 h-4 shrink-0 mt-0.5" />Missing data: {item.missing.length} of your criteria could not be checked for this place.</li>
          )}
          {item.reasons.length === 0 && item.cautions.length === 0 && item.missing.length === 0 && (
            <li className="text-muted-foreground">No personalised reasons available yet.</li>
          )}
        </ul>

        <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
          {isDest ? (
            <>
              <span>Best: {seasonLabel(item.destination!.best_season_start_month, item.destination!.best_season_end_month)}</span>
              <span>~{formatMinor(item.destination!.estimated_cost_per_day_minor, item.destination!.currency)}/day (estimate)</span>
            </>
          ) : (
            <>
              <span>{formatDuration(item.attraction!.typical_duration_minutes)}</span>
              <span>Entry: {item.attraction!.estimated_cost_minor == null ? 'unknown' : formatMinor(item.attraction!.estimated_cost_minor)}</span>
              {item.attraction!.distance_m != null && <span>{formatDistance(item.attraction!.distance_m)}</span>}
            </>
          )}
        </div>

        {!compact && used.length > 0 && (
          <Collapsible open={open} onOpenChange={setOpen}>
            <CollapsibleTrigger className="flex items-center gap-1 text-xs font-medium text-primary hover:underline">
              Why this? <ChevronDown className={`w-3.5 h-3.5 transition-transform ${open ? 'rotate-180' : ''}`} />
            </CollapsibleTrigger>
            <CollapsibleContent>
              <ul className="mt-2 space-y-2">
                {used.map(c => (
                  <li key={c.feature} className="text-xs border-t border-border/40 pt-2">
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-medium text-card-foreground">{c.label} <span className="text-muted-foreground font-normal">· weight {Math.round(c.weight * 100)}%</span></span>
                      <span className={`px-2 py-0.5 rounded-full ${STATUS_STYLE[c.status]}`}>{STATUS_LABEL[c.status]}</span>
                    </div>
                    <p className="text-muted-foreground mt-1">{c.detail}</p>
                  </li>
                ))}
              </ul>
            </CollapsibleContent>
          </Collapsible>
        )}
      </div>

      <div className="flex items-center gap-1 px-3 pb-3">
        <Button size="sm" variant={item.saved ? 'secondary' : 'outline'} className="gap-1.5" onClick={toggleSave} disabled={interaction.isPending}
          aria-pressed={item.saved}>
          {item.saved ? <BookmarkCheck className="w-4 h-4" /> : <Bookmark className="w-4 h-4" />}{item.saved ? 'Saved' : 'Save'}
        </Button>
        {!compact && (
          <>
            <Button size="icon" variant={rating === 'relevant' ? 'secondary' : 'ghost'} aria-label="Relevant" aria-pressed={rating === 'relevant'}
              disabled={feedback.isPending} onClick={() => rate('relevant')}><ThumbsUp className="w-4 h-4" /></Button>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button size="icon" variant={rating === 'not_relevant' ? 'secondary' : 'ghost'} aria-label="Not relevant" aria-pressed={rating === 'not_relevant'} disabled={feedback.isPending}>
                  <ThumbsDown className="w-4 h-4" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="start">
                {REASONS.map(([value, label]) => <DropdownMenuItem key={value} onSelect={() => rate('not_relevant', [value])}>{label}</DropdownMenuItem>)}
              </DropdownMenuContent>
            </DropdownMenu>
          </>
        )}
        <Button size="sm" variant="ghost" className="gap-1.5 ml-auto text-muted-foreground" onClick={dismiss} disabled={interaction.isPending} aria-label={`Hide ${place.name}`}>
          <EyeOff className="w-4 h-4" />Hide
        </Button>
      </div>
    </motion.article>
  );
}
