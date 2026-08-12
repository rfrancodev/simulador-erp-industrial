"""Industrial ERP Simulator — API endpoints."""

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.api.production import router as production_router
from app.core.exceptions import (
    DomainError,
    DuplicateEntityError,
    EntityHasDependenciesError,
    EntityNotFoundError,
    RecipeMaterialMismatchError,
)
from app.core.logging import setup_logging

setup_logging()

app = FastAPI(
    title="Industrial ERP Simulator",
    description="Integrated PP-PI, QM & CO Process Simulation — inspired by SAP S/4HANA concepts.",
    version="0.1.0",
)

app.include_router(production_router)


# ── Global exception handlers ────────────────────────────────────────────

@app.exception_handler(EntityNotFoundError)
async def handle_not_found(request, exc: EntityNotFoundError):
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.exception_handler(DuplicateEntityError)
async def handle_duplicate(request, exc: DuplicateEntityError):
    return JSONResponse(status_code=409, content={"detail": str(exc)})


@app.exception_handler(RecipeMaterialMismatchError)
async def handle_mismatch(request, exc: RecipeMaterialMismatchError):
    return JSONResponse(status_code=422, content={"detail": str(exc)})


@app.exception_handler(EntityHasDependenciesError)
async def handle_dependencies(request, exc: EntityHasDependenciesError):
    return JSONResponse(status_code=409, content={"detail": str(exc)})


@app.exception_handler(DomainError)
async def handle_domain_error(request, exc: DomainError):
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.get("/health")
async def health():
    return {"status": "ok"}
