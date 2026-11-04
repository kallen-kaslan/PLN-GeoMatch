"""Password verification, revocable cookies, and administrator-only accounts."""

import secrets
from datetime import timedelta
from uuid import uuid4

from app.config import settings
from app.models.auth import AuthAudit, AuthSession, AuthThrottle, utcnow
from app.models.user import User, UserRole
from app.modules.auth.schemas import (
    ChangePassword,
    CreateUser,
    LoginRequest,
    UpdateUser,
)
from app.modules.auth.security import (
    AdminUser,
    CurrentUser,
    DbSession,
    audit,
    cookie_name,
    digest,
    dummy_hash,
    hash_password,
    hasher,
    lock_admins,
    password_valid,
    require_origin,
    throttle,
    validate_password,
)
from fastapi import APIRouter, HTTPException, Request, Response
from sqlalchemy import delete, or_
from sqlalchemy.exc import IntegrityError

router = APIRouter(prefix="/auth", tags=["Authentication"])
admin_router = APIRouter(prefix="/admin/users", tags=["User Administration"])


def user_info(user) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "role": user.role.value,
        "is_active": bool(getattr(user, "is_active", True)),
    }


def clear_cookies(response: Response) -> None:
    for csrf in (False, True):
        response.delete_cookie(
            cookie_name(csrf),
            path="/",
            secure=settings.AUTH_COOKIE_SECURE,
            httponly=not csrf,
            samesite="lax",
        )


@router.post("/login")
def login(
    req: LoginRequest, request: Request, response: Response, db: DbSession
) -> dict:
    require_origin(request)
    # A custom header and JSON prevent browser form-based login CSRF.
    if request.headers.get("x-requested-with") != "PLN-GeoMatch":
        raise HTTPException(403, "Header keamanan login tidak tersedia")
    username = req.username.strip().lower()
    throttle(db, request, username)
    user = db.query(User).filter(User.username == username).first()
    valid = password_valid(req.password, user.hashed_password if user else dummy_hash)
    if valid and user is not None:
        verified_hash = user.hashed_password
        lock_admins(db)
        db.refresh(user)
        valid = user.hashed_password == verified_hash
    if not valid or user is None or not user.is_active:
        audit(db, request, "login_failed", username=username)
        db.commit()
        raise HTTPException(401, "Username atau password salah")
    if hasher.check_needs_rehash(user.hashed_password):
        user.hashed_password = hash_password(req.password)
    now = utcnow()
    # Rotate the current browser's session and remove expired credentials.
    old_token = request.cookies.get(cookie_name(), "")
    db.execute(
        delete(AuthSession).where(
            or_(
                AuthSession.token_hash == digest(old_token),
                AuthSession.expires_at <= now,
                AuthSession.last_seen_at
                <= now - timedelta(minutes=settings.AUTH_IDLE_MINUTES),
            )
        )
    )
    token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    db.add(
        AuthSession(
            token_hash=digest(token),
            user_id=user.id,
            csrf_hash=digest(csrf),
            created_at=now,
            last_seen_at=now,
            expires_at=now + timedelta(hours=settings.AUTH_ABSOLUTE_HOURS),
        )
    )
    db.execute(
        delete(AuthThrottle).where(AuthThrottle.bucket == digest("account:" + username))
    )
    audit(db, request, "login_success", actor_id=user.id)
    payload = user_info(user)
    db.commit()
    for name, value, httponly in (
        (cookie_name(), token, True),
        (cookie_name(True), csrf, False),
    ):
        response.set_cookie(
            name,
            value,
            path="/",
            secure=settings.AUTH_COOKIE_SECURE,
            httponly=httponly,
            samesite="lax",
        )
    response.headers["Cache-Control"] = "no-store"
    return payload


@router.get("/me")
def me(user: CurrentUser) -> dict:
    return user_info(user)


@router.post("/logout", status_code=204)
def logout(
    request: Request, response: Response, user: CurrentUser, db: DbSession
) -> None:
    db.execute(delete(AuthSession).where(AuthSession.token_hash == user.session_hash))
    audit(db, request, "logout", actor_id=user.id)
    db.commit()
    clear_cookies(response)


@router.post("/password", status_code=204)
def change_password(
    req: ChangePassword,
    request: Request,
    response: Response,
    user: CurrentUser,
    db: DbSession,
) -> None:
    throttle(db, request, "password:" + user.id)
    lock_admins(db)
    account = db.get(User, user.id)
    db.refresh(account)
    if not account.is_active or db.get(AuthSession, user.session_hash) is None:
        raise HTTPException(401, "Sesi sudah tidak berlaku")
    if not password_valid(req.current_password, account.hashed_password):
        audit(db, request, "password_change_failed", actor_id=user.id)
        db.commit()
        raise HTTPException(400, "Password saat ini tidak sesuai")
    ensure_password(req.new_password, account.username)
    if password_valid(req.new_password, account.hashed_password):
        raise HTTPException(422, "Password baru harus berbeda dari password saat ini")
    account.hashed_password = hash_password(req.new_password)
    db.execute(delete(AuthSession).where(AuthSession.user_id == user.id))
    audit(db, request, "password_changed", actor_id=user.id)
    db.commit()
    clear_cookies(response)


def verify_admin(db: DbSession, request: Request, admin, password: str) -> None:
    throttle(db, request, "admin:" + admin.id)
    account = db.get(User, admin.id)
    verified_hash = account.hashed_password
    if not password_valid(password, account.hashed_password):
        audit(db, request, "admin_verification_failed", actor_id=admin.id)
        db.commit()
        raise HTTPException(403, "Password admin tidak sesuai")
    lock_admins(db)
    # Recheck after acquiring the management lock: another admin may have revoked access.
    db.refresh(account)
    if (
        not account.is_active
        or account.role != UserRole.ADMIN
        or account.hashed_password != verified_hash
        or db.get(AuthSession, admin.session_hash) is None
    ):
        raise HTTPException(401, "Sesi admin sudah tidak berlaku")
    db.execute(
        delete(AuthThrottle).where(
            AuthThrottle.bucket == digest("account:admin:" + admin.id)
        )
    )


def ensure_password(password: str, username: str) -> None:
    try:
        validate_password(password, username)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@admin_router.get("")
def list_users(admin: AdminUser, db: DbSession) -> list[dict]:
    return [user_info(user) for user in db.query(User).order_by(User.username).all()]


@admin_router.post("", status_code=201)
def create_user(
    req: CreateUser, request: Request, admin: AdminUser, db: DbSession
) -> dict:
    verify_admin(db, request, admin, req.admin_password)
    ensure_password(req.password, req.username)
    if db.query(User).filter(User.username == req.username).first():
        raise HTTPException(409, "Username sudah digunakan")
    user = User(
        id=str(uuid4()),
        username=req.username,
        hashed_password=hash_password(req.password),
        role=req.role,
        is_active=True,
    )
    db.add(user)
    db.flush()
    audit(
        db,
        request,
        "user_created",
        actor_id=admin.id,
        subject_id=user.id,
        role=req.role.value,
    )
    payload = user_info(user)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "Username sudah digunakan") from exc
    return payload


@admin_router.patch("/{user_id}")
def update_user(
    user_id: str, req: UpdateUser, request: Request, admin: AdminUser, db: DbSession
) -> dict:
    verify_admin(db, request, admin, req.admin_password)
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(404, "Pengguna tidak ditemukan")
    if user.id == admin.id:
        raise HTTPException(
            403,
            "Gunakan menu Ubah password untuk akun sendiri. Role dan status akun sendiri tidak dapat diubah",
        )
    before = {"role": user.role.value, "is_active": user.is_active}
    user.role, user.is_active = req.role, req.is_active
    if req.password is not None:
        ensure_password(req.password, user.username)
        user.hashed_password = hash_password(req.password)
    # Every change revokes all sessions, including role changes and reactivation.
    db.execute(delete(AuthSession).where(AuthSession.user_id == user.id))
    audit(
        db,
        request,
        "user_updated",
        actor_id=admin.id,
        subject_id=user.id,
        before=before,
        after={"role": user.role.value, "is_active": user.is_active},
        password_reset=req.password is not None,
    )
    payload = user_info(user)
    db.commit()
    return payload


@admin_router.get("/audit")
def security_audit(admin: AdminUser, db: DbSession) -> list[dict]:
    return [
        {
            "id": event.id,
            "actor_id": event.actor_id,
            "action": event.action,
            "subject_id": event.subject_id,
            "created_at": event.created_at,
            "ip_address": event.ip_address,
            "details": event.details,
        }
        for event in db.query(AuthAudit).order_by(AuthAudit.id.desc()).limit(100).all()
    ]
