"""FastAPI application factory."""

from __future__ import annotations

from datetime import datetime

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from . import __version__, fhir
from .api import cds_router, fhir_router, router, smart_router
from .config import Settings, get_settings
from .security import AccessDenied
from .state import AppState


def create_app(settings: Settings | None = None, *, now: datetime | None = None) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(title="Asclepius API", version=__version__, description="Synthetic-data healthcare IT platform: FHIR R4, SMART (mock), HL7 v2, ABDM (mock) and governed clinical AI. Not a medical device.",
                  docs_url="/api/docs", openapi_url="/api/openapi.json", redoc_url=None)
    app.state.asc = AppState(settings, now=now)
    app.add_middleware(CORSMiddleware, allow_origins=list(settings.cors_origins), allow_methods=["*"], allow_headers=["*"], allow_credentials=False)

    @app.exception_handler(AccessDenied)
    async def denied(request: Request, exc: AccessDenied) -> JSONResponse:
        if request.url.path.startswith("/fhir"):
            return JSONResponse(fhir.operation_outcome("error", "forbidden" if exc.status == 403 else "login" if exc.status == 401 else "invalid", exc.message), status_code=exc.status, media_type="application/fhir+json")
        return JSONResponse({"error": {"code": exc.code, "message": exc.message}}, status_code=exc.status)

    @app.middleware("http")
    async def headers(request: Request, call_next):  # type: ignore[no-untyped-def]
        resp = await call_next(request)
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["Referrer-Policy"] = "no-referrer"
        resp.headers["Cache-Control"] = resp.headers.get("Cache-Control", "no-store")
        resp.headers["X-Synthetic-Data"] = "true"
        return resp

    app.include_router(router, prefix="/api")
    app.include_router(fhir_router, prefix="/fhir")
    app.include_router(cds_router, prefix="/cds-services")
    app.include_router(smart_router)
    return app
