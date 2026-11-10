import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { catalogApi, type AttractionInput, type AttractionQuery, type DestinationInput, type DestinationQuery } from '@/lib/api/catalog';

export const useCategories = () => useQuery({ queryKey: ['categories'], queryFn: catalogApi.categories, staleTime: 60_000 });
export const useDestinations = (p: DestinationQuery) =>
  useQuery({ queryKey: ['destinations', p], queryFn: () => catalogApi.destinations(p), placeholderData: keepPreviousData });
export const useDestination = (ref: string | undefined) =>
  useQuery({ queryKey: ['destination', ref], queryFn: () => catalogApi.destination(ref!), enabled: !!ref, retry: false });
export const useAttractions = (p: AttractionQuery, enabled = true) =>
  useQuery({ queryKey: ['attractions', p], queryFn: () => catalogApi.attractions(p), enabled, placeholderData: keepPreviousData });

export const useAdminDestinations = (p: { q?: string; page?: number; page_size?: number }) =>
  useQuery({ queryKey: ['admin-destinations', p], queryFn: () => catalogApi.admin.destinations(p), placeholderData: keepPreviousData });
export const useAdminDestination = (id: string | undefined) =>
  useQuery({ queryKey: ['admin-destination', id], queryFn: () => catalogApi.admin.destination(id!), enabled: !!id, retry: false });
export const useAdminAttractions = (p: { destination_id?: string; q?: string; page?: number; page_size?: number }) =>
  useQuery({ queryKey: ['admin-attractions', p], queryFn: () => catalogApi.admin.attractions(p), enabled: !!p.destination_id, placeholderData: keepPreviousData });

/** Every catalogue write invalidates all catalogue queries so lists, counts and details stay consistent. */
function useInvalidatingMutation<V, R>(fn: (v: V) => Promise<R>) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: fn,
    onSuccess: () => {
      for (const key of ['destinations', 'destination', 'attractions', 'categories', 'admin-destinations', 'admin-destination', 'admin-attractions']) {
        qc.invalidateQueries({ queryKey: [key] });
      }
    },
  });
}

export const useSaveDestination = () =>
  useInvalidatingMutation(({ id, data }: { id?: string; data: DestinationInput }) =>
    id ? catalogApi.admin.updateDestination(id, data) : catalogApi.admin.createDestination(data));
export const useDeleteDestination = () => useInvalidatingMutation((id: string) => catalogApi.admin.deleteDestination(id));
export const useSaveAttraction = () =>
  useInvalidatingMutation(({ id, data }: { id?: string; data: AttractionInput & { destination_id?: string } }) =>
    id ? catalogApi.admin.updateAttraction(id, data) : catalogApi.admin.createAttraction(data as AttractionInput & { destination_id: string }));
export const useDeleteAttraction = () => useInvalidatingMutation((id: string) => catalogApi.admin.deleteAttraction(id));
export const useSaveCategory = () =>
  useInvalidatingMutation(({ id, data }: { id?: string; data: { name: string; description?: string | null } }) =>
    id ? catalogApi.admin.updateCategory(id, data) : catalogApi.admin.createCategory(data));
export const useDeleteCategory = () => useInvalidatingMutation((id: string) => catalogApi.admin.deleteCategory(id));
