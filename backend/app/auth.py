import logging
from typing import Annotated, List

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from pydantic import BaseModel

from .config import settings

logger = logging.getLogger(__name__)

security = HTTPBearer()

class AuthUser(BaseModel):
    id: str
    email: str
    role: str

async def get_current_user(credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)]) -> AuthUser:
    token = credentials.credentials
    try:
        # PENTING: SUPABASE_JWT_SECRET harus di-set di backend/.env
        # Secret ini didapat dari Supabase Dashboard -> Settings -> API -> JWT Secret
        payload = jwt.decode(
            token,
            settings.SUPABASE_JWT_SECRET,
            algorithms=[settings.ALGORITHM],
            audience=settings.SUPABASE_JWT_AUDIENCE,
            issuer=f"{settings.SUPABASE_URL}/auth/v1"
        )

        user_id: str = payload.get("sub")
        email: str = payload.get("email", "")
        # Role diambil dari app_metadata (diset di Supabase)
        app_metadata = payload.get("app_metadata", {})
        role: str = str(app_metadata.get("role", "analis")).lower()

        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token tidak valid: sub missing",
            )

        return AuthUser(id=user_id, email=email, role=role)

    except JWTError as e:
        logger.error(f"JWT Validation Error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token tidak valid atau kadaluarsa",
            headers={"WWW-Authenticate": "Bearer"},
        )

def require_roles(allowed_roles: List[str]):
    normalized = [r.lower() for r in allowed_roles]
    async def role_checker(user: Annotated[AuthUser, Depends(get_current_user)]):
        if user.role.lower() not in normalized:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Akses ditolak. Membutuhkan salah satu role: {', '.join(allowed_roles)}",
            )
        return user
    return role_checker
