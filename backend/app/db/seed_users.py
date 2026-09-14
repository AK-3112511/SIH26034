"""Local-dev login accounts for dashboard / mobile checks.

These are NOT shipped in the web/mobile UI. Run from /backend:

    python -m app.db.seed_users
"""
from sqlalchemy.orm import Session

from app.core.security import get_password_hash
from app.db.session import SessionLocal
from app.models.enums import UserRole
from app.models.user import User

DEV_USERS = [
    {
        "username": "senior_priya",
        "email": "priya@legalmetrology.gov.in",
        "password": "SeniorSecret#1",
        "full_name": "Priya Sharma",
        "role": UserRole.SENIOR_LMO,
        "district": "Madurai",
    },
    {
        "username": "admin_rajesh",
        "email": "rajesh@legalmetrology.gov.in",
        "password": "AdminSecret#1",
        "full_name": "Rajesh V",
        "role": UserRole.ADMIN,
        "district": "Chennai",
    },
    {
        "username": "lmo_ramesh",
        "email": "ramesh@legalmetrology.gov.in",
        "password": "FieldSecret#1",
        "full_name": "Ramesh Kumar",
        "role": UserRole.FIELD_LMO,
        "district": "Coimbatore",
    },
]


def seed_dev_users(db: Session) -> list[str]:
    created_or_updated = []
    for spec in DEV_USERS:
        user = db.query(User).filter(User.username == spec["username"]).one_or_none()
        if user is None:
            user = User(
                username=spec["username"],
                email=spec["email"],
                hashed_password=get_password_hash(spec["password"]),
                full_name=spec["full_name"],
                role=spec["role"],
                district=spec["district"],
                is_active=True,
            )
            db.add(user)
            created_or_updated.append(f"created {spec['username']}")
        else:
            user.email = spec["email"]
            user.hashed_password = get_password_hash(spec["password"])
            user.full_name = spec["full_name"]
            user.role = spec["role"]
            user.district = spec["district"]
            user.is_active = True
            created_or_updated.append(f"updated {spec['username']}")
    db.commit()
    return created_or_updated


if __name__ == "__main__":
    session = SessionLocal()
    try:
        results = seed_dev_users(session)
        print("Dev users ready:")
        for line in results:
            print(f"  - {line}")
        print()
        print("Dashboard (allowed):  senior_priya / SeniorSecret#1")
        print("Dashboard (allowed):  admin_rajesh / AdminSecret#1")
        print("Dashboard (rejected): lmo_ramesh / FieldSecret#1")
    finally:
        session.close()
