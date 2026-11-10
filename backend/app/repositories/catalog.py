import uuid
from datetime import UTC, datetime

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session

from app.models.catalog import Attraction, AttractionCategory, Destination, destination_categories
from app.modules.spatial.backends import SpatialBackend


def like_pattern(q: str) -> str:
    """Escape LIKE wildcards in user input so '%' and '_' match literally."""
    return "%" + q.replace("\\", "\\\\").replace("%", r"\%").replace("_", r"\_") + "%"


class CategoryRepository:
    def __init__(self, db: Session):
        self.db = db

    def all(self) -> list[AttractionCategory]:
        return list(self.db.scalars(select(AttractionCategory).order_by(AttractionCategory.name)))

    def get(self, id_: uuid.UUID) -> AttractionCategory | None:
        return self.db.get(AttractionCategory, id_)

    def get_many(self, ids: list[uuid.UUID]) -> list[AttractionCategory]:
        if not ids:
            return []
        return list(self.db.scalars(select(AttractionCategory).where(AttractionCategory.id.in_(ids))))

    def slug_exists(self, slug: str) -> bool:
        return self.db.scalar(select(AttractionCategory.id).where(AttractionCategory.slug == slug)) is not None

    def name_exists(self, name: str, exclude: uuid.UUID | None = None) -> bool:
        stmt = select(AttractionCategory.id).where(func.lower(AttractionCategory.name) == name.lower())
        if exclude:
            stmt = stmt.where(AttractionCategory.id != exclude)
        return self.db.scalar(stmt) is not None

    def usage_count(self, id_: uuid.UUID) -> int:
        a = self.db.scalar(select(func.count()).select_from(Attraction).where(Attraction.category_id == id_))
        d = self.db.scalar(
            select(func.count()).select_from(destination_categories)
            .where(destination_categories.c.category_id == id_)
        )
        return (a or 0) + (d or 0)


class DestinationRepository:
    def __init__(self, db: Session, spatial: SpatialBackend):
        self.db = db
        self.spatial = spatial

    def get(self, id_: uuid.UUID, *, include_deleted: bool = False) -> Destination | None:
        d = self.db.get(Destination, id_)
        return d if d and (include_deleted or d.deleted_at is None) else None

    def get_by_slug(self, slug: str) -> Destination | None:
        return self.db.scalar(select(Destination).where(Destination.slug == slug, Destination.deleted_at.is_(None)))

    def slug_exists(self, slug: str) -> bool:
        return self.db.scalar(select(Destination.id).where(Destination.slug == slug)) is not None

    def attraction_counts(self, ids: list[uuid.UUID], published_only: bool) -> dict[uuid.UUID, int]:
        if not ids:
            return {}
        stmt = (
            select(Attraction.destination_id, func.count())
            .where(Attraction.destination_id.in_(ids), Attraction.deleted_at.is_(None))
            .group_by(Attraction.destination_id)
        )
        if published_only:
            stmt = stmt.where(Attraction.is_published.is_(True))
        return dict(self.db.execute(stmt).all())

    def search(
        self, *, published_only: bool, q: str | None, country: str | None, category: str | None,
        climate: str | None, month: int | None, max_cost_minor: int | None,
        near: tuple[float, float, float] | None, sort: str, page: int, page_size: int,
        include_deleted: bool = False,
    ) -> tuple[list[tuple[Destination, float | None]], int]:
        t = Destination.__table__
        dist = self.spatial.distance_m(t, near[0], near[1]) if near else None
        stmt: Select = select(Destination, dist) if dist is not None else select(Destination)
        if not include_deleted:
            stmt = stmt.where(Destination.deleted_at.is_(None))
        if published_only:
            stmt = stmt.where(Destination.is_published.is_(True))
        if q:
            p = like_pattern(q)
            stmt = stmt.where(or_(Destination.name.ilike(p), Destination.country.ilike(p),
                                  Destination.region.ilike(p), Destination.description.ilike(p)))
        if country:
            stmt = stmt.where(func.lower(Destination.country) == country.lower())
        if climate:
            stmt = stmt.where(Destination.climate == climate)
        if category:
            stmt = stmt.where(Destination.categories.any(AttractionCategory.slug == category))
        if max_cost_minor is not None:
            stmt = stmt.where(Destination.estimated_cost_per_day_minor <= max_cost_minor)
        if month:
            s, e = Destination.best_season_start_month, Destination.best_season_end_month
            stmt = stmt.where(or_(
                (s <= e) & (s <= month) & (e >= month),   # season inside one calendar year (e.g. Jun-Sep)
                (s > e) & ((month >= s) | (month <= e)),  # season wraps over the new year
            ))
        if near:
            stmt = stmt.where(self.spatial.within(t, near[0], near[1], near[2]))

        total = self.db.scalar(select(func.count()).select_from(stmt.with_only_columns(Destination.id).subquery())) or 0
        order = {
            "name": Destination.name.asc(), "-name": Destination.name.desc(),
            "cost": Destination.estimated_cost_per_day_minor.asc().nulls_last(),
            "-cost": Destination.estimated_cost_per_day_minor.desc().nulls_last(),
            "duration": Destination.recommended_duration_days.asc().nulls_last(),
            "newest": Destination.created_at.desc(),
        }
        if sort == "distance" and dist is not None:
            ordering = [dist.asc(), Destination.name.asc()]
        else:
            ordering = [order.get(sort, Destination.name.asc()), Destination.name.asc()]
        rows = self.db.execute(stmt.order_by(*ordering).offset((page - 1) * page_size).limit(page_size)).all()
        if dist is not None:
            return [(r[0], float(r[1])) for r in rows], total
        return [(r[0], None) for r in rows], total

    def add(self, d: Destination) -> Destination:
        self.db.add(d)
        self.db.flush()
        return d

    def soft_delete(self, d: Destination) -> None:
        now = datetime.now(UTC)
        d.deleted_at = now
        d.is_published = False
        for a in self.db.scalars(select(Attraction).where(Attraction.destination_id == d.id,
                                                           Attraction.deleted_at.is_(None))):
            a.deleted_at = now
            a.is_published = False


class AttractionRepository:
    def __init__(self, db: Session, spatial: SpatialBackend):
        self.db = db
        self.spatial = spatial

    def get(self, id_: uuid.UUID, *, include_deleted: bool = False) -> Attraction | None:
        a = self.db.get(Attraction, id_)
        return a if a and (include_deleted or a.deleted_at is None) else None

    def slug_exists(self, destination_id: uuid.UUID, slug: str) -> bool:
        return self.db.scalar(select(Attraction.id).where(Attraction.destination_id == destination_id,
                                                           Attraction.slug == slug)) is not None

    def add(self, a: Attraction) -> Attraction:
        self.db.add(a)
        self.db.flush()
        return a

    def search(
        self, *, published_only: bool, q: str | None, destination_id: uuid.UUID | None,
        category: str | None, outdoor: bool | None, near: tuple[float, float, float] | None,
        sort: str, page: int, page_size: int,
    ) -> tuple[list[tuple[Attraction, float | None]], int]:
        t = Attraction.__table__
        dist = self.spatial.distance_m(t, near[0], near[1]) if near else None
        stmt: Select = select(Attraction, dist) if dist is not None else select(Attraction)
        stmt = stmt.where(Attraction.deleted_at.is_(None))
        if published_only:
            # an attraction is only public when it AND its destination are published
            stmt = stmt.where(
                Attraction.is_published.is_(True),
                Attraction.destination_id.in_(
                    select(Destination.id).where(Destination.is_published.is_(True),
                                                 Destination.deleted_at.is_(None))),
            )
        if destination_id:
            stmt = stmt.where(Attraction.destination_id == destination_id)
        if q:
            p = like_pattern(q)
            stmt = stmt.where(or_(Attraction.name.ilike(p), Attraction.description.ilike(p)))
        if category:
            stmt = stmt.where(Attraction.category.has(AttractionCategory.slug == category))
        if outdoor is not None:
            stmt = stmt.where(Attraction.is_outdoor.is_(outdoor))
        if near:
            stmt = stmt.where(self.spatial.within(t, near[0], near[1], near[2]))

        total = self.db.scalar(select(func.count()).select_from(stmt.with_only_columns(Attraction.id).subquery())) or 0
        order = {
            "name": Attraction.name.asc(), "-name": Attraction.name.desc(),
            "cost": Attraction.estimated_cost_minor.asc().nulls_last(),
            "-cost": Attraction.estimated_cost_minor.desc().nulls_last(),
            "duration": Attraction.typical_duration_minutes.asc(),
            "newest": Attraction.created_at.desc(),
        }
        if sort == "distance" and dist is not None:
            ordering = [dist.asc(), Attraction.name.asc()]
        else:
            ordering = [order.get(sort, Attraction.name.asc()), Attraction.name.asc()]
        rows = self.db.execute(stmt.order_by(*ordering).offset((page - 1) * page_size).limit(page_size)).all()
        if dist is not None:
            return [(r[0], float(r[1])) for r in rows], total
        return [(r[0], None) for r in rows], total
