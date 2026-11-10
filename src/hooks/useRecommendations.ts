import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  recommendationsApi, type FeedbackReason, type InteractionType, type Kind, type Rating,
  type RecommendationRequest, type RecommendationResponse,
} from '@/lib/api/recommendations';

/**
 * Each request creates a recommendation run on the server (history + impressions), so the query must
 * not refetch on focus/mount; it reruns only when the request changes or after an explicit refetch.
 */
export const useRecommendations = (kind: Kind, req: RecommendationRequest, enabled = true) =>
  useQuery({
    queryKey: ['recommendations', kind, req],
    queryFn: () => recommendationsApi.recommend(kind, req),
    enabled,
    staleTime: 10 * 60_000,
    refetchOnWindowFocus: false,
    refetchOnMount: false,
    refetchOnReconnect: false,
  });

export const useItemState = (kind: Kind, id: string | undefined) =>
  useQuery({ queryKey: ['item-state', kind, id], queryFn: () => recommendationsApi.itemState(kind, id!), enabled: !!id, retry: false });

export const useSavedItems = (kind?: Kind) =>
  useQuery({ queryKey: ['saved', kind], queryFn: () => recommendationsApi.saved({ item_type: kind, page_size: 50 }) });

export const useRunHistory = (page: number) =>
  useQuery({ queryKey: ['reco-history', page], queryFn: () => recommendationsApi.history({ page, page_size: 10 }) });

type InteractionVars = { kind: Kind; id: string; type: InteractionType; recommendationItemId?: string; source?: 'browse' | 'detail' | 'recommendation' | 'saved' };

/** Records an interaction and patches saved/liked flags in every cached recommendation list. */
export const useInteraction = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (v: InteractionVars) => recommendationsApi.interact({
      item_type: v.kind, item_id: v.id, interaction_type: v.type, source: v.source ?? 'browse', recommendation_item_id: v.recommendationItemId,
    }),
    onSuccess: (res, v) => {
      qc.setQueryData(['item-state', v.kind, v.id], res.state);
      qc.setQueriesData<RecommendationResponse>({ queryKey: ['recommendations', v.kind] }, old => old && ({
        ...old,
        items: old.items.map(i => ((i.destination ?? i.attraction)?.id === v.id
          ? { ...i, saved: res.state.saved, liked: res.state.liked, disliked: res.state.disliked } : i)),
      }));
      if (v.type === 'save' || v.type === 'unsave') qc.invalidateQueries({ queryKey: ['saved'] });
    },
  });
};

export const useFeedback = () =>
  useMutation({
    mutationFn: (v: { itemId: string; rating: Rating; reasons?: FeedbackReason[] }) =>
      recommendationsApi.feedback(v.itemId, v.rating, v.reasons ?? []),
  });
