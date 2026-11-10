import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.deps import AdminUser, DbSession
from app.core.errors import AppError
from app.modules.catalog.service import CatalogService, Near
from app.schemas.catalog import (
    AttractionCreate,
    AttractionOut,
    AttractionSort,
    AttractionUpdate,
    CategoryIn,
    CategoryOut,
    CategoryUpdate,
    DestinationCreate,
    DestinationOut,
    DestinationSort,
    DestinationUpdate,
)
from app.schemas.user import Page

PageNo = Annotated[int, Query(ge=1)]
PageSize = Annotated[int, Query(ge=1, le=100)]
Text = Annotated[str | None, Query(max_length=100)]
Lat = Annotated[float | None, Query(ge=-90, le=90, allow_inf_nan=False)]
Lng = Annotated[float | None, Query(ge=-180, le=180, allow_inf_nan=False)]
MAX_RADIUS_KM = 500


def near_params(lat: Lat = None, lng: Lng = None,
                radius_km: Annotated[float | None, Query(gt=0, le=MAX_RADIUS_KM)] = None) -> Near | None:
    given = [v is not None for v in (lat, lng, radius_km)]
    if not any(given):
        return None
    if not all(given):
        raise AppError(422, "validation_error", "lat, lng and radius_km must be provided together")
    return (lat, lng, radius_km * 1000)  # type: ignore[operator]


def required_near(lat: Annotated[float, Query(ge=-90, le=90, allow_inf_nan=False)],
                  lng: Annotated[float, Query(ge=-180, le=180, allow_inf_nan=False)],
                  radius_km: Annotated[float, Query(gt=0, le=MAX_RADIUS_KM)] = 10) -> Near:
    return (lat, lng, radius_km * 1000)


NearOpt = Annotated[Near | None, Depends(near_params)]
NearReq = Annotated[Near, Depends(required_near)]

# --------------------------------------------------------------------------- public (read-only)
public = APIRouter(tags=["catalog"])


@public.get("/categories", response_model=list[CategoryOut])
def list_categories(db: DbSession):
    return CatalogService(db).cats.all()


@public.get("/destinations", response_model=Page[DestinationOut])
def list_destinations(
    db: DbSession, near: NearOpt, q: Text = None, country: Text = None, category: Text = None,
    climate: Text = None, month: Annotated[int | None, Query(ge=1, le=12)] = None,
    max_cost_minor: Annotated[int | None, Query(ge=0)] = None,
    sort: DestinationSort = "name", page: PageNo = 1, page_size: PageSize = 12,
):
    if sort == "distance" and near is None:
        raise AppError(422, "validation_error", "sort=distance requires lat, lng and radius_km")
    items, total = CatalogService(db).list_destinations(
        published_only=True, q=q, country=country, category=category, climate=climate, month=month,
        max_cost_minor=max_cost_minor, near=near, sort=sort, page=page, page_size=page_size)
    return Page(items=items, total=total, page=page, page_size=page_size)


@public.get("/destinations/nearby", response_model=Page[DestinationOut])
def nearby_destinations(db: DbSession, near: NearReq, page: PageNo = 1, page_size: PageSize = 12):
    items, total = CatalogService(db).list_destinations(
        published_only=True, q=None, country=None, category=None, climate=None, month=None,
        max_cost_minor=None, near=near, sort="distance", page=page, page_size=page_size)
    return Page(items=items, total=total, page=page, page_size=page_size)


@public.get("/destinations/{ref}", response_model=DestinationOut)
def get_destination(ref: str, db: DbSession):
    return CatalogService(db).get_destination(ref, published_only=True)


def _attractions(db, published_only: bool, **f):
    items, total = CatalogService(db).list_attractions(published_only=published_only, **f)
    return Page(items=items, total=total, page=f["page"], page_size=f["page_size"])


@public.get("/destinations/{ref}/attractions", response_model=Page[AttractionOut])
def destination_attractions(
    ref: str, db: DbSession, q: Text = None, category: Text = None,
    outdoor: bool | None = None, sort: AttractionSort = "name", page: PageNo = 1, page_size: PageSize = 50,
):
    dest = CatalogService(db).get_destination(ref, published_only=True)
    return _attractions(db, True, q=q, destination_id=dest.id, category=category, outdoor=outdoor,
                        near=None, sort=sort, page=page, page_size=page_size)


@public.get("/attractions", response_model=Page[AttractionOut])
def list_attractions(
    db: DbSession, near: NearOpt, q: Text = None, destination_id: uuid.UUID | None = None,
    category: Text = None, outdoor: bool | None = None,
    sort: AttractionSort = "name", page: PageNo = 1, page_size: PageSize = 20,
):
    if sort == "distance" and near is None:
        raise AppError(422, "validation_error", "sort=distance requires lat, lng and radius_km")
    return _attractions(db, True, q=q, destination_id=destination_id, category=category,
                        outdoor=outdoor, near=near, sort=sort, page=page, page_size=page_size)


@public.get("/attractions/nearby", response_model=Page[AttractionOut])
def nearby_attractions(db: DbSession, near: NearReq, category: Text = None,
                       outdoor: bool | None = None, page: PageNo = 1, page_size: PageSize = 20):
    return _attractions(db, True, q=None, destination_id=None, category=category, outdoor=outdoor,
                        near=near, sort="distance", page=page, page_size=page_size)


@public.get("/attractions/{attraction_id}", response_model=AttractionOut)
def get_attraction(attraction_id: uuid.UUID, db: DbSession):
    return CatalogService(db).get_attraction(attraction_id, published_only=True)


# ------------------------------------------------------------------------------ admin (writes)
admin = APIRouter(prefix="/admin", tags=["catalog-admin"])


@admin.post("/categories", response_model=CategoryOut, status_code=201)
def create_category(data: CategoryIn, actor: AdminUser, db: DbSession):
    return CatalogService(db).create_category(actor, data)


@admin.patch("/categories/{category_id}", response_model=CategoryOut)
def update_category(category_id: uuid.UUID, data: CategoryUpdate, actor: AdminUser, db: DbSession):
    return CatalogService(db).update_category(actor, category_id, data)


@admin.delete("/categories/{category_id}", status_code=204)
def delete_category(category_id: uuid.UUID, actor: AdminUser, db: DbSession):
    CatalogService(db).delete_category(actor, category_id)


@admin.get("/destinations", response_model=Page[DestinationOut])
def admin_list_destinations(
    _: AdminUser, db: DbSession, q: Text = None, country: Text = None, category: Text = None,
    climate: Text = None, include_deleted: bool = False,
    sort: DestinationSort = "name", page: PageNo = 1, page_size: PageSize = 20,
):
    items, total = CatalogService(db).list_destinations(
        published_only=False, include_deleted=include_deleted, q=q, country=country,
        category=category, climate=climate, month=None, max_cost_minor=None, near=None,
        sort="name" if sort == "distance" else sort, page=page, page_size=page_size)
    return Page(items=items, total=total, page=page, page_size=page_size)


@admin.get("/destinations/{destination_id}", response_model=DestinationOut)
def admin_get_destination(destination_id: uuid.UUID, _: AdminUser, db: DbSession):
    return CatalogService(db).get_destination(str(destination_id), published_only=False)


@admin.post("/destinations", response_model=DestinationOut, status_code=201)
def create_destination(data: DestinationCreate, actor: AdminUser, db: DbSession):
    return CatalogService(db).create_destination(actor, data)


@admin.patch("/destinations/{destination_id}", response_model=DestinationOut)
def update_destination(destination_id: uuid.UUID, data: DestinationUpdate, actor: AdminUser, db: DbSession):
    return CatalogService(db).update_destination(actor, destination_id, data)


@admin.delete("/destinations/{destination_id}", status_code=204)
def delete_destination(destination_id: uuid.UUID, actor: AdminUser, db: DbSession):
    CatalogService(db).delete_destination(actor, destination_id)


@admin.get("/attractions", response_model=Page[AttractionOut])
def admin_list_attractions(
    _: AdminUser, db: DbSession, destination_id: uuid.UUID | None = None, q: Text = None,
    category: Text = None, sort: AttractionSort = "name", page: PageNo = 1, page_size: PageSize = 50,
):
    return _attractions(db, False, q=q, destination_id=destination_id, category=category,
                        outdoor=None, near=None, sort="name" if sort == "distance" else sort,
                        page=page, page_size=page_size)


@admin.get("/attractions/{attraction_id}", response_model=AttractionOut)
def admin_get_attraction(attraction_id: uuid.UUID, _: AdminUser, db: DbSession):
    return CatalogService(db).get_attraction(attraction_id, published_only=False)


@admin.post("/attractions", response_model=AttractionOut, status_code=201)
def create_attraction(data: AttractionCreate, actor: AdminUser, db: DbSession):
    return CatalogService(db).create_attraction(actor, data)


@admin.patch("/attractions/{attraction_id}", response_model=AttractionOut)
def update_attraction(attraction_id: uuid.UUID, data: AttractionUpdate, actor: AdminUser, db: DbSession):
    return CatalogService(db).update_attraction(actor, attraction_id, data)


@admin.delete("/attractions/{attraction_id}", status_code=204)
def delete_attraction(attraction_id: uuid.UUID, actor: AdminUser, db: DbSession):
    CatalogService(db).delete_attraction(actor, attraction_id)
