import uuid
from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import AdminUser, CurrentUser, DbSession
from app.modules.users.service import UserService
from app.repositories.users import UserRepository
from app.schemas.user import (
    AdminUserUpdate,
    Page,
    PreferencesIn,
    PreferencesOut,
    UserOut,
    UserUpdate,
)

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserOut)
def me(user: CurrentUser) -> UserOut:
    return UserOut.model_validate(user)


@router.patch("/me", response_model=UserOut)
def update_me(data: UserUpdate, user: CurrentUser, db: DbSession) -> UserOut:
    return UserOut.model_validate(UserService(db).update_profile(user, data))


@router.get("/me/preferences", response_model=PreferencesOut)
def get_preferences(user: CurrentUser, db: DbSession) -> PreferencesOut:
    return PreferencesOut.model_validate(UserService(db).get_preferences(user))


@router.put("/me/preferences", response_model=PreferencesOut)
def put_preferences(data: PreferencesIn, user: CurrentUser, db: DbSession) -> PreferencesOut:
    return PreferencesOut.model_validate(UserService(db).set_preferences(user, data))


@router.get("", response_model=Page[UserOut])
def list_users(
    _: AdminUser,
    db: DbSession,
    q: Annotated[str | None, Query(max_length=100)] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> Page[UserOut]:
    rows, total = UserRepository(db).list(q, page, page_size)
    return Page(
        items=[UserOut.model_validate(r) for r in rows], total=total, page=page, page_size=page_size
    )


@router.patch("/{user_id}", response_model=UserOut)
def admin_update_user(
    user_id: uuid.UUID, data: AdminUserUpdate, actor: AdminUser, db: DbSession
) -> UserOut:
    return UserOut.model_validate(UserService(db).admin_update(actor, user_id, data))
