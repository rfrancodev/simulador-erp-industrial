"""Industrial ERP Simulator — API endpoints."""

from fastapi import FastAPI

from app.core.logging import setup_logging

setup_logging()

app = FastAPI(
    title="Industrial ERP Simulator",
    description="Integrated PP-PI, QM & CO Process Simulation — inspired by SAP S/4HANA concepts.",
    version="0.1.0",
)


@app.get("/health")
async def health():
    return {"status": "ok"}
