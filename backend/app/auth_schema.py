"""Add authentication without rewriting the large source tables."""

from app.models.auth import AuthAudit, AuthGuard, AuthSession, AuthThrottle
from app.models.user import User
from sqlalchemy import select
from sqlalchemy.engine import Connection


def upgrade_auth(connection: Connection) -> None:
    for model in (User, AuthSession, AuthThrottle, AuthGuard, AuthAudit):
        model.__table__.create(connection, checkfirst=True)
    table = AuthGuard.__table__
    if connection.execute(select(table.c.id).where(table.c.id == 1)).first() is None:
        connection.execute(table.insert().values(id=1, revision=0))
