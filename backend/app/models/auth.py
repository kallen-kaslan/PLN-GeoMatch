"""Revocable, hashed sessions and persistent authentication controls."""

from datetime import UTC, datetime

from app.database import Base
from sqlalchemy import JSON, Column, DateTime, ForeignKey, Integer, String


def utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class AuthSession(Base):
    __tablename__ = "auth_sessions"
    token_hash = Column(String(64), primary_key=True)
    user_id = Column(
        String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    csrf_hash = Column(String(64), nullable=False)
    created_at = Column(DateTime, nullable=False, default=utcnow)
    last_seen_at = Column(DateTime, nullable=False, default=utcnow)
    expires_at = Column(DateTime, nullable=False, index=True)


class AuthThrottle(Base):
    __tablename__ = "auth_throttles"
    bucket = Column(String(64), primary_key=True)
    started_at = Column(DateTime, nullable=False)
    attempts = Column(Integer, nullable=False)


class AuthGuard(Base):
    __tablename__ = "auth_guard"
    id = Column(Integer, primary_key=True)
    revision = Column(Integer, nullable=False, default=0)


class AuthAudit(Base):
    __tablename__ = "auth_audit"
    id = Column(Integer, primary_key=True)
    actor_id = Column(
        String, ForeignKey("users.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    action = Column(String(64), nullable=False)
    subject_id = Column(String, nullable=True)
    ip_address = Column(String(64), nullable=False, default="")
    details = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime, nullable=False, default=utcnow, index=True)
