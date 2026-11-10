import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.user import AuditLog, RefreshToken, User, UserPreference


class UserRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, user_id: uuid.UUID) -> User | None:
        return self.db.get(User, user_id)

    def get_by_email(self, email: str) -> User | None:
        return self.db.scalar(select(User).where(User.email == email.lower()))

    def add(self, user: User) -> User:
        self.db.add(user)
        self.db.flush()
        return user

    def list(self, search: str | None, page: int, page_size: int) -> tuple[list[User], int]:
        stmt = select(User)
        if search:
            like = f"%{search.lower()}%"
            stmt = stmt.where(or_(User.email.ilike(like), func.lower(User.full_name).like(like)))
        total = self.db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        rows = self.db.scalars(
            stmt.order_by(User.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        ).all()
        return list(rows), total

    def get_preferences(self, user_id: uuid.UUID) -> UserPreference | None:
        return self.db.get(UserPreference, user_id)


class TokenRepository:
    def __init__(self, db: Session):
        self.db = db

    def add(self, token: RefreshToken) -> None:
        self.db.add(token)

    def get_by_hash(self, token_hash: str) -> RefreshToken | None:
        return self.db.scalar(
            select(RefreshToken).where(RefreshToken.token_hash == token_hash).with_for_update()
        )

    def revoke_family(self, family_id: uuid.UUID, now) -> None:
        for t in self.db.scalars(
            select(RefreshToken).where(
                RefreshToken.family_id == family_id, RefreshToken.revoked_at.is_(None)
            )
        ):
            t.revoked_at = now

    def revoke_all_for_user(self, user_id: uuid.UUID, now) -> None:
        for t in self.db.scalars(
            select(RefreshToken).where(
                RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None)
            )
        ):
            t.revoked_at = now


class AuditRepository:
    def __init__(self, db: Session):
        self.db = db

    def record(
        self, actor_id: uuid.UUID | None, action: str, entity_type: str, entity_id: str, detail=None
    ) -> None:
        self.db.add(
            AuditLog(
                actor_id=actor_id,
                action=action,
                entity_type=entity_type,
                entity_id=entity_id,
                detail=detail,
            )
        )
