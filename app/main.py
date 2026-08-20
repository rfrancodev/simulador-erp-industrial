"""Industrial ERP Simulator — API endpoints."""

from fastapi import Depends, FastAPI
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.auth import router as auth_router
from app.api.costing import router as costing_router
from app.api.dashboard import api_router as dashboard_api_router
from app.api.dashboard import auth_router as dashboard_auth_router
from app.api.dashboard import router as dashboard_router
from app.api.production import router as production_router
from app.api.quality import router as quality_router
from app.core.exceptions import (
    BatchNotCompletedError,
    ComponentUnitMismatchError,
    DatabaseIntegrityError,
    DomainError,
    DuplicateEntityError,
    EntityHasDependenciesError,
    EntityNotFoundError,
    InvalidStateTransitionError,
    RecipeMaterialMismatchError,
)
from app.core.logging import setup_logging
from app.database.connection import session_dependency
from app.middleware.rate_limit import RateLimitMiddleware
from app.security.dependencies import require_admin_access
from app.security.tokens import validate_secret_key
from app.services.integration import register_integration_handlers

setup_logging()
validate_secret_key()
register_integration_handlers()

app = FastAPI(
    title="Industrial ERP Simulator",
    description="Integrated PP-PI, QM & CO Process Simulation — inspired by SAP S/4HANA concepts.",
    version="0.1.0",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

app.add_middleware(RateLimitMiddleware)

app.include_router(auth_router)
app.include_router(production_router)
app.include_router(quality_router)
app.include_router(costing_router)
app.include_router(dashboard_auth_router)
app.include_router(dashboard_router)
app.include_router(dashboard_api_router)


# ── Global exception handlers ────────────────────────────────────────────

@app.exception_handler(EntityNotFoundError)
async def handle_not_found(request, exc: EntityNotFoundError):
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.exception_handler(DuplicateEntityError)
async def handle_duplicate(request, exc: DuplicateEntityError):
    return JSONResponse(status_code=409, content={"detail": str(exc)})


@app.exception_handler(DatabaseIntegrityError)
async def handle_database_integrity(request, exc: DatabaseIntegrityError):
    return JSONResponse(status_code=409, content={"detail": str(exc)})


@app.exception_handler(RecipeMaterialMismatchError)
async def handle_mismatch(request, exc: RecipeMaterialMismatchError):
    return JSONResponse(status_code=422, content={"detail": str(exc)})


@app.exception_handler(ComponentUnitMismatchError)
async def handle_unit_mismatch(request, exc: ComponentUnitMismatchError):
    return JSONResponse(status_code=422, content={"detail": str(exc)})


@app.exception_handler(EntityHasDependenciesError)
async def handle_dependencies(request, exc: EntityHasDependenciesError):
    return JSONResponse(status_code=409, content={"detail": str(exc)})


@app.exception_handler(InvalidStateTransitionError)
async def handle_invalid_transition(request, exc: InvalidStateTransitionError):
    return JSONResponse(status_code=409, content={"detail": str(exc)})


@app.exception_handler(BatchNotCompletedError)
async def handle_batch_not_completed(request, exc: BatchNotCompletedError):
    return JSONResponse(status_code=409, content={"detail": str(exc)})


@app.exception_handler(DomainError)
async def handle_domain_error(request, exc: DomainError):
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.get("/health")
async def health(session: Session = Depends(session_dependency)):
    try:
        session.execute(text("SELECT 1"))
        return {"status": "ok", "database": "connected"}
    except Exception:
        return JSONResponse(status_code=503, content={"status": "error", "database": "unavailable"})


# ── API documentation (admin-only) ────────────────────────────────────────
# FastAPI's default Swagger routes are disabled above; /docs and /openapi.json
# are re-registered here behind admin authentication so non-admin users cannot
# reach the API documentation.

@app.get("/docs", response_class=HTMLResponse, include_in_schema=False)
async def swagger_docs(_admin=Depends(require_admin_access)):
    return get_swagger_ui_html(
        openapi_url="/openapi.json",
        title="Industrial ERP Simulator — API Docs",
    )


@app.get("/openapi.json", include_in_schema=False)
async def openapi_schema(_admin=Depends(require_admin_access)):
    return app.openapi()
