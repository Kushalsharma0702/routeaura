import uuid
from collections.abc import Callable
from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.security import decode_access_token
from app.database.session import get_db
from app.models.user import Role, User
from app.repositories.users import UserRepository

DbSession = Annotated[Session, Depends(get_db)]
_bearer = HTTPBearer(auto_error=False)


def get_current_user(
    db: DbSession,
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> User:
    if creds is None:
        raise AppError(401, "not_authenticated", "Authentication required")
    claims = decode_access_token(creds.credentials)
    try:
        user_id = uuid.UUID(claims["sub"])
    except ValueError as exc:
        raise AppError(401, "invalid_token", "Invalid or expired token") from exc
    user = UserRepository(db).get(user_id)
    if user is None or not user.is_active:
        raise AppError(401, "invalid_token", "Invalid or expired token")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_role(*roles: Role) -> Callable[[User], User]:
    def checker(user: CurrentUser) -> User:
        # Role is read from the database, not from the token, so demotions apply immediately.
        if user.role not in roles:
            raise AppError(403, "forbidden", "You do not have permission to do that")
        return user

    return checker


AdminUser = Annotated[User, Depends(require_role(Role.ADMIN))]
