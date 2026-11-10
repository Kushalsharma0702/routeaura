import { apiFetch, type ApiUser } from './client';

export interface Preferences {
  budget_per_day_minor: number | null;
  trip_duration_days: number | null;
  interests: string[];
  preferred_climate: string | null;
  preferred_season: string | null;
  group_size: number | null;
  travel_style: string | null;
  accommodation_preference: string | null;
  language: string;
}
export interface Page<T> { items: T[]; total: number; page: number; page_size: number }

export const usersApi = {
  updateMe: (data: { full_name?: string; phone?: string | null }) =>
    apiFetch<ApiUser>('/users/me', { method: 'PATCH', body: data }),
  getPreferences: () => apiFetch<Preferences>('/users/me/preferences'),
  setPreferences: (data: Preferences) =>
    apiFetch<Preferences>('/users/me/preferences', { method: 'PUT', body: data }),
  list: (params: { q?: string; page?: number; page_size?: number }) =>
    apiFetch<Page<ApiUser>>('/users', { params }),
  adminUpdate: (id: string, data: { role?: 'traveler' | 'admin'; is_active?: boolean }) =>
    apiFetch<ApiUser>(`/users/${id}`, { method: 'PATCH', body: data }),
};
