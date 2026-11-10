import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError
from app.core.security import (
    create_access_token,
    hash_password,
    hash_refresh_token,
    new_refresh_token,
    verify_password,
)
from app.models.user import RefreshToken, Role, User
from app.repositories.users import TokenRepository, UserRepository
from app.schemas.auth import RegisterIn

INVALID_CREDENTIALS = AppError(401, "invalid_credentials", "Invalid email or password")


def _now() -> datetime:
    return datetime.now(UTC)


class AuthService:
    def __init__(self, db: Session):
        self.db = db
        self.users = UserRepository(db)
        self.tokens = TokenRepository(db)

    def register(self, data: RegisterIn) -> User:
        if self.users.get_by_email(data.email):
            raise AppError(409, "email_taken", "An account with this email already exists")
        user = User(
            email=data.email.lower(),
            full_name=data.full_name.strip(),
            phone=data.phone or None,
            password_hash=hash_password(data.password),
            role=Role.TRAVELER,  # self-registration can never create an admin
        )
        try:
            self.users.add(user)
            self.db.commit()
        except IntegrityError as exc:  # concurrent duplicate registration
            self.db.rollback()
            raise AppError(409, "email_taken", "An account with this email already exists") from exc
        return user

    def login(self, email: str, password: str) -> tuple[User, str, int, str]:
        user = self.users.get_by_email(email)
        ok = verify_password(password, user.password_hash if user else None)
        if not user or not ok:
            raise INVALID_CREDENTIALS
        if not user.is_active:
            raise AppError(403, "account_disabled", "This account has been disabled")
        return (user, *self._issue(user, family_id=uuid.uuid4()))

    def refresh(self, raw_token: str | None) -> tuple[User, str, int, str]:
        if not raw_token:
            raise AppError(401, "invalid_refresh", "Session expired")
        stored = self.tokens.get_by_hash(hash_refresh_token(raw_token))
        if stored is None:
            raise AppError(401, "invalid_refresh", "Session expired")
        now = _now()
        if stored.revoked_at is not None:
            # A rotated token was replayed: assume theft and kill the whole session.
            self.tokens.revoke_family(stored.family_id, now)
            self.db.commit()
            raise AppError(401, "invalid_refresh", "Session expired")
        if stored.expires_at <= now:
            raise AppError(401, "invalid_refresh", "Session expired")
        user = self.users.get(stored.user_id)
        if user is None or not user.is_active:
            raise AppError(401, "invalid_refresh", "Session expired")
        stored.revoked_at = now
        return (user, *self._issue(user, family_id=stored.family_id))

    def logout(self, raw_token: str | None) -> None:
        if not raw_token:
            return
        stored = self.tokens.get_by_hash(hash_refresh_token(raw_token))
        if stored:
            self.tokens.revoke_family(stored.family_id, _now())
            self.db.commit()

    def _issue(self, user: User, family_id: uuid.UUID) -> tuple[str, int, str]:
        """Returns (access_token, expires_in, raw_refresh_token) and commits."""
        s = get_settings()
        raw = new_refresh_token()
        self.tokens.add(
            RefreshToken(
                user_id=user.id,
                family_id=family_id,
                token_hash=hash_refresh_token(raw),
                expires_at=_now() + timedelta(days=s.refresh_token_days),
            )
        )
        self.db.commit()
        access, expires_in = create_access_token(user.id, user.role.value)
        return access, expires_in, raw
