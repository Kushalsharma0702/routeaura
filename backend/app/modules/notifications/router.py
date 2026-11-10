import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Query
from pydantic import BaseModel, ConfigDict

from app.api.deps import CurrentUser, DbSession
from app.modules.notifications.service import NotificationService
from app.schemas.user import Page

router = APIRouter(prefix="/notifications", tags=["notifications"])


class NotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    type: str
    title: str
    body: str
    data: dict
    read_at: datetime | None
    created_at: datetime


@router.get("", response_model=Page[NotificationOut])
def list_notifications(
    user: CurrentUser,
    db: DbSession,
    unread: bool = False,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
):
    rows, total = NotificationService(db).list(user, unread, page, page_size)
    return Page(items=[NotificationOut.model_validate(r) for r in rows], total=total, page=page, page_size=page_size)


@router.get("/unread-count")
def unread_count(user: CurrentUser, db: DbSession) -> dict:
    return {"unread": NotificationService(db).unread_count(user)}


@router.post("/read-all")
def read_all(user: CurrentUser, db: DbSession) -> dict:
    return {"marked": NotificationService(db).read_all(user)}


@router.post("/{notification_id}/read", response_model=NotificationOut)
def mark_read(notification_id: uuid.UUID, user: CurrentUser, db: DbSession):
    return NotificationOut.model_validate(NotificationService(db).mark_read(user, notification_id))
