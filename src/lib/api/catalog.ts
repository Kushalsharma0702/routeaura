import { apiFetch } from './client';
import type { Page } from './users';

export interface Category { id: string; slug: string; name: string; description?: string | null }
export type CategoryBrief = Pick<Category, 'id' | 'slug' | 'name'>;

export interface Destination {
  id: string; slug: string; name: string; country: string; region: string | null; description: string;
  latitude: number; longitude: number;
  estimated_cost_per_day_minor: number | null; currency: string;
  recommended_duration_days: number | null;
  best_season_start_month: number | null; best_season_end_month: number | null;
  climate: string | null; climate_notes: string | null; accessibility_notes: string | null;
  images: string[]; is_published: boolean;
  /** "seed"/"admin" = curated estimates; only "provider" is sourced data */
  source: string;
  categories: CategoryBrief[]; attraction_count: number; distance_m: number | null;
  created_at: string; updated_at: string; deleted_at: string | null;
}

export type OpeningHours = Record<string, string[][]>;
export interface Attraction {
  id: string; destination_id: string; slug: string; name: string; description: string;
  category: CategoryBrief; latitude: number; longitude: number;
  estimated_cost_minor: number | null; currency: string; typical_duration_minutes: number;
  opening_hours: OpeningHours | null; opening_hours_source: string | null;
  is_outdoor: boolean; accessibility_notes: string | null; images: string[];
  is_published: boolean; source: string; distance_m: number | null;
}

export type DestinationInput = Partial<Omit<Destination, 'id' | 'slug' | 'categories' | 'source' | 'currency' |
  'attraction_count' | 'distance_m' | 'created_at' | 'updated_at' | 'deleted_at'>> & { category_ids?: string[] };
export type AttractionInput = Partial<Omit<Attraction, 'id' | 'slug' | 'category' | 'currency' | 'source' |
  'distance_m' | 'opening_hours_source'>> & { category_id?: string };

export interface DestinationQuery {
  q?: string; country?: string; category?: string; climate?: string; month?: number;
  max_cost_minor?: number; sort?: string; page?: number; page_size?: number;
  lat?: number; lng?: number; radius_km?: number;
}
export interface AttractionQuery {
  q?: string; destination_id?: string; category?: string; outdoor?: boolean; sort?: string;
  page?: number; page_size?: number; lat?: number; lng?: number; radius_km?: number;
}

export const catalogApi = {
  categories: () => apiFetch<Category[]>('/categories'),
  destinations: (p: DestinationQuery) => apiFetch<Page<Destination>>('/destinations', { params: { ...p } }),
  destination: (ref: string) => apiFetch<Destination>(`/destinations/${encodeURIComponent(ref)}`),
  attractions: (p: AttractionQuery) => apiFetch<Page<Attraction>>('/attractions', { params: { ...p } }),

  admin: {
    destinations: (p: { q?: string; include_deleted?: boolean; page?: number; page_size?: number; sort?: string }) =>
      apiFetch<Page<Destination>>('/admin/destinations', { params: { ...p } }),
    destination: (id: string) => apiFetch<Destination>(`/admin/destinations/${id}`),
    createDestination: (d: DestinationInput) => apiFetch<Destination>('/admin/destinations', { method: 'POST', body: d }),
    updateDestination: (id: string, d: DestinationInput) =>
      apiFetch<Destination>(`/admin/destinations/${id}`, { method: 'PATCH', body: d }),
    deleteDestination: (id: string) => apiFetch<void>(`/admin/destinations/${id}`, { method: 'DELETE' }),

    attractions: (p: { destination_id?: string; q?: string; page?: number; page_size?: number }) =>
      apiFetch<Page<Attraction>>('/admin/attractions', { params: { ...p } }),
    createAttraction: (a: AttractionInput & { destination_id: string }) =>
      apiFetch<Attraction>('/admin/attractions', { method: 'POST', body: a }),
    updateAttraction: (id: string, a: AttractionInput) =>
      apiFetch<Attraction>(`/admin/attractions/${id}`, { method: 'PATCH', body: a }),
    deleteAttraction: (id: string) => apiFetch<void>(`/admin/attractions/${id}`, { method: 'DELETE' }),

    createCategory: (c: { name: string; description?: string | null }) =>
      apiFetch<Category>('/admin/categories', { method: 'POST', body: c }),
    updateCategory: (id: string, c: { name?: string; description?: string | null }) =>
      apiFetch<Category>(`/admin/categories/${id}`, { method: 'PATCH', body: c }),
    deleteCategory: (id: string) => apiFetch<void>(`/admin/categories/${id}`, { method: 'DELETE' }),
  },
};
