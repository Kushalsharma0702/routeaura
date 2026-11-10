import { apiFetch } from './client';
import type { Attraction, Destination } from './catalog';
import type { Page } from './users';

export type Feature = 'interest' | 'budget' | 'duration' | 'climate' | 'season' | 'style';
export type Priority = 'ignore' | 'low' | 'normal' | 'high';
export type Strategy = 'weighted' | 'cosine' | 'popularity';
export type Kind = 'destination' | 'attraction';
export type Rating = 'relevant' | 'not_relevant';
export type FeedbackReason = 'not_my_interest' | 'too_expensive' | 'wrong_season' | 'wrong_climate' | 'already_visited' | 'other';
export type InteractionType = 'view' | 'click' | 'save' | 'unsave' | 'like' | 'dislike' | 'reaction_clear' | 'dismiss' | 'restore';

export interface PreferenceOverrides {
  budget_per_day_minor?: number | null;
  trip_duration_days?: number | null;
  interests?: string[] | null;
  preferred_climate?: string | null;
  preferred_season?: string | null;
  travel_month?: number | null;
  travel_style?: string | null;
}
export interface RecommendationRequest {
  overrides?: PreferenceOverrides;
  priorities?: Partial<Record<Feature, Priority>>;
  filters?: { category?: string; country?: string; climate?: string; max_cost_minor?: number; destination_id?: string; outdoor?: boolean };
  strategy?: Strategy;
  diversify?: boolean;
  diversity_lambda?: number;
  include_dismissed?: boolean;
  page?: number;
  page_size?: number;
}

export interface Component {
  feature: Feature; label: string; value: number | null; weight: number; contribution: number;
  status: 'matched' | 'partial' | 'mismatch' | 'unknown' | 'not_applicable'; detail: string;
}
export interface RecommendationItem {
  recommendation_item_id: string; kind: Kind; rank: number; original_rank: number;
  /** Relevance score for ranking (0-1). NOT a probability of satisfaction. */
  score: number;
  /** Share of the applicable criteria that could be evaluated with catalogue data (0-1). */
  confidence: number;
  destination: Destination | null; attraction: Attraction | null;
  components: Component[]; reasons: string[]; cautions: string[]; missing: string[];
  saved: boolean; liked: boolean; disliked: boolean; feedback: Rating | null;
}
export interface RecommendationResponse {
  run_id: string; kind: Kind; strategy: string; model_version: string; diversified: boolean;
  diversity_lambda: number | null; total_candidates: number; page: number; page_size: number;
  items: RecommendationItem[]; applied_preferences: Record<string, unknown>;
  effective_weights: Record<string, number>; notes: string[]; disclaimer: string;
}
export interface ItemState { saved: boolean; liked: boolean; disliked: boolean; dismissed: boolean }
export interface InteractionResult { recorded: boolean; state: ItemState }
export interface SavedItem { item_type: Kind; destination: Destination | null; attraction: Attraction | null }
export interface RunSummary {
  run_id: string; kind: Kind; strategy: string; model_version: string; created_at: string;
  total_candidates: number; returned_count: number; page: number; page_size: number; diversified: boolean;
  preferences: Record<string, unknown>; top_items: string[];
}

export const recommendationsApi = {
  recommend: (kind: Kind, req: RecommendationRequest) =>
    apiFetch<RecommendationResponse>(`/recommendations/${kind === 'destination' ? 'destinations' : 'attractions'}`, { method: 'POST', body: req }),
  feedback: (recommendation_item_id: string, rating: Rating, reasons: FeedbackReason[] = []) =>
    apiFetch<{ rating: Rating }>('/recommendations/feedback', { method: 'POST', body: { recommendation_item_id, rating, reasons } }),
  history: (p: { kind?: Kind; page?: number; page_size?: number }) =>
    apiFetch<Page<RunSummary>>('/recommendations/history', { params: { ...p } }),
  interact: (body: { item_type: Kind; item_id: string; interaction_type: InteractionType; source?: 'browse' | 'detail' | 'recommendation' | 'saved'; recommendation_item_id?: string }) =>
    apiFetch<InteractionResult>('/interactions', { method: 'POST', body }),
  itemState: (item_type: Kind, item_id: string) => apiFetch<ItemState>('/interactions/state', { params: { item_type, item_id } }),
  saved: (p: { item_type?: Kind; page?: number; page_size?: number }) => apiFetch<Page<SavedItem>>('/interactions/saved', { params: { ...p } }),
};
