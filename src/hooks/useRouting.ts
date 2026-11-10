import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { contextApi, type Report } from '@/lib/api/context';
import { optimizationApi, type Weights } from '@/lib/api/optimization';
import type { Itinerary } from '@/lib/api/itineraries';

export const useOptimizationHistory = (id: string) => useQuery({ queryKey: ['optimizations', id], queryFn: () => optimizationApi.history(id) });
export const useOptimize = (id: string) => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (v: { weights?: Partial<Weights>; improve?: boolean }) => optimizationApi.preview(id, v),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['optimizations', id] }),
  });
};
/** Applying a preview or approving a proposal returns the updated itinerary: cache it and refresh dependants. */
const useAppliedItinerary = (id: string, fn: (v: string) => Promise<Itinerary>) => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: fn,
    onSuccess: it => {
      qc.setQueryData(['itinerary', id], it);
      for (const k of ['itineraries', 'itinerary-versions', 'optimizations', 'adaptations', 'context']) qc.invalidateQueries({ queryKey: [k] });
    },
  });
};
export const useApplyOptimization = (id: string) => useAppliedItinerary(id, optimizationApi.apply);
export const useApproveProposal = (id: string) => useAppliedItinerary(id, contextApi.approve);

export const useContextStatus = (id: string) => useQuery({ queryKey: ['context', id], queryFn: () => contextApi.status(id) });
export const useRefreshContext = (id: string) => {
  const qc = useQueryClient();
  return useMutation({ mutationFn: () => contextApi.refresh(id), onSuccess: s => qc.setQueryData(['context', id], s) });
};
export const useReport = (id: string) => {
  const qc = useQueryClient();
  return useMutation({ mutationFn: (r: Report) => contextApi.report(id, r), onSuccess: s => qc.setQueryData(['context', id], s) });
};
export const useAdapt = (id: string) => {
  const qc = useQueryClient();
  return useMutation({ mutationFn: () => contextApi.adapt(id), onSuccess: () => { qc.invalidateQueries({ queryKey: ['adaptations', id] }); qc.invalidateQueries({ queryKey: ['context', id] }); } });
};
export const useProposals = (id: string) => useQuery({ queryKey: ['adaptations', id], queryFn: () => contextApi.proposals(id) });
export const useRejectProposal = (id: string) => {
  const qc = useQueryClient();
  return useMutation({ mutationFn: (pid: string) => contextApi.reject(pid), onSuccess: () => qc.invalidateQueries({ queryKey: ['adaptations', id] }) });
};
