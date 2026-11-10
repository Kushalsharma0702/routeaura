import { apiFetch } from './client';
import type { Page } from './users';

export interface AppNotification { id: string; type: string; title: string; body: string; data: Record<string, unknown>; read_at: string | null; created_at: string }
export const notificationsApi = {
  list: (p: { unread?: boolean; page?: number; page_size?: number }) => apiFetch<Page<AppNotification>>('/notifications', { params: { ...p } }),
  unread: () => apiFetch<{ unread: number }>('/notifications/unread-count'),
  read: (id: string) => apiFetch<AppNotification>(`/notifications/${id}/read`, { method: 'POST' }),
  readAll: () => apiFetch<{ marked: number }>('/notifications/read-all', { method: 'POST' }),
};
