import uuid
from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import AppError, not_found
from app.models.catalog import Attraction, AttractionCategory, Destination
from app.models.user import User
from app.modules.catalog.slugs import slugify, unique_slug
from app.modules.spatial.backends import get_spatial_backend
from app.repositories.catalog import AttractionRepository, CategoryRepository, DestinationRepository
from app.repositories.users import AuditRepository
from app.schemas.catalog import (
    AttractionCreate,
    AttractionOut,
    AttractionUpdate,
    CategoryIn,
    CategoryUpdate,
    DestinationCreate,
    DestinationOut,
    DestinationUpdate,
)

Near = tuple[float, float, float]  # lat, lng, radius in metres


def _need[T](value: T | None, what: str) -> T:
    if value is None:
        raise not_found(what)
    return value


class CatalogService:
    def __init__(self, db: Session):
        self.db = db
        spatial = get_spatial_backend(db)
        self.spatial = spatial
        self.dest = DestinationRepository(db, spatial)
        self.attr = AttractionRepository(db, spatial)
        self.cats = CategoryRepository(db)
        self.audit = AuditRepository(db)

    # ---------- categories ----------
    def create_category(self, actor: User, data: CategoryIn) -> AttractionCategory:
        if self.cats.name_exists(data.name):
            raise AppError(409, "category_exists", "A category with this name already exists")
        cat = AttractionCategory(
            name=data.name.strip(), description=data.description,
            slug=unique_slug(data.name, self.cats.slug_exists),
        )
        self.db.add(cat)
        self.db.flush()
        self.audit.record(actor.id, "category.create", "category", str(cat.id), {"name": cat.name})
        self.db.commit()
        return cat

    def update_category(self, actor: User, id_: uuid.UUID, data: CategoryUpdate) -> AttractionCategory:
        cat = _need(self.cats.get(id_), "Category")
        changes = data.model_dump(exclude_unset=True)
        if "name" in changes and changes["name"] is not None:
            if self.cats.name_exists(changes["name"], exclude=cat.id):
                raise AppError(409, "category_exists", "A category with this name already exists")
            cat.name = changes["name"].strip()
        if "description" in changes:
            cat.description = changes["description"]
        self.audit.record(actor.id, "category.update", "category", str(cat.id), changes)
        self.db.commit()
        return cat

    def delete_category(self, actor: User, id_: uuid.UUID) -> None:
        cat = _need(self.cats.get(id_), "Category")
        n = self.cats.usage_count(cat.id)
        if n:
            raise AppError(409, "category_in_use", f"Category is used by {n} record(s)")
        self.db.delete(cat)
        self.audit.record(actor.id, "category.delete", "category", str(id_))
        self.db.commit()

    # ---------- destinations ----------
    def _destination_out(self, d: Destination, counts: dict, dist: float | None = None) -> DestinationOut:
        out = DestinationOut.model_validate(d)
        out.attraction_count = counts.get(d.id, 0)
        out.distance_m = dist
        return out

    def list_destinations(self, *, published_only: bool, include_deleted: bool = False, **f):
        rows, total = self.dest.search(published_only=published_only, include_deleted=include_deleted, **f)
        counts = self.dest.attraction_counts([d.id for d, _ in rows], published_only)
        return [self._destination_out(d, counts, dist) for d, dist in rows], total

    def get_destination(self, ref: str, *, published_only: bool) -> DestinationOut:
        d = None
        try:
            d = self.dest.get(uuid.UUID(ref))
        except ValueError:
            d = self.dest.get_by_slug(ref)
        if d is None or (published_only and not d.is_published):
            raise not_found("Destination")
        return self._destination_out(d, self.dest.attraction_counts([d.id], published_only))

    def _resolve_categories(self, ids: list[uuid.UUID]) -> list[AttractionCategory]:
        found = self.cats.get_many(list(set(ids)))
        if len(found) != len(set(ids)):
            raise AppError(422, "unknown_category", "One or more category_ids do not exist")
        return found

    def create_destination(self, actor: User, data: DestinationCreate) -> DestinationOut:
        fields = data.model_dump(exclude={"category_ids"})
        d = Destination(**fields, source="admin",
                        slug=unique_slug(data.name, self.dest.slug_exists))
        d.categories = self._resolve_categories(data.category_ids)
        self._flush(lambda: self.dest.add(d))
        self.audit.record(actor.id, "destination.create", "destination", str(d.id), {"name": d.name})
        self.db.commit()
        return self._destination_out(d, {})

    def update_destination(self, actor: User, id_: uuid.UUID, data: DestinationUpdate) -> DestinationOut:
        d = _need(self.dest.get(id_), "Destination")
        changes = data.model_dump(exclude_unset=True)
        cat_ids = changes.pop("category_ids", None)
        for non_null in ("name", "country", "latitude", "longitude", "description", "images", "is_published"):
            if non_null in changes and changes[non_null] is None:
                raise AppError(422, "validation_error", f"{non_null} cannot be null")
        for k, v in changes.items():
            setattr(d, k, v)
        if (d.best_season_start_month is None) != (d.best_season_end_month is None):
            self.db.rollback()
            raise AppError(422, "validation_error", "Set both season months or neither")
        if cat_ids is not None:
            d.categories = self._resolve_categories(cat_ids)
        self._flush(lambda: self.db.flush())
        self.audit.record(actor.id, "destination.update", "destination", str(d.id),
                          {k: str(v)[:80] for k, v in changes.items()})
        self.db.commit()
        return self._destination_out(d, self.dest.attraction_counts([d.id], False))

    def delete_destination(self, actor: User, id_: uuid.UUID) -> None:
        d = _need(self.dest.get(id_), "Destination")
        self.dest.soft_delete(d)
        self.audit.record(actor.id, "destination.delete", "destination", str(d.id), {"name": d.name})
        self.db.commit()

    # ---------- attractions ----------
    def get_attraction(self, id_: uuid.UUID, *, published_only: bool) -> AttractionOut:
        a = self.attr.get(id_)
        if a is None or (published_only and not (a.is_published and a.destination.is_published
                                                  and a.destination.deleted_at is None)):
            raise not_found("Attraction")
        return AttractionOut.model_validate(a)

    def list_attractions(self, *, published_only: bool, **f):
        rows, total = self.attr.search(published_only=published_only, **f)
        out = []
        for a, dist in rows:
            o = AttractionOut.model_validate(a)
            o.distance_m = dist
            out.append(o)
        return out, total

    def create_attraction(self, actor: User, data: AttractionCreate) -> AttractionOut:
        if self.dest.get(data.destination_id) is None:
            raise AppError(422, "unknown_destination", "destination_id does not exist")
        if self.cats.get(data.category_id) is None:
            raise AppError(422, "unknown_category", "category_id does not exist")
        fields = data.model_dump()
        a = Attraction(**fields, source="admin",
                       slug=unique_slug(data.name, lambda s: self.attr.slug_exists(data.destination_id, s)))
        a.opening_hours_source = "admin" if data.opening_hours is not None else None
        self._flush(lambda: self.attr.add(a))
        self.audit.record(actor.id, "attraction.create", "attraction", str(a.id), {"name": a.name})
        self.db.commit()
        self.db.refresh(a)
        return AttractionOut.model_validate(a)

    def update_attraction(self, actor: User, id_: uuid.UUID, data: AttractionUpdate) -> AttractionOut:
        a = _need(self.attr.get(id_), "Attraction")
        changes = data.model_dump(exclude_unset=True)
        for non_null in ("name", "latitude", "longitude", "category_id", "description", "images",
                         "is_published", "is_outdoor", "typical_duration_minutes"):
            if non_null in changes and changes[non_null] is None:
                raise AppError(422, "validation_error", f"{non_null} cannot be null")
        if "category_id" in changes and self.cats.get(changes["category_id"]) is None:
            raise AppError(422, "unknown_category", "category_id does not exist")
        if "opening_hours" in changes:
            a.opening_hours_source = "admin" if changes["opening_hours"] is not None else None
        for k, v in changes.items():
            setattr(a, k, v)
        self._flush(lambda: self.db.flush())
        self.audit.record(actor.id, "attraction.update", "attraction", str(a.id),
                          {k: str(v)[:80] for k, v in changes.items()})
        self.db.commit()
        self.db.refresh(a)
        return AttractionOut.model_validate(a)

    def delete_attraction(self, actor: User, id_: uuid.UUID) -> None:
        a = _need(self.attr.get(id_), "Attraction")
        a.deleted_at = datetime.now(UTC)
        a.is_published = False
        self.audit.record(actor.id, "attraction.delete", "attraction", str(a.id), {"name": a.name})
        self.db.commit()

    def _flush(self, fn) -> None:
        try:
            fn()
        except IntegrityError as exc:
            self.db.rollback()
            raise AppError(409, "conflict", "The change conflicts with existing data") from exc


__all__ = ["CatalogService", "Near", "slugify"]
