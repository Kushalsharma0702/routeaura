import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { notificationsApi } from '@/lib/api/notifications';

/** The unread badge polls once a minute (no websocket yet). */
export const useUnreadCount = () => useQuery({ queryKey: ['unread'], queryFn: notificationsApi.unread, refetchInterval: 60_000, retry: false });
export const useNotifications = (p: { unread?: boolean; page?: number; page_size?: number }) =>
  useQuery({ queryKey: ['notifications', p], queryFn: () => notificationsApi.list(p), placeholderData: keepPreviousData });
const refresh = (qc: ReturnType<typeof useQueryClient>) => { qc.invalidateQueries({ queryKey: ['notifications'] }); qc.invalidateQueries({ queryKey: ['unread'] }); };
export const useMarkRead = () => { const qc = useQueryClient(); return useMutation({ mutationFn: (id: string) => notificationsApi.read(id), onSuccess: () => refresh(qc) }); };
export const useMarkAllRead = () => { const qc = useQueryClient(); return useMutation({ mutationFn: notificationsApi.readAll, onSuccess: () => refresh(qc) }); };
