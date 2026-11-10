"""Pure interaction logic: derive current item state from an append-only event log and turn it into
time-decayed, signed evidence for the profile builder. No database access."""

from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime

ItemKey = tuple[str, str]  # (kind, id)

HALF_LIFE_DAYS = 90.0
VIEW_W, CLICK_W = 0.2, 0.5
SAVE_W, LIKE_W, DISLIKE_W, DISMISS_W, FEEDBACK_W = 1.0, 1.0, -1.0, -0.5, 0.7
MAX_REPEATS = 3  # repeated views/clicks stop adding evidence after this many
WEIGHT_CAP = 2.0


@dataclass
class ItemState:
    saved: bool = False
    reaction: str | None = None  # "like" | "dislike" | None
    dismissed: bool = False
    views: int = 0
    clicks: int = 0
    last_at: datetime | None = None

    @property
    def liked(self) -> bool:
        return self.reaction == "like"

    @property
    def disliked(self) -> bool:
        return self.reaction == "dislike"


def apply_event(state: ItemState, event_type: str, at: datetime | None = None) -> ItemState:
    if event_type == "view":
        state.views += 1
    elif event_type == "click":
        state.clicks += 1
    elif event_type == "save":
        state.saved = True
    elif event_type == "unsave":
        state.saved = False
    elif event_type in ("like", "dislike"):
        state.reaction = event_type
    elif event_type == "reaction_clear":
        state.reaction = None
    elif event_type == "dismiss":
        state.dismissed = True
    elif event_type == "restore":
        state.dismissed = False
    else:
        raise ValueError(f"unknown interaction type {event_type!r}")
    if at is not None and (state.last_at is None or at > state.last_at):
        state.last_at = at
    return state


def changes_state(state: ItemState, event_type: str) -> bool:
    """False when the event would be a no-op (so state events stay idempotent)."""
    return {
        "save": not state.saved,
        "unsave": state.saved,
        "like": state.reaction != "like",
        "dislike": state.reaction != "dislike",
        "reaction_clear": state.reaction is not None,
        "dismiss": not state.dismissed,
        "restore": state.dismissed,
    }.get(event_type, True)  # view / click always count


def fold(events: Iterable[tuple[ItemKey, str, datetime]]) -> dict[ItemKey, ItemState]:
    """Fold events (must be in chronological order) into current per-item state."""
    states: dict[ItemKey, ItemState] = {}
    for key, event_type, at in events:
        apply_event(states.setdefault(key, ItemState()), event_type, at)
    return states


def history_weight(state: ItemState, feedback: list[str], now: datetime) -> float:
    """Signed evidence about the user's taste from one item, decayed by the age of its latest signal."""
    w = VIEW_W * min(state.views, MAX_REPEATS) + CLICK_W * min(state.clicks, MAX_REPEATS)
    w += SAVE_W if state.saved else 0.0
    w += LIKE_W if state.liked else DISLIKE_W if state.disliked else 0.0
    w += DISMISS_W if state.dismissed else 0.0
    w += sum(FEEDBACK_W if f == "relevant" else -FEEDBACK_W for f in feedback)
    w = max(-WEIGHT_CAP, min(WEIGHT_CAP, w))
    if state.last_at is None:
        return w
    age_days = max(0.0, (now - state.last_at).total_seconds() / 86400.0)
    return w * math.exp(-math.log(2) * age_days / HALF_LIFE_DAYS)


def popularity_weight(counts: dict[str, int]) -> float:
    """Aggregate, non-personal popularity of an item from event counts across all users (never below 0)."""
    w = (
        counts.get("view", 0) * 1.0
        + counts.get("click", 0) * 2.0
        + counts.get("save", 0) * 3.0
        + counts.get("like", 0) * 3.0
        - counts.get("dislike", 0) * 2.0
        - counts.get("dismiss", 0) * 1.0
    )
    return max(0.0, w)
