"""
Reports Router — Build Day 10
------------------------------
Three endpoints:
    GET /report/{dataset_id}/kpis       → raw KPI numbers only
    GET /report/{dataset_id}/summary    → executive narrative only
    GET /report/{dataset_id}            → full combined report

WHY THREE SEPARATE ENDPOINTS?
    Different consumers need different things:
    - A dashboard widget needs just KPIs (fast, lightweight)
    - A Slack bot needs just the summary text
    - A PDF export needs the full report

    This mirrors how real analytics APIs work (e.g. Mixpanel, Amplitude).
    One God endpoint that returns everything is an anti-pattern in production.

AUTHENTICATION:
    All endpoints are protected with JWT (from Day 6).
    The current_user dependency injects the logged-in user.
    Workspace access is validated (Day 16) — you can only report on
    datasets in a workspace you belong to.
"""

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

# Adjust these imports to match your actual import paths
from app.database import get_db
from app.models.dataset import Dataset               # your SQLAlchemy Dataset model
from app.models.user import User                     # your SQLAlchemy User model
from app.rate_limiter import limiter
from app.services.access_control import require_dataset_access
from app.services.auth_service import get_current_user   # your JWT dependency
from app.services.job_service import record_job_owner
from app.services.storage_service import load_dataframe
from app.services.report_service import get_cached_executive_summary, get_cached_full_report, get_cached_kpis
from app.schemas.export import ReportExportRequest
from app.schemas.jobs import JobSubmitResponse
from app.schemas.report import KPIReport, ExecutiveSummary, FullReport
from app.tasks.export_tasks import export_report_task

router = APIRouter(prefix="/report", tags=["Reporting"])


# ─────────────────────────────────────────────────────────────────────────────
# Helper: load dataset + verify ownership + read CSV
# ─────────────────────────────────────────────────────────────────────────────

def _load_dataset_df(
    dataset_id: int,
    current_user: User,
    db: Session,
) -> tuple[Dataset, pd.DataFrame]:
    """
    Shared helper used by all three endpoints.

    Returns (dataset_record, dataframe) or raises HTTPException.

    WHY A HELPER FUNCTION?
        All three endpoints need the same three steps:
            1. Fetch from DB
            2. Verify ownership
            3. Read CSV into DataFrame
        DRY principle — define once, call three times.
    """
    dataset = require_dataset_access(db, dataset_id, current_user.id)

    try:
        df = load_dataframe(dataset.file_path)
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dataset file not found in storage.",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not read dataset file: {str(e)}",
        )

    return dataset, df


# ─────────────────────────────────────────────────────────────────────────────
# Endpoint 1: KPIs only
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/{dataset_id}/kpis", response_model=KPIReport)
@limiter.limit("100/hour")
def get_kpis(
    request: Request,
    response: Response,
    dataset_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Returns raw computed KPIs for a dataset.

    Fast endpoint — no narrative generation.
    Useful for dashboards that just need numbers.

    Example response:
        {
            "dataset_id": 1,
            "filename": "sales.csv",
            "kpis": {
                "total_records": 500,
                "total_value": 245000.0,
                "average_value": 490.0,
                "mom_growth_pct": 12.3,
                ...
            }
        }
    """
    dataset, df = _load_dataset_df(dataset_id, current_user, db)
    kpis = get_cached_kpis(dataset.id, df)

    return KPIReport(
        dataset_id=dataset.id,
        filename=dataset.filename,
        kpis=kpis,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Endpoint 2: Executive Summary only
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/{dataset_id}/summary", response_model=ExecutiveSummary)
@limiter.limit("100/hour")
def get_executive_summary(
    request: Request,
    response: Response,
    dataset_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Returns a plain-English executive summary with health score.

    Useful for:
    - Slack notifications
    - Email digests
    - Slide deck auto-generation (Day 14 will use LLM here)

    Example response:
        {
            "headline": "Revenue grew 12.3% month-over-month.",
            "summary_points": ["500 records...", "No duplicates...", ...],
            "health_score": 82.5,
            "health_label": "Healthy",
            "recommendation": "Set automated alerts for >15% deviation..."
        }
    """
    dataset, df = _load_dataset_df(dataset_id, current_user, db)
    kpis = get_cached_kpis(dataset.id, df)
    summary = get_cached_executive_summary(dataset.id, dataset.filename, kpis)

    return summary


# ─────────────────────────────────────────────────────────────────────────────
# Endpoint 3: Full Report (KPIs + Summary + Chart links)
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/{dataset_id}", response_model=FullReport)
@limiter.limit("100/hour")
def get_full_report(
    request: Request,
    response: Response,
    dataset_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    The flagship endpoint — returns the complete business report.

    Combines:
        - KPIs (from kpi_service)
        - Executive summary (from report_service)
        - Chart endpoint references (from Day 9 /visualize/ router)

    In a real company, this is what powers the "Generate Report" button.
    The frontend calls this once, gets everything, then lazy-loads charts
    by calling the chart_endpoints URLs separately.

    This is called "lazy loading" or "progressive rendering" — common
    pattern at analytics companies (Tableau, Looker, Metabase).
    """
    dataset, df = _load_dataset_df(dataset_id, current_user, db)
    report = get_cached_full_report(dataset.id, dataset.filename, df)

    return report


@router.post("/{dataset_id}/export", response_model=JobSubmitResponse, status_code=202)
def export_report(
    dataset_id: int,
    request: ReportExportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Exports the full KPI report as CSV/Excel/PDF. Async only — poll GET /jobs/{task_id}, then GET /exports/{export_id}."""
    require_dataset_access(db, dataset_id, current_user.id)

    task = export_report_task.delay(dataset_id, current_user.id, request.format)
    record_job_owner(task.id, current_user.id)
    return JobSubmitResponse(task_id=task.id)