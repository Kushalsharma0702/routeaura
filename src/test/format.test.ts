import { describe, expect, it } from 'vitest';
import { z } from 'zod';
import { formatDistance, formatDuration, formatMinor, hoursToText, parseDayHours, seasonLabel } from '@/lib/format';
import { imageList, minorToRupees, numField, rupeesToMinor, splitList, toNum } from '@/lib/forms';

describe('format helpers', () => {
  it('formats money from minor units and unknowns', () => {
    expect(formatMinor(320000)).toBe('₹3,200');
    expect(formatMinor(null)).toBe('Not set');
  });
  it('labels seasons, including wrap-around', () => {
    expect(seasonLabel(10, 3)).toBe('Oct – Mar');
    expect(seasonLabel(null, null)).toMatch(/not set/i);
  });
  it('formats distances and durations', () => {
    expect(formatDistance(250)).toBe('250 m');
    expect(formatDistance(1500)).toBe('1.5 km');
    expect(formatDistance(48_000)).toBe('48 km');
    expect(formatDuration(45)).toBe('45 min');
    expect(formatDuration(150)).toBe('2h 30m');
  });
});

describe('opening hours parsing', () => {
  it('parses ranges, closed and unknown', () => {
    expect(parseDayHours('09:00-17:00')).toEqual([['09:00', '17:00']]);
    expect(parseDayHours('09:00-12:00, 14:00-18:30')).toEqual([['09:00', '12:00'], ['14:00', '18:30']]);
    expect(parseDayHours('Closed')).toEqual([]);
    expect(parseDayHours('  ')).toBeUndefined();
  });
  it('rejects malformed or reversed ranges', () => {
    expect(() => parseDayHours('9am-5pm')).toThrow(/HH:MM/);
    expect(() => parseDayHours('18:00-09:00')).toThrow(/before closing/);
    expect(() => parseDayHours('25:00-26:00')).toThrow();
  });
  it('round-trips to text', () => {
    expect(hoursToText({ mon: [['09:00', '17:00']], sun: [] }, 'mon')).toBe('09:00-17:00');
    expect(hoursToText({ mon: [['09:00', '17:00']], sun: [] }, 'sun')).toBe('closed');
    expect(hoursToText({ mon: [] }, 'tue')).toBe('');
    expect(hoursToText(null, 'mon')).toBe('');
  });
});

describe('form helpers', () => {
  const lat = numField({ label: 'Latitude', min: -90, max: 90, required: true });
  const msg = (s: z.ZodString | z.ZodEffects<z.ZodString>, v: string) => {
    const r = s.safeParse(v);
    return r.success ? null : r.error.issues[0].message;
  };
  it('validates coordinates', () => {
    expect(msg(lat, '26.9')).toBeNull();
    expect(msg(lat, '90')).toBeNull();
    expect(msg(lat, '90.1')).toMatch(/between -90 and 90/);
    expect(msg(lat, '-91')).toMatch(/between/);
    expect(msg(lat, 'abc')).toBe('Enter a number');
    expect(msg(lat, '')).toBe('Latitude is required');
  });
  it('treats empty optional numbers as unset and enforces whole numbers', () => {
    expect(msg(numField({ label: 'Days', min: 1, max: 60, int: true }), '')).toBeNull();
    expect(msg(numField({ label: 'Days', min: 1, max: 60, int: true }), '2.5')).toBe('Enter a whole number');
  });
  it('converts rupees and minor units without float drift', () => {
    expect(rupeesToMinor('3200')).toBe(320000);
    expect(rupeesToMinor('19.99')).toBe(1999);
    expect(rupeesToMinor('')).toBeNull();
    expect(minorToRupees(320000)).toBe('3200');
    expect(toNum(' 4 ')).toBe(4);
    expect(toNum('')).toBeNull();
  });
  it('validates image lists', () => {
    expect(imageList.safeParse('https://a.io/x.jpg\nhttp://b.io/y.png').success).toBe(true);
    expect(imageList.safeParse('javascript:alert(1)').success).toBe(false);
    expect(imageList.safeParse(Array(13).fill('https://a.io/x.jpg').join('\n')).success).toBe(false);
    expect(splitList('a, b\n c')).toEqual(['a', 'b', 'c']);
  });
});
