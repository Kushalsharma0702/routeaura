import uuid

from fastapi import APIRouter

from app.api.deps import CurrentUser, DbSession
from app.modules.routing.service import OptimizationService
from app.schemas.itinerary import ItineraryOut
from app.schemas.optimization import OptimizationOut, OptimizeRequest

router = APIRouter(tags=["optimization"])


@router.post("/itineraries/{itinerary_id}/optimize", response_model=OptimizationOut, status_code=201)
def optimize(itinerary_id: uuid.UUID, req: OptimizeRequest, user: CurrentUser, db: DbSession):
    """Computes a PREVIEW (original vs optimized). Nothing changes until the traveler applies it."""
    return OptimizationService(db).preview(user, itinerary_id, req)


@router.get("/itineraries/{itinerary_id}/optimizations", response_model=list[OptimizationOut])
def optimizations(itinerary_id: uuid.UUID, user: CurrentUser, db: DbSession):
    return OptimizationService(db).history(user, itinerary_id)


@router.get("/optimizations/{run_id}", response_model=OptimizationOut)
def optimization(run_id: uuid.UUID, user: CurrentUser, db: DbSession):
    return OptimizationService(db).get(user, run_id)


@router.post("/optimizations/{run_id}/apply", response_model=ItineraryOut)
def apply_optimization(run_id: uuid.UUID, user: CurrentUser, db: DbSession):
    return OptimizationService(db).apply(user, run_id)
