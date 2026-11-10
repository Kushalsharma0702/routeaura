from datetime import UTC, datetime, timedelta

import pytest

from app.modules.recommendations.interactions import (
    ItemState,
    apply_event,
    changes_state,
    fold,
    history_weight,
    popularity_weight,
)

NOW = datetime(2026, 6, 1, tzinfo=UTC)
K = ("destination", "d1")


def ev(t, minutes=0):
    return (K, t, NOW + timedelta(minutes=minutes))


def test_fold_derives_current_state_from_the_latest_events():
    s = fold([ev("save", 0), ev("like", 1), ev("dismiss", 2), ev("unsave", 3), ev("dislike", 4), ev("restore", 5)])[K]
    assert (s.saved, s.reaction, s.dismissed) == (False, "dislike", False)
    s2 = fold([ev("like", 0), ev("reaction_clear", 1), ev("save", 2)])[K]
    assert (s2.saved, s2.reaction) == (True, None)
    assert s2.last_at == NOW + timedelta(minutes=2)


def test_views_and_clicks_are_counted_not_toggled():
    s = fold([ev("view"), ev("view", 1), ev("click", 2)])[K]
    assert (s.views, s.clicks, s.saved) == (2, 1, False)


def test_unknown_event_type_is_rejected():
    with pytest.raises(ValueError):
        apply_event(ItemState(), "teleport")


def test_changes_state_makes_state_events_idempotent():
    st = ItemState()
    assert changes_state(st, "save") and not changes_state(st, "unsave")
    assert not changes_state(st, "reaction_clear") and not changes_state(st, "restore")
    apply_event(st, "save")
    assert not changes_state(st, "save") and changes_state(st, "unsave")
    apply_event(st, "like")
    assert not changes_state(st, "like") and changes_state(st, "dislike") and changes_state(st, "reaction_clear")
    assert changes_state(st, "view") and changes_state(st, "click")  # always count


def test_history_weight_signs_caps_and_decay():
    fresh = ItemState(saved=True, last_at=NOW)
    assert history_weight(fresh, [], NOW) == pytest.approx(1.0)
    assert history_weight(ItemState(reaction="dislike", last_at=NOW), [], NOW) == pytest.approx(-1.0)
    assert history_weight(ItemState(dismissed=True, last_at=NOW), [], NOW) == pytest.approx(-0.5)
    # repeated views stop adding evidence after 3
    assert history_weight(ItemState(views=3, last_at=NOW), [], NOW) == history_weight(
        ItemState(views=50, last_at=NOW), [], NOW
    )
    # explicit feedback is signed
    assert (
        history_weight(ItemState(last_at=NOW), ["relevant"], NOW)
        > 0
        > history_weight(ItemState(last_at=NOW), ["not_relevant"], NOW)
    )
    # total evidence is capped at +-2
    assert history_weight(
        ItemState(saved=True, reaction="like", views=3, clicks=3, last_at=NOW), ["relevant"] * 5, NOW
    ) == pytest.approx(2.0)
    # half-life of 90 days
    old = ItemState(saved=True, last_at=NOW - timedelta(days=90))
    assert history_weight(old, [], NOW) == pytest.approx(0.5)
    # saved then unsaved = no evidence
    assert history_weight(fold([ev("save"), ev("unsave", 1)])[K], [], NOW) == 0.0


def test_popularity_weight_is_never_negative():
    assert popularity_weight({"view": 2, "save": 1}) == 5.0
    assert popularity_weight({"dislike": 10}) == 0.0
    assert popularity_weight({}) == 0.0
