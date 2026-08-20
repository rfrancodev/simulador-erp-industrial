"""Dashboard router — serves HTML pages and analytics API endpoints."""

import os

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.analytics.service import AnalyticsService
from app.database.connection import session_dependency
from app.security.dependencies import require_dashboard_access
from app.security.tokens import create_access_token, token_expiry_minutes
from app.services.auth_service import AuthService

router = APIRouter(
    prefix="/dashboard",
    tags=["Dashboard"],
    dependencies=[Depends(require_dashboard_access)],
)
auth_router = APIRouter(prefix="/dashboard", tags=["Dashboard Auth"])
api_router = APIRouter(
    prefix="/api/dashboard",
    tags=["Dashboard API"],
    dependencies=[Depends(require_dashboard_access)],
)

templates = Jinja2Templates(directory="templates")

_ACCESS_TOKEN_COOKIE = "access_token"


def _cookie_secure() -> bool:
    """Whether the auth cookie should be marked ``Secure``.

    The reverse proxy terminates TLS, so the app sees HTTP. Set
    ``COOKIE_SECURE=true`` in production (behind Cloudflare/HTTPS) so the
    HttpOnly auth cookie is only sent over HTTPS.
    """
    return os.getenv("COOKIE_SECURE", "false").lower() in ("1", "true", "yes")


def _analytics(session: Session = Depends(session_dependency)) -> AnalyticsService:
    return AnalyticsService(session)


def _auth(session: Session = Depends(session_dependency)) -> AuthService:
    return AuthService(session)


# ── Authentication pages ─────────────────────────────────────────────────

@auth_router.get("/login", response_class=HTMLResponse)
async def dashboard_login_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="dashboard/login.html",
        context={"error": None},
    )


@auth_router.post("/login")
async def dashboard_login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    svc: AuthService = Depends(_auth),
):
    try:
        user = svc.authenticate(username, password)
    except HTTPException:
        return templates.TemplateResponse(
            request=request,
            name="dashboard/login.html",
            context={"error": "Usuário ou senha inválidos."},
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    token = create_access_token(subject=user.username)
    response = RedirectResponse(url="/dashboard/", status_code=status.HTTP_303_SEE_OTHER)
    response.set_cookie(
        _ACCESS_TOKEN_COOKIE,
        token,
        httponly=True,
        secure=_cookie_secure(),
        samesite="lax",
        max_age=token_expiry_minutes() * 60,
    )
    return response


@auth_router.post("/logout")
async def dashboard_logout():
    response = RedirectResponse(url="/dashboard/login", status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie(_ACCESS_TOKEN_COOKIE)
    return response


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
    request: Request,
    analytics: AnalyticsService = Depends(_analytics),
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1, le=50),
):
    return templates.TemplateResponse(
        request=request,
        name="dashboard/production.html",
        context={
            "active_nav": "production",
            "kpis": analytics.executive_kpis(),
            "stats": analytics.production_stats(page=page, per_page=per_page),
            "page": page,
            "per_page": per_page,
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
