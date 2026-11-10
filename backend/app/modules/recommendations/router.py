import uuid
from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import CurrentUser, DbSession
from app.modules.recommendations.service import RecommendationService
from app.schemas.recommendations import (
    FeedbackIn,
    FeedbackOut,
    InteractionIn,
    InteractionOut,
    ItemStateOut,
    Kind,
    RecommendationRequest,
    RecommendationResponse,
    RunDetail,
    RunSummary,
    SavedItemOut,
)
from app.schemas.user import Page

PageNo = Annotated[int, Query(ge=1)]
PageSize = Annotated[int, Query(ge=1, le=100)]

router = APIRouter(prefix="/recommendations", tags=["recommendations"])
interactions = APIRouter(prefix="/interactions", tags=["interactions"])


@router.post("/destinations", response_model=RecommendationResponse)
def recommend_destinations(req: RecommendationRequest, user: CurrentUser, db: DbSession):
    return RecommendationService(db).recommend(user, "destination", req)


@router.post("/attractions", response_model=RecommendationResponse)
def recommend_attractions(req: RecommendationRequest, user: CurrentUser, db: DbSession):
    return RecommendationService(db).recommend(user, "attraction", req)


@router.get("/history", response_model=Page[RunSummary])
def history(user: CurrentUser, db: DbSession, kind: Kind | None = None, page: PageNo = 1, page_size: PageSize = 20):
    items, total = RecommendationService(db).history(user, kind, page, page_size)
    return Page(items=items, total=total, page=page, page_size=page_size)


@router.get("/history/{run_id}", response_model=RunDetail)
def history_detail(run_id: uuid.UUID, user: CurrentUser, db: DbSession):
    return RecommendationService(db).run_detail(user, run_id)


@router.post("/feedback", response_model=FeedbackOut)
def feedback(data: FeedbackIn, user: CurrentUser, db: DbSession):
    return RecommendationService(db).give_feedback(user, data)


@interactions.post("", response_model=InteractionOut)
def record_interaction(data: InteractionIn, user: CurrentUser, db: DbSession):
    return RecommendationService(db).record_interaction(user, data)


@interactions.get("/state", response_model=ItemStateOut)
def item_state(item_type: Kind, item_id: uuid.UUID, user: CurrentUser, db: DbSession):
    return RecommendationService(db).item_state(user, item_type, item_id)


@interactions.get("/saved", response_model=Page[SavedItemOut])
def saved(user: CurrentUser, db: DbSession, item_type: Kind | None = None, page: PageNo = 1, page_size: PageSize = 20):
    items, total = RecommendationService(db).saved(user, item_type, page, page_size)
    return Page(items=items, total=total, page=page, page_size=page_size)
