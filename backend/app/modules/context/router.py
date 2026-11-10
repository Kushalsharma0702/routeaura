import uuid

from fastapi import APIRouter

from app.api.deps import CurrentUser, DbSession
from app.modules.context.service import ContextService
from app.schemas.context import AdaptResultOut, ContextStatusOut, ProposalOut, ReportIn
from app.schemas.itinerary import ItineraryOut

router = APIRouter(tags=["context"])


@router.get("/itineraries/{itinerary_id}/context", response_model=ContextStatusOut)
def context(itinerary_id: uuid.UUID, user: CurrentUser, db: DbSession):
    return ContextService(db).status(user, itinerary_id)


@router.post("/itineraries/{itinerary_id}/context/refresh", response_model=ContextStatusOut)
def refresh(itinerary_id: uuid.UUID, user: CurrentUser, db: DbSession):
    """Fetch weather from the configured provider. 409 when none is configured; nothing is simulated."""
    return ContextService(db).refresh(user, itinerary_id)


@router.post("/itineraries/{itinerary_id}/context/report", response_model=ContextStatusOut, status_code=201)
def report(itinerary_id: uuid.UUID, body: ReportIn, user: CurrentUser, db: DbSession):
    return ContextService(db).report(user, itinerary_id, body)


@router.post("/itineraries/{itinerary_id}/adapt", response_model=AdaptResultOut)
def adapt(itinerary_id: uuid.UUID, user: CurrentUser, db: DbSession):
    """Detects issues from fresh context and creates PENDING proposals. Nothing is applied here."""
    return ContextService(db).adapt(user, itinerary_id)


@router.get("/itineraries/{itinerary_id}/adaptations", response_model=list[ProposalOut])
def proposals(itinerary_id: uuid.UUID, user: CurrentUser, db: DbSession):
    return ContextService(db).proposals(user, itinerary_id)


@router.get("/adaptations/{proposal_id}", response_model=ProposalOut)
def proposal(proposal_id: uuid.UUID, user: CurrentUser, db: DbSession):
    return ContextService(db).get(user, proposal_id)


@router.post("/adaptations/{proposal_id}/approve", response_model=ItineraryOut)
def approve(proposal_id: uuid.UUID, user: CurrentUser, db: DbSession):
    return ContextService(db).approve(user, proposal_id)


@router.post("/adaptations/{proposal_id}/reject", response_model=ProposalOut)
def reject(proposal_id: uuid.UUID, user: CurrentUser, db: DbSession):
    return ContextService(db).reject(user, proposal_id)
