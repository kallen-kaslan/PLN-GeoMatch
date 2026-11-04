"""One application factory with mandatory authentication for all business routers."""

from app.config import settings
from app.database_errors import register_database_error_handlers
from app.modules.auth.router import admin_router
from app.modules.auth.router import router as auth_router
from app.modules.auth.security import require_access
from app.modules.corrections.router import router as correction_router
from app.modules.history.router import router as history_router
from app.modules.master.router import router as master_router
from app.modules.pdpj.router import router as pdpj_router
from app.modules.spatial.router import router as spatial_router
from app.modules.upload.router import router as upload_router
from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse


def create_application() -> FastAPI:
    app = FastAPI(
        title="PLN GeoMatch API",
        version="1.0.0",
        dependencies=[Depends(require_access)],
        docs_url=None if settings.APP_ENV == "production" else "/docs",
        redoc_url=None,
        openapi_url=None if settings.APP_ENV == "production" else "/openapi.json",
    )
    register_database_error_handlers(app)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
        allow_headers=[
            "Content-Type",
            "X-CSRF-Token",
            "X-Requested-With",
            "X-Upload-Progress",
        ],
        expose_headers=["Content-Disposition"],
    )

    @app.middleware("http")
    async def response_security(request: Request, call_next):
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        if settings.APP_ENV == "production":
            response.headers["Strict-Transport-Security"] = "max-age=31536000"
        return response

    @app.exception_handler(RequestValidationError)
    async def safe_validation(request: Request, exc: RequestValidationError):
        # FastAPI otherwise echoes invalid password fields in validation responses.
        return JSONResponse(
            status_code=422,
            content={
                "detail": [
                    {"loc": error["loc"], "msg": error["msg"], "type": error["type"]}
                    for error in exc.errors()
                ]
            },
        )

    for router in (
        auth_router,
        admin_router,
        upload_router,
        spatial_router,
        history_router,
        master_router,
        pdpj_router,
        correction_router,
    ):
        app.include_router(router)

    @app.get("/")
    def root():
        return {"message": "Welcome to PLN GeoMatch API", "status": "online"}

    @app.get("/health")
    def health():
        return {"status": "ok"}

    return app
