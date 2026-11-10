import type { Feature, Priority, RecommendationRequest, Strategy } from '@/lib/api/recommendations';
import type { Preferences } from '@/lib/api/users';
import { minorToRupees, rupeesToMinor, splitList, toNum } from '@/lib/forms';

export const NONE = 'none';

export interface Controls {
  budget: string; days: string; month: string; climate: string; style: string; interests: string;
  priorities: Partial<Record<Feature, Priority>>; diversify: boolean; lambda: number; strategy: Strategy;
}

export const fromSaved = (p: Preferences | undefined): Controls => ({
  budget: minorToRupees(p?.budget_per_day_minor), days: p?.trip_duration_days?.toString() ?? '', month: NONE,
  climate: p?.preferred_climate ?? 'any', style: p?.travel_style ?? NONE, interests: (p?.interests ?? []).join(', '),
  priorities: {}, diversify: true, lambda: 0.7, strategy: 'weighted',
});

/** Only fields that differ from the saved preferences are sent as overrides. */
export function buildRequest(c: Controls, saved: Preferences | undefined): RecommendationRequest {
  const base = fromSaved(saved);
  const overrides: NonNullable<RecommendationRequest['overrides']> = {};
  if (c.budget.trim() !== base.budget.trim()) overrides.budget_per_day_minor = rupeesToMinor(c.budget);
  if (c.days.trim() !== base.days.trim()) overrides.trip_duration_days = toNum(c.days);
  if (c.climate !== base.climate) overrides.preferred_climate = c.climate === 'any' ? null : c.climate;
  if (c.style !== base.style) overrides.travel_style = c.style === NONE ? null : c.style;
  const wanted = splitList(c.interests).map(s => s.toLowerCase()).sort().join('|');
  if (wanted !== splitList(base.interests).map(s => s.toLowerCase()).sort().join('|')) overrides.interests = splitList(c.interests);
  if (c.month !== NONE) overrides.travel_month = Number(c.month);
  const priorities = Object.fromEntries(Object.entries(c.priorities).filter(([, v]) => v && v !== 'normal')) as RecommendationRequest['priorities'];
  return {
    ...(Object.keys(overrides).length ? { overrides } : {}),
    ...(priorities && Object.keys(priorities).length ? { priorities } : {}),
    strategy: c.strategy, diversify: c.diversify, ...(c.diversify ? { diversity_lambda: c.lambda } : {}),
  };
}

