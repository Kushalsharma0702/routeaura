import { describe, expect, it } from 'vitest';
import { buildRequest, fromSaved } from '@/lib/recoControls';
import { PREFS } from './utils';

describe('recommendation request building', () => {
  it('sends no overrides when nothing changed from the saved preferences', () => {
    const req = buildRequest(fromSaved(PREFS), PREFS);
    expect(req.overrides).toBeUndefined();
    expect(req.priorities).toBeUndefined();
    expect(req).toMatchObject({ strategy: 'weighted', diversify: true, diversity_lambda: 0.7 });
  });

  it('sends only the fields the user changed, converting rupees to minor units', () => {
    const c = { ...fromSaved(PREFS), budget: '2500', month: '7', interests: 'Beach, nature' };
    expect(buildRequest(c, PREFS).overrides).toEqual({ budget_per_day_minor: 250000, travel_month: 7, interests: ['Beach', 'nature'] });
  });

  it('treats interest order and case as unchanged', () => {
    const c = { ...fromSaved(PREFS), interests: 'Food,  HISTORY' };
    expect(buildRequest(c, PREFS).overrides).toBeUndefined();
  });

  it('clears values explicitly with null (blank budget, no climate, no style)', () => {
    const c = { ...fromSaved(PREFS), budget: '', climate: 'any', style: 'none', days: '' };
    expect(buildRequest(c, PREFS).overrides).toEqual({
      budget_per_day_minor: null, preferred_climate: null, travel_style: null, trip_duration_days: null });
  });

  it('includes only non-normal priorities, the chosen strategy and the variety setting', () => {
    const c = { ...fromSaved(PREFS), priorities: { budget: 'high', interest: 'normal', season: 'ignore' } as const, strategy: 'cosine' as const, diversify: false, lambda: 0.4 };
    const req = buildRequest(c, PREFS);
    expect(req.priorities).toEqual({ budget: 'high', season: 'ignore' });
    expect(req.strategy).toBe('cosine');
    expect(req.diversify).toBe(false);
    expect(req.diversity_lambda).toBeUndefined();
  });

  it('works before saved preferences have loaded', () => {
    expect(buildRequest(fromSaved(undefined), undefined)).toMatchObject({ strategy: 'weighted' });
  });
});
