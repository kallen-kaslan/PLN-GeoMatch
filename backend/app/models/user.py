import enum

from sqlalchemy import Boolean, Column, Enum, String

from app.database import Base


class UserRole(str, enum.Enum):
    ADMIN = "admin"
    ANALIS = "analis"
    AUDITOR = "auditor"


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role: Column[UserRole] = Column(Enum(UserRole), default=UserRole.ANALIS)
    is_active = Column(Boolean, default=True)
