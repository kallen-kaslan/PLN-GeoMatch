"""Only administrator-controlled account creation; no public registration schema."""

from app.models.user import UserRole
from app.modules.auth.security import normalize_username, validate_password
from pydantic import BaseModel, ConfigDict, Field, field_validator


class StrictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)


class LoginRequest(StrictRequest):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)


class ChangePassword(StrictRequest):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str

    @field_validator("new_password")
    @classmethod
    def strong_password(cls, value: str) -> str:
        return validate_password(value)


class CreateUser(StrictRequest):
    username: str
    password: str
    role: UserRole = UserRole.ANALIS
    admin_password: str = Field(min_length=1, max_length=128)

    @field_validator("username")
    @classmethod
    def valid_username(cls, value: str) -> str:
        return normalize_username(value)

    @field_validator("password")
    @classmethod
    def strong_password(cls, value: str) -> str:
        return validate_password(value)


class UpdateUser(StrictRequest):
    role: UserRole
    is_active: bool
    password: str | None = None
    admin_password: str = Field(min_length=1, max_length=128)

    @field_validator("password")
    @classmethod
    def strong_password(cls, value: str | None) -> str | None:
        return validate_password(value) if value is not None else None
