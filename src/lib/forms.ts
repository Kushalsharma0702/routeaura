import { z } from 'zod';

interface NumOpts { label: string; min: number; max: number; int?: boolean; required?: boolean }

/** String-typed numeric input (HTML inputs yield strings). Empty is allowed unless `required`. */
export const numField = ({ label, min, max, int, required }: NumOpts) =>
  z.string().trim().superRefine((v, ctx) => {
    if (v === '') {
      if (required) ctx.addIssue({ code: 'custom', message: `${label} is required` });
      return;
    }
    const n = Number(v);
    if (!Number.isFinite(n)) return void ctx.addIssue({ code: 'custom', message: 'Enter a number' });
    if (int && !Number.isInteger(n)) return void ctx.addIssue({ code: 'custom', message: 'Enter a whole number' });
    if (n < min || n > max) ctx.addIssue({ code: 'custom', message: `${label} must be between ${min} and ${max}` });
  });

export const toNum = (v: string): number | null => (v.trim() === '' ? null : Number(v));
export const rupeesToMinor = (v: string): number | null => (v.trim() === '' ? null : Math.round(Number(v) * 100));
export const minorToRupees = (m: number | null | undefined): string => (m == null ? '' : String(m / 100));

export const splitList = (v: string): string[] => v.split(/[\n,]/).map(s => s.trim()).filter(Boolean);
export const imageList = z.string().superRefine((v, ctx) => {
  const urls = splitList(v);
  if (urls.length > 12) ctx.addIssue({ code: 'custom', message: 'At most 12 images' });
  if (urls.some(u => !/^https?:\/\/\S+$/.test(u))) ctx.addIssue({ code: 'custom', message: 'Each image must be an http(s) URL' });
});
