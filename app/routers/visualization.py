# WHY THIS FILE EXISTS:
# Routers are the HTTP layer. They do three things only:
#   1. Define the URL and HTTP method
#   2. Extract and validate inputs (path params, body, current user)
#   3. Call the service and return the result
# No business logic here — that all lives in visualization_service.py

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.auth_service import get_current_user   # reuse your existing auth dependency
from app.models.user import User
from app.schemas.visualization import (
    BarChartRequest,
    LineChartRequest,
    PieChartRequest,
    ScatterChartRequest,
    DashboardRequest,
    ChartResponse,
)
from app.services import visualization_service

router = APIRouter(
    prefix="/datasets",
    tags=["Visualizations"]   # groups endpoints under "Visualizations" in Swagger
)


@router.post(
    "/{dataset_id}/charts/bar",
    response_model=ChartResponse,
    summary="Bar Chart — Top N categories by value"
)
def bar_chart(
    dataset_id: int,
    request: BarChartRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Returns a Plotly bar chart JSON for the specified dataset.
    
    The client renders it with: Plotly.react(div, JSON.parse(chart_json))
    """
    return visualization_service.build_bar_chart(
        dataset_id, current_user.id, request, db
    )


@router.post(
    "/{dataset_id}/charts/line",
    response_model=ChartResponse,
    summary="Line Chart — Value trend over time"
)
def line_chart(
    dataset_id: int,
    request: LineChartRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return visualization_service.build_line_chart(
        dataset_id, current_user.id, request, db
    )


@router.post(
    "/{dataset_id}/charts/pie",
    response_model=ChartResponse,
    summary="Pie / Donut Chart — Category distribution"
)
def pie_chart(
    dataset_id: int,
    request: PieChartRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return visualization_service.build_pie_chart(
        dataset_id, current_user.id, request, db
    )


@router.post(
    "/{dataset_id}/charts/scatter",
    response_model=ChartResponse,
    summary="Scatter Plot — Correlation between two numeric columns"
)
def scatter_chart(
    dataset_id: int,
    request: ScatterChartRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return visualization_service.build_scatter_chart(
        dataset_id, current_user.id, request, db
    )


@router.post(
    "/{dataset_id}/charts/dashboard",
    response_model=ChartResponse,
    summary="Executive Dashboard — Combined multi-chart view"
)
def dashboard(
    dataset_id: int,
    request: DashboardRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Returns a single Plotly figure containing bar + pie + (optional) line charts.
    One API call → full dashboard. Render with Plotly.react().
    """
    return visualization_service.build_dashboard(
        dataset_id, current_user.id, request, db
    )