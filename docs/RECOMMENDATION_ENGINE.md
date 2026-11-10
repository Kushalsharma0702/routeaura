# Recommendation Engine

Deterministic, explainable, LLM-free. Code: `backend/app/modules/recommendations/engine/` (pure Python, no DB imports) and `service.py` (DB orchestration).

## Pipeline
1. **Feature engineering** (`features.py`): categories become sparse vectors over the catalogue category vocabulary (destinations blend their own categories with the category mix of their published attractions, `attraction_blend = 0.5`); costs are min-max normalised and percentile-ranked across the catalogue; seasons become month sets (wrapping over the new year, e.g. Oct-Mar); climates/styles are categorical. **Unknown stays unknown**: a missing cost/season/climate/duration/category is `None`, never a default value.
2. **User profile**: saved preferences + per-request overrides (`overrides` fields that are *sent*, even as null, replace saved values). Free-text interests are matched to categories by lightly-stemmed token overlap plus a small synonym table; unmatched interests are reported back. Interaction history is blended in: `interest = alpha*stated + (1-alpha)*history`, minus `beta*avoid` (alpha 0.7, beta 0.3).
3. **Scoring** (`scoring.py`): `score = sum_f(w_f * v_f) / sum_f(w_f)` over the features the **user** specified.

| Feature | Value in [0,1] |
|---|---|
| interest | cosine(user interest vector, item category vector) |
| budget | destination: 1 within budget, then linear to 0 at +50% (`budget_overrun_tolerance`); attraction: entry fee <= 25% of the daily budget scores 1, falling to 0 at 100% |
| duration | 1 within +-1 day of the recommended length, else min/max ratio |
| climate | 1 exact; judgement-based similarity matrix for neighbours (`CLIMATE_SIMILARITY`); destination climate "any" = 0.75 |
| season | share of the user's months (explicit month, or a named season's months) inside the item's best season |
| style | derived from catalogue data: budget/luxury/comfort from cost percentile; adventure/relaxed from category mix and outdoor share |

Default weights: interest .35, budget .20, season .15, duration .10, climate .10, style .10. Explicit priorities scale a weight by 0 / 0.5 / 1 / 2 (`ignore/low/normal/high`).

## Missing data policy (the honesty rules)
* Feature **not applicable** (the user did not set it): takes no weight; weights renormalise.
* Feature **unknown** (the user set it, the catalogue cannot answer): under the default `lower_bound` policy it contributes 0, so missing data can never raise a score; `confidence` reports the share of applicable weight that was backed by data. `renormalize` (drop the unknowns) exists for experiments and scores worse in our evaluation (see research doc).
* A clearly over-budget item (budget value 0) is multiplied by `budget_incompatible_multiplier = 0.6`.
* The score ranks items against each other. **It is not a probability of satisfaction**, and every API response and card says so.

## Ranking
Deterministic order: score, confidence, name, id. **Diversity**: Maximal Marginal Relevance over the top `5k` candidates, `lambda*relevance - (1-lambda)*max cosine to already-selected` (default lambda 0.7; lambda = 1 reproduces the plain ranking). Item similarity uses the category vector plus climate and normalised cost.

## Cold start and fallbacks
No usable preference and no history -> `strategy = popularity_fallback`: items ranked by aggregate interaction counts (view 1, click 2, save 3, like 3, minus dislike 2/dismiss 1) across all users (aggregates only, never per-user data), clearly labelled. Trip length alone is not a signal for attractions.

## Explanations
Each item returns per-feature `components` (value, normalised weight, contribution, status `matched|partial|mismatch|unknown|not_applicable`, human-readable detail), plus `reasons`, `cautions`, `missing`, `score`, `confidence`, `rank`, `original_rank` (before diversification). They are persisted with the impression (`recommendation_items.explanation`).

## Interactions and feedback
`user_interactions` is an append-only event log (view, click, save/unsave, like/dislike/reaction_clear, dismiss/restore). State-changing events are idempotent; repeated views within 10 minutes are ignored. Evidence decays with a 90-day half-life, repeated views/clicks cap at 3, total evidence per item caps at +-2. Dismissed/disliked items are hidden unless `include_dismissed`. `recommendation_feedback` stores one rating per user and impression (`relevant|not_relevant` + reasons), and feeds the history signal (+-0.7).

## Not scored (and why)
`group_size`, `accommodation_preference`: the catalogue has no per-group or accommodation data yet (hotels arrive with bookings). The API reports them in `notes` instead of pretending to use them. There is no group-type field.

## Privacy
Every endpoint requires authentication. History, runs, impressions and feedback are scoped to the caller; another user's run or impression id is indistinguishable from a missing one (404). Popularity uses aggregate counts only.
