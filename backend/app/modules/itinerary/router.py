import uuid
from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import CurrentUser, DbSession
from app.modules.itinerary.service import ItineraryService
from app.schemas.itinerary import (
    AddActivity,
    ItineraryOut,
    ItinerarySummary,
    ItineraryUpdate,
    RegenerateRequest,
    ReorderRequest,
    TripRequest,
    UpdateActivity,
    VersionDetail,
    VersionOut,
)
from app.schemas.user import Page

router = APIRouter(prefix="/itineraries", tags=["itineraries"])


@router.post("/generate", response_model=ItineraryOut, status_code=201)
def generate(req: TripRequest, user: CurrentUser, db: DbSession):
    return ItineraryService(db).generate(user, req)


@router.get("", response_model=Page[ItinerarySummary])
def list_itineraries(
    user: CurrentUser,
    db: DbSession,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
):
    items, total = ItineraryService(db).list(user, page, page_size)
    return Page(items=items, total=total, page=page, page_size=page_size)


@router.get("/{itinerary_id}", response_model=ItineraryOut)
def get_itinerary(itinerary_id: uuid.UUID, user: CurrentUser, db: DbSession):
    return ItineraryService(db).get(user, itinerary_id)


@router.patch("/{itinerary_id}", response_model=ItineraryOut)
def update_itinerary(itinerary_id: uuid.UUID, data: ItineraryUpdate, user: CurrentUser, db: DbSession):
    return ItineraryService(db).update(user, itinerary_id, data)


@router.delete("/{itinerary_id}", status_code=204)
def delete_itinerary(itinerary_id: uuid.UUID, user: CurrentUser, db: DbSession):
    ItineraryService(db).delete(user, itinerary_id)


@router.post("/{itinerary_id}/regenerate", response_model=ItineraryOut)
def regenerate(itinerary_id: uuid.UUID, req: RegenerateRequest, user: CurrentUser, db: DbSession):
    return ItineraryService(db).regenerate(user, itinerary_id, req)


@router.post("/{itinerary_id}/activities", response_model=ItineraryOut, status_code=201)
def add_activity(itinerary_id: uuid.UUID, data: AddActivity, user: CurrentUser, db: DbSession):
    return ItineraryService(db).add_activity(user, itinerary_id, data)


@router.patch("/{itinerary_id}/activities/{activity_id}", response_model=ItineraryOut)
def update_activity(
    itinerary_id: uuid.UUID, activity_id: uuid.UUID, data: UpdateActivity, user: CurrentUser, db: DbSession
):
    return ItineraryService(db).update_activity(user, itinerary_id, activity_id, data)


@router.delete("/{itinerary_id}/activities/{activity_id}", response_model=ItineraryOut)
def remove_activity(itinerary_id: uuid.UUID, activity_id: uuid.UUID, user: CurrentUser, db: DbSession):
    return ItineraryService(db).remove_activity(user, itinerary_id, activity_id)


@router.post("/{itinerary_id}/reorder", response_model=ItineraryOut)
def reorder(itinerary_id: uuid.UUID, data: ReorderRequest, user: CurrentUser, db: DbSession):
    return ItineraryService(db).reorder(user, itinerary_id, data)


@router.get("/{itinerary_id}/versions", response_model=list[VersionOut])
def versions(itinerary_id: uuid.UUID, user: CurrentUser, db: DbSession):
    return ItineraryService(db).versions(user, itinerary_id)


@router.get("/{itinerary_id}/versions/{version}", response_model=VersionDetail)
def version_detail(itinerary_id: uuid.UUID, version: int, user: CurrentUser, db: DbSession):
    return ItineraryService(db).version_detail(user, itinerary_id, version)


@router.post("/{itinerary_id}/versions/{version}/restore", response_model=ItineraryOut)
def restore(itinerary_id: uuid.UUID, version: int, user: CurrentUser, db: DbSession):
    return ItineraryService(db).restore(user, itinerary_id, version)
