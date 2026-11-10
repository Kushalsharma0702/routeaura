"""Development-only seed accounts. Refuses to run outside ENVIRONMENT=development."""
import sys

from sqlalchemy import select

from app.core.config import get_settings
from app.core.security import hash_password
from app.database.session import get_sessionmaker
from app.models.user import Role, User


def main() -> int:
    s = get_settings()
    if s.environment != "development":
        print("seed_dev refuses to run outside ENVIRONMENT=development", file=sys.stderr)
        return 1
    accounts = [
        (s.seed_admin_email, s.seed_admin_password, "Admin User", Role.ADMIN),
        (s.seed_traveler_email, s.seed_traveler_password, "Priya Sharma", Role.TRAVELER),
    ]
    with get_sessionmaker()() as db:
        for email, password, name, role in accounts:
            if not email or not password:
                print(f"skipping {role.value}: SEED_* variables not set")
                continue
            if db.scalar(select(User).where(User.email == email.lower())):
                print(f"exists:  {email}")
                continue
            db.add(User(email=email.lower(), full_name=name, role=role,
                        password_hash=hash_password(password)))
            print(f"created: {email} ({role.value})")
        db.commit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
