import type { OpeningHours } from '@/lib/api/catalog';

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
export const DAYS = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun'] as const;

/** Money is stored as integer minor units (paise). */
export const formatMinor = (minor: number | null | undefined, currency = 'INR') =>
  minor == null
    ? 'Not set'
    : new Intl.NumberFormat('en-IN', { style: 'currency', currency, maximumFractionDigits: 0 }).format(minor / 100);

export const seasonLabel = (start: number | null, end: number | null) =>
  start == null || end == null ? 'Year-round / not set' : `${MONTHS[start - 1]} – ${MONTHS[end - 1]}`;

export const formatDistance = (m: number | null | undefined) =>
  m == null ? '' : m < 1000 ? `${Math.round(m)} m` : `${(m / 1000).toFixed(m < 10_000 ? 1 : 0)} km`;

export const formatDuration = (minutes: number) =>
  minutes < 60 ? `${minutes} min` : `${Math.floor(minutes / 60)}h${minutes % 60 ? ` ${minutes % 60}m` : ''}`;

/** "09:00-17:00, 18:00-20:00" -> [["09:00","17:00"],["18:00","20:00"]]; "closed" -> []; "" -> undefined (unknown). */
export function parseDayHours(text: string): string[][] | undefined {
  const t = text.trim();
  if (!t) return undefined;
  if (/^closed$/i.test(t)) return [];
  return t.split(',').map(part => {
    const m = part.trim().match(/^([01]\d|2[0-3]):([0-5]\d)\s*-\s*([01]\d|2[0-3]):([0-5]\d)$/);
    if (!m) throw new Error(`Invalid time range "${part.trim()}" (use HH:MM-HH:MM)`);
    const span = [`${m[1]}:${m[2]}`, `${m[3]}:${m[4]}`];
    if (span[0] >= span[1]) throw new Error(`Opening must be before closing in "${part.trim()}"`);
    return span;
  });
}

export function hoursToText(hours: OpeningHours | null, day: string): string {
  const spans = hours?.[day];
  if (spans === undefined) return '';
  return spans.length === 0 ? 'closed' : spans.map(s => `${s[0]}-${s[1]}`).join(', ');
}
