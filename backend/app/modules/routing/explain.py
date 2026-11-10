"""Human-readable comparison of two day plans. Pure functions: statements are derived from the data only."""

from __future__ import annotations


def pct(before: float, after: float) -> str:
    if before == 0:
        return "n/a"
    return f"{(after - before) / before * 100:+.0f}%"


def explain(
    before_days: list[list[str]],
    after_days: list[list[str]],
    names: dict[str, str],
    before: dict,
    after: dict,
    dropped: list[tuple[str, str]],
) -> list[str]:
    out: list[str] = []
    bd, ad = before["distance_m"] / 1000, after["distance_m"] / 1000
    bt, at = before["travel_min"], after["travel_min"]
    if before_days == after_days and not dropped:
        out.append("The current order is already the best found for the chosen weights; nothing was changed.")
    else:
        out.append(f"Travel distance {bd:.1f} km → {ad:.1f} km ({pct(bd, ad)}).")
        out.append(f"Estimated travel time {bt} min → {at} min ({pct(bt, at)}).")
    old_day = {i: d + 1 for d, ids in enumerate(before_days) for i in ids}
    new_day = {i: d + 1 for d, ids in enumerate(after_days) for i in ids}
    for i, nd in new_day.items():
        if i in old_day and old_day[i] != nd:
            out.append(f"Moved {names[i]} from day {old_day[i]} to day {nd}.")
    for d, ids in enumerate(after_days):
        same_day_before = [i for i in before_days[d] if i in ids] if d < len(before_days) else []
        same_day_after = [i for i in ids if i in same_day_before]
        if same_day_before and same_day_before != same_day_after:
            out.append(
                f"Day {d + 1} order changed: {' → '.join(names[i] for i in same_day_before)} ⇒ {' → '.join(names[i] for i in same_day_after)}."
            )
    for i, reason in dropped:
        out.append(f"Removed {names.get(i, i)}: {reason}.")
    bv, av = len(before["violations"]), len(after["violations"])
    if bv != av:
        out.append(f"Constraint violations {bv} → {av}.")
    elif av:
        out.append(f"{av} constraint violation(s) remain; see the list below.")
    bb, ab = before["budget"].get("deviation_pct"), after["budget"].get("deviation_pct")
    if bb is not None and ab is not None and bb != ab:
        out.append(f"Estimated budget deviation {bb:+.1f}% → {ab:+.1f}%.")
    return out
