"""Server-side authorization; the browser never supplies a trusted identity or role."""

import hashlib
import re
import secrets
from dataclasses import dataclass
from datetime import timedelta
from threading import BoundedSemaphore
from typing import Annotated

from app.config import settings
from app.database import get_db
from app.models.auth import AuthAudit, AuthGuard, AuthSession, AuthThrottle, utcnow
from app.models.user import User, UserRole
from app.sqlite_runtime import sqlite_busy
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import Depends, HTTPException, Request
from sqlalchemy import case, delete, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

DbSession = Annotated[Session, Depends(get_db)]
hasher = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=1)
password_slots = BoundedSemaphore(4)
dummy_hash = hasher.hash(secrets.token_urlsafe(32))
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


@dataclass(frozen=True)
class Principal:
    id: str
    username: str
    role: UserRole
    session_hash: str


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def cookie_name(csrf: bool = False) -> str:
    return ("__Host-" if settings.AUTH_COOKIE_SECURE else "") + (
        "geomatch_csrf" if csrf else "geomatch_session"
    )


def password_valid(password: str, encoded: str) -> bool:
    try:
        with password_slots:
            return hasher.verify(encoded, password)
    except (VerificationError, InvalidHashError):
        return False


def hash_password(password: str) -> str:
    with password_slots:
        return hasher.hash(password)


def validate_password(password: str, username: str = "") -> str:
    if not 15 <= len(password) <= 128:
        raise ValueError("Password harus terdiri dari 15 sampai 128 karakter")
    compact = password.casefold().strip()
    weak = {
        "password",
        "password123456789",
        "123456789012345",
        "qwertyuiopasdfgh",
        "admin1234567890",
        "petugas123456789",
    }
    if (
        compact in weak
        or len(set(compact)) < 5
        or compact.isdecimal()
        or (username and compact == username.casefold())
    ):
        raise ValueError("Gunakan passphrase yang lebih sulit ditebak")
    return password


def normalize_username(value: str) -> str:
    value = value.strip().lower()
    if not re.fullmatch(r"[a-z0-9][a-z0-9._-]{2,63}", value):
        raise ValueError(
            "Username harus 3–64 karakter: huruf, angka, titik, garis bawah, atau tanda minus"
        )
    return value


def audit(
    db: Session,
    request: Request | None,
    action: str,
    actor_id: str | None = None,
    subject_id: str | None = None,
    **details,
) -> None:
    db.add(
        AuthAudit(
            action=action,
            actor_id=actor_id,
            subject_id=subject_id,
            ip_address=(request.client.host[:64] if request and request.client else ""),
            details=details,
        )
    )


def throttle(db: Session, request: Request, identity: str) -> None:
    """Atomic buckets shared by workers, including concurrent failed attempts."""
    now = utcnow()
    cutoff = now - timedelta(minutes=15)
    insert = sqlite_insert if db.bind.dialect.name == "sqlite" else pg_insert
    ip = request.client.host if request.client else "unknown"
    limited = False
    for label, limit in (
        ("ip:" + ip, settings.AUTH_LOGIN_IP_LIMIT),
        ("account:" + identity, settings.AUTH_LOGIN_ACCOUNT_LIMIT),
    ):
        stmt = insert(AuthThrottle).values(
            bucket=digest(label), started_at=now, attempts=1
        )
        expired = AuthThrottle.started_at <= cutoff
        stmt = stmt.on_conflict_do_update(
            index_elements=[AuthThrottle.bucket],
            set_={
                "started_at": case((expired, now), else_=AuthThrottle.started_at),
                "attempts": case((expired, 1), else_=AuthThrottle.attempts + 1),
            },
        ).returning(AuthThrottle.attempts)
        limited |= db.execute(stmt).scalar_one() > limit
        if limited:
            break
    # Bound table growth from random usernames and release locks before Argon2.
    db.execute(
        delete(AuthThrottle).where(AuthThrottle.started_at < now - timedelta(days=1))
    )
    db.commit()
    if limited:
        raise HTTPException(
            429,
            "Terlalu banyak percobaan. Coba kembali setelah 15 menit.",
            headers={"Retry-After": "900"},
        )


def lock_admins(db: Session) -> None:
    """Serialize bootstrap and admin changes, including the last active admin."""
    result = db.execute(
        update(AuthGuard)
        .where(AuthGuard.id == 1)
        .values(revision=AuthGuard.revision + 1)
    )
    if result.rowcount != 1:
        raise HTTPException(503, "Skema autentikasi belum siap")


def require_origin(request: Request) -> None:
    origin = request.headers.get("origin")
    if origin and origin not in settings.CORS_ALLOWED_ORIGINS:
        raise HTTPException(403, "Origin permintaan tidak diizinkan")
    if request.headers.get("sec-fetch-site") == "cross-site":
        raise HTTPException(403, "Permintaan lintas situs tidak diizinkan")


def touch_session(db: Session, token_hash: str, now) -> None:
    statement = (
        update(AuthSession)
        .where(
            AuthSession.token_hash == token_hash,
            AuthSession.last_seen_at <= now - timedelta(seconds=60),
        )
        .values(last_seen_at=now)
    )
    bind = db.get_bind()
    if bind.dialect.name != "sqlite":
        db.execute(statement)
        db.commit()
        return
    # A long atomic import holds SQLite's only write lock. Progress reads and
    # pause requests must remain responsive; retry the heartbeat next request.
    with bind.connect() as connection:
        previous_timeout = connection.exec_driver_sql(
            "PRAGMA busy_timeout"
        ).scalar_one()
        try:
            connection.exec_driver_sql("PRAGMA busy_timeout=0")
            connection.execute(statement)
            connection.commit()
        except OperationalError as exc:
            connection.rollback()
            if not sqlite_busy(exc):
                raise
        finally:
            connection.exec_driver_sql(f"PRAGMA busy_timeout={int(previous_timeout)}")
            connection.commit()


def require_access(request: Request, db: DbSession) -> Principal | None:
    path = request.url.path.rstrip("/") or "/"
    if (request.method, path) in {
        ("GET", "/"),
        ("GET", "/health"),
        ("POST", "/auth/login"),
    }:
        return None
    cached = getattr(request.state, "principal", None)
    if cached:
        return cached
    token = request.cookies.get(cookie_name(), "")
    if not re.fullmatch(r"[A-Za-z0-9_-]{43}", token):
        raise HTTPException(401, "Silakan login untuk melanjutkan")
    session = db.get(AuthSession, digest(token))
    now = utcnow()
    if (
        session is None
        or session.expires_at <= now
        or session.last_seen_at <= now - timedelta(minutes=settings.AUTH_IDLE_MINUTES)
    ):
        raise HTTPException(401, "Sesi telah berakhir. Silakan login kembali")
    user = db.get(User, session.user_id)
    if user is None or not user.is_active:
        raise HTTPException(401, "Sesi tidak berlaku. Silakan login kembali")
    if request.method not in SAFE_METHODS:
        require_origin(request)
        csrf = request.headers.get("x-csrf-token", "")
        if (
            not csrf
            or len(csrf) > 128
            or not secrets.compare_digest(digest(csrf), session.csrf_hash)
        ):
            raise HTTPException(403, "Token keamanan tidak sesuai. Muat ulang halaman")
        if user.role == UserRole.AUDITOR and path not in {
            "/auth/logout",
            "/auth/password",
        }:
            raise HTTPException(403, "Auditor hanya memiliki izin membaca data")
    if path.startswith("/admin/") and user.role != UserRole.ADMIN:
        raise HTTPException(403, "Hanya admin yang dapat mengelola pengguna")
    if request.method == "DELETE" and user.role != UserRole.ADMIN:
        raise HTTPException(403, "Hanya admin yang dapat menghapus data")
    if path in {"/upload/reset", "/upload/seed-dummy"}:
        if not settings.ALLOW_TEST_DATA_TOOLS:
            raise HTTPException(403, "Alat data uji dinonaktifkan")
        if user.role != UserRole.ADMIN:
            raise HTTPException(403, "Hanya admin yang dapat menjalankan alat data uji")
    principal = Principal(user.id, user.username, user.role, session.token_hash)
    should_touch = session.last_seen_at <= now - timedelta(seconds=60)
    # Release the auth read before the endpoint opens its own transaction. In
    # particular, never reserve two pooled connections while updating a session.
    db.rollback()
    if should_touch:
        touch_session(db, principal.session_hash, now)
    request.state.principal = principal
    return principal


def current_user(
    principal: Annotated[Principal | None, Depends(require_access)],
) -> Principal:
    if principal is None:
        raise HTTPException(401, "Silakan login untuk melanjutkan")
    return principal


def current_actor(principal: Annotated[Principal, Depends(current_user)]) -> str:
    return principal.username


CurrentUser = Annotated[Principal, Depends(current_user)]
CurrentActor = Annotated[str, Depends(current_actor)]


def require_admin(principal: CurrentUser) -> Principal:
    if principal.role != UserRole.ADMIN:
        raise HTTPException(403, "Hanya admin yang dapat mengelola pengguna")
    return principal


AdminUser = Annotated[Principal, Depends(require_admin)]
