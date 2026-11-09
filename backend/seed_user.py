"""Seed user directly into backend database."""
import os
import sys

# Ensure backend root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from uuid import uuid4
from app.database import SessionLocal, engine
from app.auth_schema import upgrade_auth
from app.models.user import User, UserRole
from app.modules.auth.security import hash_password, normalize_username, validate_password

def seed_user(username: str, password: str, role: UserRole = UserRole.ADMIN):
    username = normalize_username(username)
    validate_password(password, username)

    # Ensure schema exists
    with engine.begin() as conn:
        upgrade_auth(conn)

    with SessionLocal() as db:
        user = db.query(User).filter(User.username == username).first()
        if user:
            print(f"[INFO] User '{username}' exists. Updating password & role...")
            user.hashed_password = hash_password(password)
            user.role = role
            user.is_active = True
        else:
            print(f"[INFO] Creating user '{username}' ({role.value})...")
            user = User(
                id=str(uuid4()),
                username=username,
                hashed_password=hash_password(password),
                role=role,
                is_active=True,
            )
            db.add(user)
        db.commit()
        print(f"[SUCCESS] User '{username}' ready with role '{role.value}'.")

if __name__ == "__main__":
    u = sys.argv[1] if len(sys.argv) > 1 else "admin"
    p = sys.argv[2] if len(sys.argv) > 2 else "AdminGeoMatch2026!#"
    r_str = sys.argv[3] if len(sys.argv) > 3 else "admin"
    r = UserRole(r_str)
    seed_user(u, p, r)
