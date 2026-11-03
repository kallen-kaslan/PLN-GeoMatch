from fastapi import APIRouter

router = APIRouter(prefix="/auth", tags=["Authentication"])

# Deprecated: Frontend now uses Supabase Auth directly.
# Backend verifies tokens in app/auth.py.
