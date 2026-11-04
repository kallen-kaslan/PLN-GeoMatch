import json
import logging
import urllib.request
from typing import Annotated, Any, Dict, List

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from pydantic import BaseModel

from .config import settings

logger = logging.getLogger(__name__)

security = HTTPBearer()

_jwks_cache: Dict[str, Any] | None = None


def get_supabase_jwks() -> Dict[str, Any]:
    global _jwks_cache
    if _jwks_cache is not None:
        return _jwks_cache
    url = f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1/.well-known/jwks.json"
    req = urllib.request.Request(url, headers={"User-Agent": "PLN-GeoMatch-Backend"})
    with urllib.request.urlopen(req, timeout=5) as response:
        _jwks_cache = json.loads(response.read().decode("utf-8"))
    return _jwks_cache


class AuthUser(BaseModel):
    id: str
    email: str
    role: str


async def get_current_user(credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)]) -> AuthUser:
    token = credentials.credentials
    try:
        unverified_header = jwt.get_unverified_header(token)
        alg = unverified_header.get("alg", "HS256")
        kid = unverified_header.get("kid")

        # Asymmetric (RS256, ES256, dll) verifikasi lewat JWKS Supabase
        if alg != "HS256":
            jwks = get_supabase_jwks()
            key_dict = None
            for key in jwks.get("keys", []):
                if kid and key.get("kid") == kid:
                    key_dict = key
                    break
                if not kid and key.get("alg") == alg:
                    key_dict = key
                    break
            if not key_dict and jwks.get("keys"):
                key_dict = jwks["keys"][0]
            if not key_dict:
                raise JWTError(f"JWKS key matching alg={alg} kid={kid} not found")
            signing_key = key_dict
        else:
            # Symmetric HS256 verifikasi via SUPABASE_JWT_SECRET
            signing_key = settings.SUPABASE_JWT_SECRET

        payload = jwt.decode(
            token,
            signing_key,
            algorithms=[alg],
            audience=settings.SUPABASE_JWT_AUDIENCE,
            issuer=f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1",
        )

        user_id: str = payload.get("sub")
        email: str = payload.get("email", "")
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
    except Exception as e:
        logger.error(f"Auth Unexpected Error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Gagal memverifikasi token autentikasi",
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

require_admin = Depends(require_roles(["admin"]))
require_operator = Depends(require_roles(["admin", "analis"]))
require_viewer = Depends(require_roles(["admin", "analis", "auditor"]))

