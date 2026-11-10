from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, Response, status

from app.api.deps import DbSession
from app.core.config import get_settings
from app.core.ratelimit import rate_limit
from app.modules.authentication.service import AuthService
from app.schemas.auth import AuthOut, LoginIn, RegisterIn
from app.schemas.user import UserOut

router = APIRouter(prefix="/auth", tags=["auth"])
_limit = Depends(rate_limit("auth", limit=10, window_s=60))
COOKIE_PATH = "/api/v1/auth"


def _set_cookie(response: Response, token: str) -> None:
    s = get_settings()
    response.set_cookie(
        s.refresh_cookie_name,
        token,
        max_age=s.refresh_token_days * 86400,
        httponly=True,
        secure=s.cookie_secure,
        samesite="lax",
        path=COOKIE_PATH,
    )


def _clear_cookie(response: Response) -> None:
    response.delete_cookie(get_settings().refresh_cookie_name, path=COOKIE_PATH)


@router.post("/register", response_model=AuthOut, status_code=status.HTTP_201_CREATED,
             dependencies=[_limit])
def register(data: RegisterIn, response: Response, db: DbSession) -> AuthOut:
    svc = AuthService(db)
    svc.register(data)
    user, access, expires_in, refresh = svc.login(data.email, data.password)
    _set_cookie(response, refresh)
    return AuthOut(access_token=access, expires_in=expires_in, user=UserOut.model_validate(user))


@router.post("/login", response_model=AuthOut, dependencies=[_limit])
def login(data: LoginIn, response: Response, db: DbSession) -> AuthOut:
    user, access, expires_in, refresh = AuthService(db).login(data.email, data.password)
    _set_cookie(response, refresh)
    return AuthOut(access_token=access, expires_in=expires_in, user=UserOut.model_validate(user))


@router.post("/refresh", response_model=AuthOut, dependencies=[_limit])
def refresh(
    response: Response,
    db: DbSession,
    ra_refresh: Annotated[str | None, Cookie()] = None,
) -> AuthOut:
    user, access, expires_in, new_refresh = AuthService(db).refresh(ra_refresh)
    _set_cookie(response, new_refresh)
    return AuthOut(access_token=access, expires_in=expires_in, user=UserOut.model_validate(user))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    response: Response,
    db: DbSession,
    ra_refresh: Annotated[str | None, Cookie()] = None,
) -> None:
    AuthService(db).logout(ra_refresh)
    _clear_cookie(response)
