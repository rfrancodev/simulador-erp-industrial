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
            "active_nav": "home",
            "kpis": analytics.executive_kpis(),
            "order_dist": analytics.order_status_distribution(),
            "inspection_dist": analytics.inspection_status_distribution(),
            "cost_variance": analytics.cost_variance_by_order(),
            "monthly_trend": analytics.monthly_trend(),
        },
    )


@router.get("/production", response_class=HTMLResponse)
async def dashboard_production(
    request: Request, analytics: AnalyticsService = Depends(_analytics)
):
    return templates.TemplateResponse(
        request=request,
        name="dashboard/production.html",
        context={
            "active_nav": "production",
            "kpis": analytics.executive_kpis(),
            "stats": analytics.production_stats(),
        },
    )


@router.get("/quality", response_class=HTMLResponse)
async def dashboard_quality(
    request: Request, analytics: AnalyticsService = Depends(_analytics)
):
    return templates.TemplateResponse(
        request=request,
        name="dashboard/quality.html",
        context={
            "active_nav": "quality",
            "kpis": analytics.executive_kpis(),
            "stats": analytics.quality_stats(),
        },
    )


@router.get("/costing", response_class=HTMLResponse)
async def dashboard_costing(
    request: Request, analytics: AnalyticsService = Depends(_analytics)
):
    return templates.TemplateResponse(
        request=request,
        name="dashboard/costing.html",
        context={
            "active_nav": "cost",
            "kpis": analytics.executive_kpis(),
            "stats": analytics.cost_stats(),
        },
    )


@router.get("/order-360", response_class=HTMLResponse)
async def dashboard_order_360(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="dashboard/order_360.html",
        context={"active_nav": "order360"},
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


@api_router.get("/monthly-trend")
def get_monthly_trend(analytics: AnalyticsService = Depends(_analytics)):
    return analytics.monthly_trend()
