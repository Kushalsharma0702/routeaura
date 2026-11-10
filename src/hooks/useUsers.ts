import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { usersApi, type Preferences } from '@/lib/api/users';

export const usePreferences = () =>
  useQuery({ queryKey: ['preferences'], queryFn: usersApi.getPreferences });

export const useSavePreferences = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (p: Preferences) => usersApi.setPreferences(p),
    onSuccess: (data) => qc.setQueryData(['preferences'], data),
  });
};

export const useAdminUsers = (q: string, page: number) =>
  useQuery({ queryKey: ['admin-users', q, page], queryFn: () => usersApi.list({ q, page, page_size: 12 }) });

export const useAdminUpdateUser = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...data }: { id: string; role?: 'traveler' | 'admin'; is_active?: boolean }) =>
      usersApi.adminUpdate(id, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['admin-users'] }),
  });
};
