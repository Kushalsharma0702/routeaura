> **SYNTHETIC experiment: generated data, not real users. See docs/research/RECOMMENDATION_EVALUATION.md.**

Seeds: [42, 43, 44, 45, 46] · users/seed: 300 · items: 120 · K = 10 · MMR λ = 0.7

Values are the mean over seeds ± the standard deviation across seeds (each seed's value is itself a mean over users).

### cold_start_stated
_Cold start: users state (noisy, partial) preferences and have NO interaction history_

| method | precision@10 | recall@10 | ndcg@10 | intra_list_diversity | catalog_coverage | cold_item_recall@10 |
|---|---|---|---|---|---|---|
| random | 0.100 ± 0.007 | 0.083 ± 0.005 | 0.100 ± 0.006 | 0.799 ± 0.011 | 1.000 | 0.085 ± 0.006 |
| popularity | 0.189 ± 0.014 | 0.158 ± 0.012 | 0.198 ± 0.013 | 0.737 ± 0.063 | 0.083 | 0.000 ± 0.000 |
| weighted | 0.380 ± 0.013 | 0.317 ± 0.011 | 0.419 ± 0.012 | 0.592 ± 0.011 | 0.977 | 0.334 ± 0.068 |
| weighted_renormalize | 0.352 ± 0.022 | 0.293 ± 0.018 | 0.360 ± 0.025 | 0.687 ± 0.027 | 1.000 | 0.321 ± 0.056 |
| cosine | 0.356 ± 0.004 | 0.296 ± 0.004 | 0.387 ± 0.005 | 0.522 ± 0.006 | 0.905 | 0.279 ± 0.038 |
| weighted_mmr | 0.339 ± 0.011 | 0.283 ± 0.009 | 0.380 ± 0.007 | 0.694 ± 0.014 | 0.987 | 0.297 ± 0.052 |

### warm_history
_Warm: as above plus 5 simulated saves per user used as interaction history_

| method | precision@10 | recall@10 | ndcg@10 | intra_list_diversity | catalog_coverage | cold_item_recall@10 |
|---|---|---|---|---|---|---|
| random | 0.101 ± 0.006 | 0.084 ± 0.005 | 0.103 ± 0.008 | 0.800 ± 0.010 | 1.000 | 0.087 ± 0.021 |
| popularity | 0.189 ± 0.014 | 0.158 ± 0.012 | 0.198 ± 0.013 | 0.737 ± 0.063 | 0.083 | 0.000 ± 0.000 |
| weighted | 0.454 ± 0.006 | 0.378 ± 0.005 | 0.505 ± 0.006 | 0.556 ± 0.015 | 0.945 | 0.396 ± 0.084 |
| weighted_renormalize | 0.427 ± 0.026 | 0.355 ± 0.021 | 0.412 ± 0.035 | 0.659 ± 0.035 | 1.000 | 0.383 ± 0.040 |
| cosine | 0.471 ± 0.016 | 0.392 ± 0.014 | 0.493 ± 0.016 | 0.393 ± 0.024 | 0.927 | 0.396 ± 0.070 |
| weighted_mmr | 0.398 ± 0.005 | 0.332 ± 0.004 | 0.446 ± 0.003 | 0.672 ± 0.013 | 0.970 | 0.352 ± 0.068 |

### no_signal
_No signal: users state nothing and have no history (content methods must fall back to popularity)_

| method | precision@10 | recall@10 | ndcg@10 | intra_list_diversity | catalog_coverage | cold_item_recall@10 |
|---|---|---|---|---|---|---|
| random | 0.101 ± 0.008 | 0.084 ± 0.007 | 0.102 ± 0.011 | 0.798 ± 0.011 | 1.000 | 0.088 ± 0.023 |
| popularity | 0.189 ± 0.014 | 0.158 ± 0.012 | 0.198 ± 0.013 | 0.737 ± 0.063 | 0.083 | 0.000 ± 0.000 |
| weighted | 0.189 ± 0.014 | 0.158 ± 0.012 | 0.198 ± 0.013 | 0.737 ± 0.063 | 0.083 | 0.000 ± 0.000 |
| weighted_renormalize | 0.189 ± 0.014 | 0.158 ± 0.012 | 0.198 ± 0.013 | 0.737 ± 0.063 | 0.083 | 0.000 ± 0.000 |
| cosine | 0.189 ± 0.014 | 0.158 ± 0.012 | 0.198 ± 0.013 | 0.737 ± 0.063 | 0.083 | 0.000 ± 0.000 |
| weighted_mmr | 0.189 ± 0.014 | 0.158 ± 0.012 | 0.198 ± 0.013 | 0.737 ± 0.063 | 0.083 | 0.000 ± 0.000 |

### Paired differences (per-user, seed 42, 95% bootstrap CI)

| scenario | comparison | mean difference | 95% CI | n users |
|---|---|---|---|---|
| cold_start_stated | weighted - popularity (precision@10) | +0.1870 | [+0.1613, +0.2137] | 300 |
| cold_start_stated | weighted - popularity (ndcg@10) | +0.2128 | [+0.1834, +0.2430] | 300 |
| cold_start_stated | cosine - popularity (ndcg@10) | +0.1854 | [+0.1573, +0.2154] | 300 |
| cold_start_stated | weighted - cosine (ndcg@10) | +0.0273 | [+0.0096, +0.0461] | 300 |
| cold_start_stated | weighted_mmr - weighted (precision@10) | -0.0300 | [-0.0417, -0.0187] | 300 |
| cold_start_stated | weighted_mmr - weighted (intra_list_diversity) | +0.0781 | [+0.0709, +0.0855] | 300 |
| cold_start_stated | weighted - weighted_renormalize (ndcg@10) | +0.0580 | [+0.0431, +0.0737] | 300 |
| warm_history | weighted - popularity (precision@10) | +0.2590 | [+0.2353, +0.2837] | 300 |
| warm_history | weighted - popularity (ndcg@10) | +0.3007 | [+0.2734, +0.3287] | 300 |
| warm_history | cosine - popularity (ndcg@10) | +0.2898 | [+0.2576, +0.3214] | 300 |
| warm_history | weighted - cosine (ndcg@10) | +0.0109 | [-0.0067, +0.0299] | 300 |
| warm_history | weighted_mmr - weighted (precision@10) | -0.0483 | [-0.0603, -0.0363] | 300 |
| warm_history | weighted_mmr - weighted (intra_list_diversity) | +0.0879 | [+0.0808, +0.0947] | 300 |
| warm_history | weighted - weighted_renormalize (ndcg@10) | +0.0929 | [+0.0755, +0.1112] | 300 |
| no_signal | weighted - popularity (precision@10) | +0.0000 | [+0.0000, +0.0000] | 300 |
| no_signal | weighted - popularity (ndcg@10) | +0.0000 | [+0.0000, +0.0000] | 300 |
| no_signal | cosine - popularity (ndcg@10) | +0.0000 | [+0.0000, +0.0000] | 300 |
| no_signal | weighted - cosine (ndcg@10) | +0.0000 | [+0.0000, +0.0000] | 300 |
| no_signal | weighted_mmr - weighted (precision@10) | +0.0000 | [+0.0000, +0.0000] | 300 |
| no_signal | weighted_mmr - weighted (intra_list_diversity) | +0.0000 | [+0.0000, +0.0000] | 300 |
| no_signal | weighted - weighted_renormalize (ndcg@10) | +0.0000 | [+0.0000, +0.0000] | 300 |

### Run parameters

```json
{
  "catalogue": {
    "n_cold_items_in_training": 24,
    "n_items": 120,
    "n_relevant_per_user": 12,
    "observed_missing_rates": {
      "categories": 0.05,
      "climate": 0.10833333333333334,
      "cost_per_day_minor": 0.15833333333333333,
      "duration_days": 0.10833333333333334,
      "season_start": 0.14166666666666666
    }
  },
  "dataset": {
    "catalogue_missing_rate": 0.15,
    "category_missing_rate": 0.05,
    "interest_error_rate": 0.15,
    "n_items": 120,
    "n_test_users": 300,
    "n_train_users": 400,
    "new_item_fraction": 0.2,
    "relevant_fraction": 0.1,
    "seed": 42,
    "softmax_temperature": 0.1,
    "stated_rate": 0.75,
    "train_interactions_per_user": 15,
    "warm_interactions_per_user": 5
  },
  "scoring_config": {
    "attraction_blend": 0.5,
    "attraction_budget_full_share": 0.25,
    "avoid_beta": 0.3,
    "budget_incompatible_multiplier": 0.6,
    "budget_overrun_tolerance": 0.5,
    "climate_any_score": 0.75,
    "duration_slack_days": 1,
    "history_alpha": 0.7,
    "missing_policy": "lower_bound",
    "mmr_lambda": 0.7,
    "model_version": "content-v1",
    "weights": {
      "budget": 0.2,
      "climate": 0.1,
      "duration": 0.1,
      "interest": 0.35,
      "season": 0.15,
      "style": 0.1
    }
  }
}
```
