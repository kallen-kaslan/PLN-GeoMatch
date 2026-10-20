from sqlalchemy import Column, String, Enum, Boolean
from app.database import Base
import enum

class UserRole(str, enum.Enum):
    ADMIN = "admin"
    ANALIS = "analis"
    AUDITOR = "auditor"

class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(Enum(UserRole), default=UserRole.ANALIS)
    is_active = Column(Boolean, default=True)
