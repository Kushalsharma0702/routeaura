"""Deterministic catalogue and helpers for recommendation-engine tests (no database)."""

from app.modules.recommendations.engine.config import DEFAULT_CONFIG, ScoringConfig
from app.modules.recommendations.engine.features import build_destination_items, build_profile
from app.modules.recommendations.engine.types import Category, DestinationRecord

HIST = Category("history-heritage", "History & Heritage")
BEACH = Category("beach", "Beach")
ADV = Category("adventure", "Adventure")
NATURE = Category("nature-wildlife", "Nature & Wildlife")
CULT = Category("culture-religion", "Culture & Religion")
FOOD = Category("food-markets", "Food & Markets")
SCENIC = Category("scenic-viewpoint", "Scenic Viewpoint")
CATS = [HIST, BEACH, ADV, NATURE, CULT, FOOD, SCENIC]


def dest(id_, name, cats, cost, days, s, e, climate, attr=None, outdoor=None):
    return DestinationRecord(
        id=id_,
        name=name,
        categories=cats,
        cost_per_day_minor=cost,
        duration_days=days,
        season_start=s,
        season_end=e,
        climate=climate,
        attraction_categories=attr or {},
        outdoor_share=outdoor,
    )


DESTS = [
    dest("jaipur", "Jaipur", [HIST, FOOD, CULT], 320000, 4, 10, 3, "arid", {"history-heritage": 4}, 0.25),
    dest("goa", "Goa", [BEACH, HIST], 350000, 5, 10, 3, "tropical", {"beach": 2, "history-heritage": 2}, 0.75),
    dest(
        "manali",
        "Manali",
        [ADV, SCENIC],
        300000,
        6,
        10,
        6,
        "cold",
        {"adventure": 2, "culture-religion": 1, "food-markets": 1},
        0.75,
    ),
    dest(
        "ladakh",
        "Ladakh",
        [ADV, CULT, SCENIC],
        420000,
        8,
        6,
        9,
        "cold",
        {"scenic-viewpoint": 2, "adventure": 1, "culture-religion": 1},
        0.75,
    ),
    dest("kerala", "Kerala", [NATURE, BEACH], 380000, 7, 9, 3, "tropical", {"nature-wildlife": 2, "beach": 2}, 1.0),
    dest("mystery", "Mystery Island", [], None, None, None, None, None),
]


def items(cfg: ScoringConfig = DEFAULT_CONFIG):
    return build_destination_items(DESTS, cfg)


def profile(cfg: ScoringConfig = DEFAULT_CONFIG, **kw):
    base = dict(
        budget_per_day_minor=None,
        trip_days=None,
        interests=[],
        climate=None,
        season=None,
        travel_month=None,
        style=None,
        categories=CATS,
        history=[],
        config=cfg,
    )
    base.update(kw)
    return build_profile(**base)


def names(scored):
    return [s.item.name for s in scored]
