"""Orchestrates the recommendation engine against PostgreSQL: loads published catalogue records and the
user's preferences/history, runs the engine, persists the run, impressions and feedback."""

from __future__ import annotations

import time
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.core.errors import AppError, not_found
from app.models.catalog import Attraction, AttractionCategory, Destination
from app.models.recommendations import RecommendationItem, RecommendationRun
from app.models.user import User, UserPreference
from app.modules.recommendations.engine.config import COSINE_CONFIG, DEFAULT_CONFIG, ScoringConfig
from app.modules.recommendations.engine.features import build_attraction_items, build_destination_items, build_profile
from app.modules.recommendations.engine.ranking import mmr_rerank, rank_content, rank_popularity
from app.modules.recommendations.engine.scoring import has_usable_signal
from app.modules.recommendations.engine.types import (
    AttractionRecord,
    Category,
    DestinationRecord,
    HistoryItem,
    Item,
    ScoredItem,
)
from app.modules.recommendations.interactions import (
    ItemState,
    changes_state,
    fold,
    history_weight,
    popularity_weight,
)
from app.repositories.recommendations import (
    FeedbackRepository,
    InteractionRepository,
    ItemKey,
    RunRepository,
    item_key,
)
from app.schemas.catalog import AttractionOut, DestinationOut
from app.schemas.recommendations import (
    ComponentOut,
    FeedbackIn,
    FeedbackOut,
    InteractionIn,
    InteractionOut,
    ItemStateOut,
    RecommendationItemOut,
    RecommendationRequest,
    RecommendationResponse,
    RunDetail,
    RunItemOut,
    RunSummary,
    SavedItemOut,
)

HISTORY_DAYS = 365
UNUSED_PREFS = {"group_size": "group size", "accommodation_preference": "accommodation preference"}


def _state_out(s: ItemState) -> ItemStateOut:
    return ItemStateOut(saved=s.saved, liked=s.liked, disliked=s.disliked, dismissed=s.dismissed)


class RecommendationService:
    def __init__(self, db: Session):
        self.db = db
        self.interactions = InteractionRepository(db)
        self.runs = RunRepository(db)
        self.feedback = FeedbackRepository(db)

    # ------------------------------------------------------------------ catalogue loading
    def _categories(self) -> list[AttractionCategory]:
        return list(self.db.scalars(select(AttractionCategory).order_by(AttractionCategory.name)))

    def _published_destinations(self) -> list[Destination]:
        return list(
            self.db.scalars(
                select(Destination)
                .where(Destination.is_published.is_(True), Destination.deleted_at.is_(None))
                .order_by(Destination.name)
            )
        )

    def _destination_records(self, dests: list[Destination], cats: dict[uuid.UUID, AttractionCategory]):
        rows = self.db.execute(
            select(
                Attraction.destination_id,
                Attraction.category_id,
                func.count(),
                func.sum(case((Attraction.is_outdoor.is_(True), 1), else_=0)),
            )
            .where(Attraction.is_published.is_(True), Attraction.deleted_at.is_(None))
            .group_by(Attraction.destination_id, Attraction.category_id)
        ).all()
        hist: dict[uuid.UUID, dict[str, int]] = {}
        totals: dict[uuid.UUID, list[int]] = {}
        for dest_id, cat_id, n, outdoor in rows:
            hist.setdefault(dest_id, {})[cats[cat_id].slug] = n
            t = totals.setdefault(dest_id, [0, 0])
            t[0] += n
            t[1] += int(outdoor or 0)
        records = []
        for d in dests:
            tot = totals.get(d.id)
            records.append(
                DestinationRecord(
                    id=str(d.id),
                    name=d.name,
                    country=d.country,
                    categories=[Category(c.slug, c.name) for c in d.categories],
                    cost_per_day_minor=d.estimated_cost_per_day_minor,
                    duration_days=d.recommended_duration_days,
                    season_start=d.best_season_start_month,
                    season_end=d.best_season_end_month,
                    climate=d.climate,
                    attraction_categories=hist.get(d.id, {}),
                    outdoor_share=(tot[1] / tot[0]) if tot and tot[0] else None,
                )
            )
        return records, {d.id: sum(hist.get(d.id, {}).values()) for d in dests}

    def _published_attractions(self, dests_by_id: dict[uuid.UUID, Destination]) -> list[Attraction]:
        return list(
            self.db.scalars(
                select(Attraction)
                .where(
                    Attraction.is_published.is_(True),
                    Attraction.deleted_at.is_(None),
                    Attraction.destination_id.in_(list(dests_by_id)) if dests_by_id else Attraction.id.is_(None),
                )
                .order_by(Attraction.name)
            )
        )

    # ------------------------------------------------------------------ preferences & history
    def _effective_preferences(self, user: User, req: RecommendationRequest) -> tuple[dict, dict[str, str], list[str]]:
        saved = self.db.get(UserPreference, user.id)
        base = {
            "budget_per_day_minor": saved.budget_per_day_minor if saved else None,
            "trip_duration_days": saved.trip_duration_days if saved else None,
            "interests": list(saved.interests) if saved and saved.interests else [],
            "preferred_climate": saved.preferred_climate if saved else None,
            "preferred_season": saved.preferred_season if saved else None,
            "travel_month": None,
            "travel_style": saved.travel_style if saved else None,
        }
        source = {k: "saved" for k in base}
        for field in req.overrides.model_fields_set:
            value = getattr(req.overrides, field)
            base[field] = [] if field == "interests" and value is None else value
            source[field] = "request"
        notes = [
            f"Your {label} is saved but not used for scoring yet (no matching catalogue data)."
            for attr, label in UNUSED_PREFS.items()
            if saved and getattr(saved, attr)
        ]
        return base, source, notes

    def _history(
        self, user: User, item_lookup: dict[ItemKey, Item]
    ) -> tuple[list[HistoryItem], dict[ItemKey, ItemState]]:
        now = datetime.now(UTC)
        events = self.interactions.events(user.id, since=now - timedelta(days=HISTORY_DAYS))
        states = fold((item_key(e), e.interaction_type, e.created_at) for e in events)
        feedback = self.feedback.by_target(user.id)
        keys = set(states) | set(feedback)
        # attraction -> category for attractions not already loaded as items
        missing_attr = [uuid.UUID(k[1]) for k in keys if k[0] == "attraction" and k not in item_lookup]
        if missing_attr:
            for a in self.db.scalars(
                select(Attraction).where(Attraction.id.in_(missing_attr), Attraction.deleted_at.is_(None))
            ):
                item_lookup[("attraction", str(a.id))] = Item(
                    id=str(a.id),
                    kind="attraction",
                    name=a.name,
                    category_vec={a.category.slug: 1.0},
                    category_names={},
                    cost_minor=None,
                    cost_norm=None,
                    duration_days=None,
                    season_months=None,
                    climate=None,
                    styles={},
                    vector={},
                )
        out: list[HistoryItem] = []
        for key in keys:
            item = item_lookup.get(key)
            if item is None or not item.category_vec:
                continue  # unpublished/deleted items carry no usable signal
            w = history_weight(states.get(key, ItemState()), feedback.get(key, []), now)
            if abs(w) > 1e-9:
                out.append(HistoryItem(weight=w, category_vec=item.category_vec))
        return out, states

    def _popularity(self, kind: str) -> dict[str, float]:
        return {item_id: popularity_weight(c) for item_id, c in self.interactions.popularity_counts(kind).items()}

    # ------------------------------------------------------------------ recommend
    def recommend(self, user: User, kind: str, req: RecommendationRequest) -> RecommendationResponse:
        started = time.perf_counter()
        f = req.filters
        if kind == "destination" and (f.destination_id or f.outdoor is not None):
            raise AppError(
                422, "validation_error", "destination_id and outdoor filters apply to attraction recommendations only"
            )
        if kind == "attraction" and (f.country or f.climate or f.max_cost_minor is not None):
            raise AppError(
                422,
                "validation_error",
                "country, climate and max_cost_minor filters apply to destination recommendations only",
            )

        cats = self._categories()
        cat_by_id = {c.id: c for c in cats}
        vocab = [Category(c.slug, c.name) for c in cats]
        dests = self._published_destinations()
        dests_by_id = {d.id: d for d in dests}
        dest_records, attraction_counts = self._destination_records(dests, cat_by_id)
        cfg_base = COSINE_CONFIG if req.strategy == "cosine" else DEFAULT_CONFIG
        cfg = cfg_base.with_priorities(req.priorities) if req.priorities else cfg_base
        dest_items, _ = build_destination_items(dest_records, cfg, vocab)
        lookup: dict[ItemKey, Item] = {("destination", i.id): i for i in dest_items}

        orm_by_id: dict[str, Destination | Attraction] = {str(d.id): d for d in dests}
        if kind == "attraction":
            attrs = self._published_attractions(dests_by_id)
            arecs = [
                AttractionRecord(
                    id=str(a.id),
                    name=a.name,
                    destination_id=str(a.destination_id),
                    category=Category(a.category.slug, a.category.name),
                    cost_minor=a.estimated_cost_minor,
                    minutes=a.typical_duration_minutes,
                    is_outdoor=a.is_outdoor,
                    climate=dests_by_id[a.destination_id].climate,
                    season_start=dests_by_id[a.destination_id].best_season_start_month,
                    season_end=dests_by_id[a.destination_id].best_season_end_month,
                )
                for a in attrs
            ]
            candidates, _ = build_attraction_items(arecs)
            orm_by_id = {str(a.id): a for a in attrs}
            for it in candidates:
                lookup[("attraction", it.id)] = it
        else:
            candidates = dest_items

        history, states = self._history(user, lookup)
        prefs, pref_source, notes = self._effective_preferences(user, req)
        profile = build_profile(
            budget_per_day_minor=prefs["budget_per_day_minor"],
            trip_days=prefs["trip_duration_days"],
            interests=prefs["interests"],
            climate=prefs["preferred_climate"],
            season=prefs["preferred_season"],
            travel_month=prefs["travel_month"],
            style=prefs["travel_style"],
            categories=vocab,
            history=history,
            config=cfg,
        )
        notes = notes + profile.notes

        # ---- candidate filtering
        def keep(it: Item) -> bool:
            st = states.get((kind, it.id))
            if st and (st.dismissed or st.disliked) and not req.include_dismissed:
                return False
            if f.category and f.category not in it.category_vec:
                return False
            if kind == "destination":
                d = orm_by_id[it.id]
                if f.country and d.country.lower() != f.country.lower():  # type: ignore[union-attr]
                    return False
                if f.climate and it.climate != f.climate:
                    return False
                if f.max_cost_minor is not None and (it.cost_minor is None or it.cost_minor > f.max_cost_minor):
                    return False
            else:
                if f.destination_id and it.meta["destination_id"] != str(f.destination_id):
                    return False
                if f.outdoor is not None and bool(it.meta["is_outdoor"]) != f.outdoor:
                    return False
            return True

        pool = [it for it in candidates if keep(it)]

        # ---- strategy
        strategy = req.strategy
        has_signal = has_usable_signal(profile, cfg, kind)
        if strategy == "popularity":
            ranked = rank_popularity(pool, self._popularity(kind))
        elif not has_signal:
            strategy = "popularity_fallback"
            notes.append(
                "No usable preferences or history yet, so popular places are shown instead. "
                "Set your preferences for personalised results."
            )
            ranked = rank_popularity(pool, self._popularity(kind))
        else:
            ranked = rank_content(profile, pool, cfg)

        lam = req.diversity_lambda if req.diversity_lambda is not None else cfg.mmr_lambda
        diversified = req.diversify and strategy in ("weighted", "cosine") and len(ranked) > 1
        k = req.page * req.page_size
        ordered = mmr_rerank(list(ranked), k, lam) if diversified else ranked[:k]
        if not diversified:
            for i, s in enumerate(ordered, 1):
                s.rank = i
        page_slice = ordered[(req.page - 1) * req.page_size : req.page * req.page_size]

        # ---- persist the run + impressions
        eff_weights = {k2: round(v, 4) for k2, v in cfg.weights.items()}
        snapshot = {
            **prefs,
            "sources": pref_source,
            "matched_interests": profile.matched_interests,
            "unmatched_interests": profile.unmatched_interests,
            "used_history": profile.has_history,
        }
        run = RecommendationRun(
            user_id=user.id,
            kind=kind,
            strategy=strategy,
            model_version=cfg.model_version,
            config=cfg.to_dict(),
            preferences=snapshot,
            filters=f.model_dump(mode="json", exclude_none=True),
            priorities=dict(req.priorities),
            total_candidates=len(ranked),
            returned_count=len(page_slice),
            page=req.page,
            page_size=req.page_size,
            diversified=diversified,
            diversity_lambda=lam if diversified else None,
            latency_ms=round((time.perf_counter() - started) * 1000, 2),
        )
        impressions = [self._impression(s, kind) for s in page_slice]
        self.runs.add_run(run, impressions)
        self.db.commit()

        items_out = [
            self._item_out(imp, s, kind, orm_by_id, attraction_counts, states)
            for imp, s in zip(impressions, page_slice, strict=True)
        ]
        return RecommendationResponse(
            run_id=run.id,
            kind=kind,
            strategy=strategy,
            model_version=cfg.model_version,
            diversified=diversified,
            diversity_lambda=run.diversity_lambda,
            total_candidates=len(ranked),
            page=req.page,
            page_size=req.page_size,
            items=items_out,
            applied_preferences=snapshot,
            effective_weights=eff_weights,
            notes=notes,
        )

    def score_attractions(
        self,
        user: User,
        destination: Destination,
        attractions: list[Attraction],
        *,
        interests: list[str] | None = None,
        style: str | None = None,
        budget_per_day_minor: int | None = None,
    ) -> tuple[dict[str, ScoredItem], list[str]]:
        """Score the given (already published) attractions of one destination for this user with the same
        engine the recommendation API uses. Returns ({attraction_id: ScoredItem}, notes). Nothing is persisted."""
        cats = self._categories()
        cat_by_id = {c.id: c for c in cats}
        vocab = [Category(c.slug, c.name) for c in cats]
        dests = self._published_destinations()
        dest_records, _ = self._destination_records(dests, cat_by_id)
        cfg = DEFAULT_CONFIG
        dest_items, _ = build_destination_items(dest_records, cfg, vocab)
        arecs = [
            AttractionRecord(
                id=str(a.id),
                name=a.name,
                destination_id=str(a.destination_id),
                category=Category(a.category.slug, a.category.name),
                cost_minor=a.estimated_cost_minor,
                minutes=a.typical_duration_minutes,
                is_outdoor=a.is_outdoor,
                climate=destination.climate,
                season_start=destination.best_season_start_month,
                season_end=destination.best_season_end_month,
            )
            for a in attractions
        ]
        items, _ = build_attraction_items(arecs)
        lookup: dict[ItemKey, Item] = {("destination", i.id): i for i in dest_items}
        lookup.update({("attraction", i.id): i for i in items})
        history, _ = self._history(user, lookup)
        prefs, _, notes = self._effective_preferences(user, RecommendationRequest())
        profile = build_profile(
            budget_per_day_minor=budget_per_day_minor
            if budget_per_day_minor is not None
            else prefs["budget_per_day_minor"],
            trip_days=None,
            interests=interests if interests is not None else prefs["interests"],
            climate=prefs["preferred_climate"],
            season=prefs["preferred_season"],
            travel_month=None,
            style=style or prefs["travel_style"],
            categories=vocab,
            history=history,
            config=cfg,
        )
        notes = notes + profile.notes
        if has_usable_signal(profile, cfg, "attraction"):
            ranked = rank_content(profile, items, cfg)
        else:
            notes.append("No preferences were available, so attractions were ordered by popularity.")
            ranked = rank_popularity(items, self._popularity("attraction"))
        return {s.item.id: s for s in ranked}, notes

    def _impression(self, s: ScoredItem, kind: str) -> RecommendationItem:
        explanation = {
            "components": [c.to_dict() for c in s.components],
            "reasons": s.reasons,
            "cautions": s.cautions,
            "missing": s.missing,
            "multiplier": s.multiplier,
        }
        target = (
            {"destination_id": uuid.UUID(s.item.id)}
            if kind == "destination"
            else {"attraction_id": uuid.UUID(s.item.id)}
        )
        return RecommendationItem(
            rank=s.rank,
            original_rank=s.original_rank,
            score=round(s.score, 6),
            confidence=round(s.confidence, 6),
            explanation=explanation,
            **target,
        )

    def _item_out(
        self,
        imp: RecommendationItem,
        s: ScoredItem,
        kind: str,
        orm_by_id: dict,
        attraction_counts: dict,
        states: dict[ItemKey, ItemState],
    ) -> RecommendationItemOut:
        orm = orm_by_id[s.item.id]
        st = states.get((kind, s.item.id), ItemState())
        dest_out = attr_out = None
        if kind == "destination":
            dest_out = DestinationOut.model_validate(orm)
            dest_out.attraction_count = attraction_counts.get(orm.id, 0)
        else:
            attr_out = AttractionOut.model_validate(orm)
        return RecommendationItemOut(
            recommendation_item_id=imp.id,
            kind=kind,
            rank=imp.rank,
            original_rank=imp.original_rank,
            score=imp.score,
            confidence=imp.confidence,
            destination=dest_out,
            attraction=attr_out,
            components=[ComponentOut(**c.to_dict()) for c in s.components],
            reasons=s.reasons,
            cautions=s.cautions,
            missing=s.missing,
            saved=st.saved,
            liked=st.liked,
            disliked=st.disliked,
        )

    # ------------------------------------------------------------------ interactions
    def _target(self, kind: str, item_id: uuid.UUID) -> Destination | Attraction:
        if kind == "destination":
            d = self.db.get(Destination, item_id)
            if d is None or d.deleted_at is not None or not d.is_published:
                raise not_found("Destination")
            return d
        a = self.db.get(Attraction, item_id)
        if (
            a is None
            or a.deleted_at is not None
            or not a.is_published
            or not a.destination.is_published
            or a.destination.deleted_at is not None
        ):
            raise not_found("Attraction")
        return a

    def _state(self, user: User, kind: str, item_id: uuid.UUID) -> ItemState:
        events = self.interactions.events(user.id, kind_item=(kind, str(item_id)))
        return fold((item_key(e), e.interaction_type, e.created_at) for e in events).get(
            (kind, str(item_id)), ItemState()
        )

    def item_state(self, user: User, kind: str, item_id: uuid.UUID) -> ItemStateOut:
        self._target(kind, item_id)
        return _state_out(self._state(user, kind, item_id))

    def record_interaction(self, user: User, data: InteractionIn) -> InteractionOut:
        self._target(data.item_type, data.item_id)
        if data.recommendation_item_id:
            imp = self.runs.get_item(user.id, data.recommendation_item_id)
            if imp is None:
                raise not_found("Recommendation")  # not yours or nonexistent: indistinguishable
            target = imp.destination_id if data.item_type == "destination" else imp.attraction_id
            if target != data.item_id:
                raise not_found("Recommendation")
        state = self._state(user, data.item_type, data.item_id)
        t = data.interaction_type
        if not changes_state(state, t) or (
            t == "view" and self.interactions.recent_view_exists(user.id, data.item_type, data.item_id)
        ):
            return InteractionOut(recorded=False, state=_state_out(state))
        self.interactions.add(user.id, data.item_type, data.item_id, t, data.source, data.recommendation_item_id)
        self.db.commit()
        return InteractionOut(recorded=True, state=_state_out(self._state(user, data.item_type, data.item_id)))

    def saved(self, user: User, kind: str | None, page: int, page_size: int) -> tuple[list[SavedItemOut], int]:
        states = fold((item_key(e), e.interaction_type, e.created_at) for e in self.interactions.events(user.id))
        keys = sorted(
            (k for k, s in states.items() if s.saved and (kind is None or k[0] == kind)),
            key=lambda k: states[k].last_at or datetime.min.replace(tzinfo=UTC),
            reverse=True,
        )
        out: list[SavedItemOut] = []
        for k in keys:
            try:
                target = self._target(k[0], uuid.UUID(k[1]))
            except AppError:
                continue  # saved item was since unpublished or deleted
            if k[0] == "destination":
                out.append(SavedItemOut(item_type="destination", destination=DestinationOut.model_validate(target)))
            else:
                out.append(SavedItemOut(item_type="attraction", attraction=AttractionOut.model_validate(target)))
        return out[(page - 1) * page_size : page * page_size], len(out)

    # ------------------------------------------------------------------ feedback & history
    def give_feedback(self, user: User, data: FeedbackIn) -> FeedbackOut:
        imp = self.runs.get_item(user.id, data.recommendation_item_id)
        if imp is None:
            raise not_found("Recommendation")  # also hides other users' impressions
        row = self.feedback.upsert(user.id, imp.id, data.rating, list(dict.fromkeys(data.reasons)), data.comment)
        self.db.commit()
        return FeedbackOut(
            recommendation_item_id=imp.id,
            rating=data.rating,
            reasons=row.reasons,
            comment=row.comment,
            updated_at=row.updated_at,
        )

    def _summary(self, run: RecommendationRun, items: list[RecommendationItem], names: dict) -> RunSummary:
        top = [names.get(i.destination_id or i.attraction_id, "(removed)") for i in items[:3]]
        return RunSummary(
            run_id=run.id,
            kind=run.kind,
            strategy=run.strategy,
            model_version=run.model_version,
            created_at=run.created_at,
            total_candidates=run.total_candidates,
            returned_count=run.returned_count,
            page=run.page,
            page_size=run.page_size,
            diversified=run.diversified,
            preferences=run.preferences,
            top_items=top,
        )

    def _names(self, items: list[RecommendationItem]) -> dict:
        names: dict = {}
        d_ids = [i.destination_id for i in items if i.destination_id]
        a_ids = [i.attraction_id for i in items if i.attraction_id]
        if d_ids:
            names.update(
                self.db.execute(select(Destination.id, Destination.name).where(Destination.id.in_(d_ids))).all()
            )
        if a_ids:
            names.update(self.db.execute(select(Attraction.id, Attraction.name).where(Attraction.id.in_(a_ids))).all())
        return names

    def history(self, user: User, kind: str | None, page: int, page_size: int) -> tuple[list[RunSummary], int]:
        runs, total = self.runs.list_runs(user.id, kind, page, page_size)
        items = self.runs.items([r.id for r in runs])
        names = self._names(items)
        by_run: dict[uuid.UUID, list[RecommendationItem]] = {}
        for it in items:
            by_run.setdefault(it.run_id, []).append(it)
        return [self._summary(r, by_run.get(r.id, []), names) for r in runs], total

    def run_detail(self, user: User, run_id: uuid.UUID) -> RunDetail:
        run = self.runs.get_run(user.id, run_id)
        if run is None:
            raise not_found("Recommendation run")
        items = self.runs.items([run.id])
        names = self._names(items)
        fb = self.feedback.for_items(user.id, [i.id for i in items])
        summary = self._summary(run, items, names)
        out_items = [
            RunItemOut(
                recommendation_item_id=i.id,
                kind=run.kind,
                item_id=i.destination_id or i.attraction_id,
                name=names.get(i.destination_id or i.attraction_id),
                rank=i.rank,
                original_rank=i.original_rank,
                score=i.score,
                confidence=i.confidence,
                explanation=i.explanation,
                feedback=fb.get(i.id),
            )
            for i in items
        ]
        return RunDetail(
            **summary.model_dump(), config=run.config, filters=run.filters, priorities=run.priorities, items=out_items
        )


__all__ = ["RecommendationService", "ScoringConfig"]
