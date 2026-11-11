"""Draw the README charts from the committed synthetic-experiment results (docs/research/results/*.json).

Nothing here is typed in by hand: every bar is read from the JSON files.
Run:  cd backend && uv run --with matplotlib python ../docs/images/make_charts.py
"""
import json
import statistics as st
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
RES = HERE.parent / "research" / "results"
NOTE = "SYNTHETIC experiment (seeded generated data, 5 seeds). Not real users."
C = {"blue": "#2563eb", "green": "#16a34a", "amber": "#d97706", "violet": "#7c3aed", "grey": "#94a3b8", "red": "#dc2626"}
plt.rcParams.update({"font.family": "DejaVu Sans", "axes.spines.top": False, "axes.spines.right": False, "font.size": 10})


def save(fig, name):
    fig.text(0.5, -0.03, NOTE, fontsize=7.5, color="#64748b", ha="center", va="top")
    fig.savefig(HERE / name, dpi=160, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print("wrote", name)


# ---------------------------------------------------------------- recommendations
rec = json.load(open(RES / "results.json"))["aggregate_across_seeds"]
methods = ["random", "popularity", "cosine", "weighted", "weighted_mmr"]
labels = ["Random", "Popularity", "Cosine only", "Weighted\n(RouteAura)", "Weighted\n+ MMR"]
cols = [C["grey"], C["grey"], C["amber"], C["blue"], C["violet"]]
fig, axes = plt.subplots(1, 2, figsize=(10, 3.8), sharey=True)
for ax, sc, title in zip(axes, ["cold_start_stated", "warm_history"], ["Cold start (stated preferences only)", "Warm (preferences + 5 saves)"]):
    vals = [rec[sc][m]["ndcg@10"]["mean"] for m in methods]
    err = [rec[sc][m]["ndcg@10"]["sd_across_seeds"] or 0 for m in methods]
    ax.bar(labels, vals, yerr=err, color=cols, capsize=3)
    for i, v in enumerate(vals):
        ax.text(i, v + err[i] + 0.012, f"{v:.2f}", ha="center", fontsize=8.5)
    ax.set_ylim(0, 0.6)
    ax.set_title(title, fontsize=10.5)
    ax.tick_params(axis="x", labelsize=8)
axes[0].set_ylabel("NDCG@10 (higher is better)")
fig.suptitle("Recommendation quality vs baselines", fontweight="bold")
save(fig, "chart_recommendation_ndcg.png")

fig, ax = plt.subplots(figsize=(6.2, 4.2))
for m, lab, c in zip(methods, ["Random", "Popularity", "Cosine only", "Weighted", "Weighted + MMR"], cols):
    x = rec["cold_start_stated"][m]["intra_list_diversity"]["mean"]
    y = rec["cold_start_stated"][m]["precision@10"]["mean"]
    ax.scatter(x, y, s=90, color=c, zorder=3)
    ax.annotate(lab, (x, y), textcoords="offset points", xytext=(7, 5), fontsize=8.5)
ax.set_xlabel("Diversity of the list (higher = more varied)")
ax.set_ylabel("Precision@10 (higher = more relevant)")
ax.set_title("Relevance vs variety (cold start)", fontweight="bold")
ax.grid(alpha=0.25)
save(fig, "chart_relevance_vs_diversity.png")

# ---------------------------------------------------------------- itineraries
it = json.load(open(RES / "itinerary_results.json"))["aggregate_across_seeds"]
im = ["simple_order", "nearest_neighbour", "validated_planner"]
il = ["Simple order", "Nearest neighbour", "Validated planner\n(RouteAura)"]
fig, axes = plt.subplots(1, 2, figsize=(9.5, 3.6))
v = [it[m]["has_violation"]["mean"] * 100 for m in im]
e = [(it[m]["has_violation"]["sd_across_seeds"] or 0) * 100 for m in im]
axes[0].bar(il, v, yerr=e, color=[C["grey"], C["amber"], C["blue"]], capsize=3)
for i, x in enumerate(v):
    axes[0].text(i, x + e[i] + 2, f"{x:.0f}%", ha="center")
axes[0].set_ylim(0, 90)
axes[0].set_ylabel("% of trips with a rule violation (lower is better)")
axes[0].set_title("Constraint violations", fontsize=10.5)
n = [it[m]["n_activities"]["mean"] for m in im]
axes[1].bar(il, n, color=[C["grey"], C["amber"], C["blue"]])
for i, x in enumerate(n):
    axes[1].text(i, x + 0.1, f"{x:.1f}", ha="center")
axes[1].set_ylabel("Activities per trip")
axes[1].set_title("Plan size", fontsize=10.5)
for a in axes:
    a.tick_params(axis="x", labelsize=8)
fig.suptitle("Itinerary planner: validity (judged by the planner's own rule set)", fontweight="bold")
save(fig, "chart_itinerary_violations.png")

# ---------------------------------------------------------------- routing
runs = json.load(open(RES / "routing_results.json"))["runs"]
rm = ["nearest_neighbour", "ortools_locked", "ortools_free"]
rl = ["Nearest\nneighbour", "OR-Tools\n(locked stops kept)", "OR-Tools\n(free)"]
fig, ax = plt.subplots(figsize=(6.6, 3.9))
vals = [st.mean(r["route_optimization_paired"][m]["distance_reduction_pct"]["mean"] for r in runs) for m in rm]
sds = [st.stdev(r["route_optimization_paired"][m]["distance_reduction_pct"]["mean"] for r in runs) for m in rm]
ax.bar(rl, vals, yerr=sds, color=[C["amber"], C["blue"], C["violet"]], capsize=3)
for i, x in enumerate(vals):
    ax.text(i, x + sds[i] + 1, f"{x:.0f}%", ha="center")
ax.set_ylim(0, 45)
ax.set_ylabel("Distance saved vs original plan (%)")
ax.set_title("Route optimization", fontweight="bold")
save(fig, "chart_route_savings.png")

sp = [r["shortest_paths"] for r in runs]
keys = list(sp[0].keys())
dk = next(k for k in keys if "expanded" in k and "dijkstra" in k)
ak = next(k for k in keys if "expanded" in k and "astar" in k)
fig, ax = plt.subplots(figsize=(4.6, 3.6))
d, a = st.mean(s[dk] for s in sp), st.mean(s[ak] for s in sp)
ax.bar(["Dijkstra", "A*"], [d, a], color=[C["grey"], C["green"]])
for i, x in enumerate([d, a]):
    ax.text(i, x + 0.8, f"{x:.0f}", ha="center")
ax.set_ylabel("Nodes explored per query")
ax.set_title("Same shortest path,\nhalf the search", fontweight="bold", fontsize=10.5)
save(fig, "chart_astar_vs_dijkstra.png")

ctx = [r["context_adaptation"] for r in runs]
top = st.mean(c["proposals_with_violations_if_top_ranked_alternative_used"] for c in ctx)
aware = st.mean(c["proposals_with_violations_feasibility_aware_choice"] for c in ctx)
tot = st.mean(c["proposals_built"] for c in ctx)
fig, ax = plt.subplots(figsize=(5.4, 3.6))
ax.bar(["Take top-ranked\nalternative", "Feasibility-aware\npick (RouteAura)"], [top / tot * 100, aware / tot * 100], color=[C["grey"], C["blue"]])
for i, x in enumerate([top / tot * 100, aware / tot * 100]):
    ax.text(i, x + 1, f"{x:.0f}%", ha="center")
ax.set_ylabel("% of proposals still breaking a rule")
ax.set_ylim(0, 72)
ax.set_title("Weather adaptation: choosing the replacement", fontweight="bold", fontsize=10.5)
save(fig, "chart_context_adaptation.png")
