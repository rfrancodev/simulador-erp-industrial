"""Dashboard router — serves HTML pages and analytics API endpoints."""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.analytics.service import AnalyticsService
from app.database.connection import session_dependency
from app.security.dependencies import require_api_access

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])
api_router = APIRouter(
    prefix="/api/dashboard",
    tags=["Dashboard API"],
    dependencies=[Depends(require_api_access)],
)

templates = Jinja2Templates(directory="templates")


def _analytics(session: Session = Depends(session_dependency)) -> AnalyticsService:
    return AnalyticsService(session)


# ── HTML Pages ───────────────────────────────────────────────────────────

@router.get("/", response_class=HTMLResponse)
async def dashboard_home(
    request: Request, analytics: AnalyticsService = Depends(_analytics)
):
    return templates.TemplateResponse(
        request=request,
        name="dashboard/home.html",
        context={
            "kpis": analytics.executive_kpis(),
            "order_dist": analytics.order_status_distribution(),
            "inspection_dist": analytics.inspection_status_distribution(),
            "cost_variance": analytics.cost_variance_by_order(),
        },
    )


@router.get("/order-360", response_class=HTMLResponse)
async def dashboard_order_360(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="dashboard/order_360.html",
    )


# ── Data API Endpoints ────────────────────────────────────────────────────

@api_router.get("/kpis")
def get_kpis(analytics: AnalyticsService = Depends(_analytics)):
    return analytics.executive_kpis()


@api_router.get("/order-360/{order_number}")
def get_order_360(order_number: str, analytics: AnalyticsService = Depends(_analytics)):
    from app.core.exceptions import EntityNotFoundError

    data = analytics.order_360(order_number)
    if data is None:
        raise EntityNotFoundError("ProductionOrder", order_number)
    return data


@api_router.get("/production-stats")
def get_production_stats(analytics: AnalyticsService = Depends(_analytics)):
    return analytics.production_stats()


@api_router.get("/quality-stats")
def get_quality_stats(analytics: AnalyticsService = Depends(_analytics)):
    return analytics.quality_stats()


@api_router.get("/cost-stats")
def get_cost_stats(analytics: AnalyticsService = Depends(_analytics)):
    return analytics.cost_stats()
