import uuid
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.errors import AppError, not_found
from app.models.user import User, UserPreference
from app.repositories.users import AuditRepository, TokenRepository, UserRepository
from app.schemas.user import AdminUserUpdate, PreferencesIn, UserUpdate


class UserService:
    def __init__(self, db: Session):
        self.db = db
        self.users = UserRepository(db)
        self.audit = AuditRepository(db)

    def update_profile(self, user: User, data: UserUpdate) -> User:
        changes = data.model_dump(exclude_unset=True)
        for field, value in changes.items():
            setattr(user, field, value.strip() if isinstance(value, str) else value)
        self.db.commit()
        return user

    def get_preferences(self, user: User) -> UserPreference:
        prefs = self.users.get_preferences(user.id)
        if prefs is None:
            prefs = UserPreference(user_id=user.id, interests=[])
            self.db.add(prefs)
            self.db.commit()
        return prefs

    def set_preferences(self, user: User, data: PreferencesIn) -> UserPreference:
        prefs = self.get_preferences(user)
        for field, value in data.model_dump().items():
            setattr(prefs, field, value)
        self.db.commit()
        return prefs

    def admin_update(self, actor: User, user_id: uuid.UUID, data: AdminUserUpdate) -> User:
        target = self.users.get(user_id)
        if target is None:
            raise not_found("User")
        if target.id == actor.id:
            raise AppError(400, "self_modification", "You cannot change your own role or status")
        changes = data.model_dump(exclude_unset=True, exclude_none=True)
        before = {k: getattr(target, k) for k in changes}
        for field, value in changes.items():
            setattr(target, field, value)
        if changes.get("is_active") is False:
            TokenRepository(self.db).revoke_all_for_user(target.id, datetime.now(UTC))
        self.audit.record(
            actor.id,
            "user.update",
            "user",
            str(target.id),
            {"before": {k: str(v) for k, v in before.items()},
             "after": {k: str(v) for k, v in changes.items()}},
        )
        self.db.commit()
        return target
