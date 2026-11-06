"""Create the first admin locally; never expose a setup or registration endpoint."""

import argparse
import getpass
import sys
from uuid import uuid4

from app.auth_schema import upgrade_auth
from app.database import SessionLocal, engine
from app.models.user import User, UserRole
from app.modules.auth.security import (
    audit,
    hash_password,
    lock_admins,
    normalize_username,
    validate_password,
)


def create_initial_admin(db, username: str, password: str) -> None:
    username = normalize_username(username)
    validate_password(password, username)
    lock_admins(db)
    if (
        db.query(User)
        .filter(User.role == UserRole.ADMIN, User.is_active.is_(True))
        .first()
    ):
        raise ValueError(
            "Admin aktif sudah ada. Tambahkan pengguna melalui Manajemen Pengguna"
        )
    if db.query(User).filter(User.username == username).first():
        raise ValueError("Username sudah digunakan; bootstrap tidak menimpa akun lama")
    user = User(
        id=str(uuid4()),
        username=username,
        hashed_password=hash_password(password),
        role=UserRole.ADMIN,
        is_active=True,
    )
    db.add(user)
    db.flush()
    audit(db, None, "initial_admin_created", actor_id=user.id, subject_id=user.id)
    db.commit()


def main() -> None:
    parser = argparse.ArgumentParser(description="Buat admin pertama PLN GeoMatch")
    parser.add_argument("--username", required=True)
    parser.add_argument(
        "--password-stdin",
        action="store_true",
        help="Untuk otomasi aman; password tidak dimasukkan ke argumen",
    )
    args = parser.parse_args()
    password = (
        sys.stdin.readline().rstrip("\r\n")
        if args.password_stdin
        else getpass.getpass("Password admin (minimal 15 karakter): ")
    )
    if not args.password_stdin and password != getpass.getpass("Ulangi password: "):
        parser.exit(1, "Konfirmasi password tidak sama\n")
    with engine.begin() as connection:
        upgrade_auth(connection)
    with SessionLocal() as db:
        try:
            create_initial_admin(db, args.username, password)
        except ValueError as exc:
            db.rollback()
            parser.exit(1, str(exc) + "\n")
    print("Admin pertama berhasil dibuat. Silakan login melalui aplikasi.")


if __name__ == "__main__":
    main()
