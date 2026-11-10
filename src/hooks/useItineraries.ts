import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { itinerariesApi, type Itinerary, type TripRequest } from '@/lib/api/itineraries';

export const useItineraries = (page: number) =>
  useQuery({ queryKey: ['itineraries', page], queryFn: () => itinerariesApi.list({ page, page_size: 12 }) });
export const useItinerary = (id: string | undefined) =>
  useQuery({ queryKey: ['itinerary', id], queryFn: () => itinerariesApi.get(id!), enabled: !!id, retry: false });
export const useVersions = (id: string | undefined, version: number | undefined) =>
  useQuery({ queryKey: ['itinerary-versions', id, version], queryFn: () => itinerariesApi.versions(id!), enabled: !!id });

export const useGenerate = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (req: TripRequest) => itinerariesApi.generate(req),
    onSuccess: it => { qc.setQueryData(['itinerary', it.id], it); qc.invalidateQueries({ queryKey: ['itineraries'] }); },
  });
};

/** Every edit returns the full updated itinerary: cache it and refresh the list and version history. */
export const useItineraryMutation = <V,>(id: string, fn: (v: V) => Promise<Itinerary>) => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: fn,
    onSuccess: it => {
      qc.setQueryData(['itinerary', id], it);
      qc.invalidateQueries({ queryKey: ['itineraries'] });
      qc.invalidateQueries({ queryKey: ['itinerary-versions', id] });
    },
  });
};

export const useDeleteItinerary = () => {
  const qc = useQueryClient();
  return useMutation({ mutationFn: (id: string) => itinerariesApi.remove(id), onSuccess: () => qc.invalidateQueries({ queryKey: ['itineraries'] }) });
};
