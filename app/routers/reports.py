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
    Dataset ownership is validated — you can only report on YOUR datasets.
"""

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

# Adjust these imports to match your actual import paths
from app.database import get_db
from app.models.dataset import Dataset               # your SQLAlchemy Dataset model
from app.models.user import User                     # your SQLAlchemy User model
from app.services.auth_service import get_current_user   # your JWT dependency
from app.services.report_service import generate_full_report, generate_executive_summary
from app.services.kpi_service import compute_kpis
from app.schemas.report import KPIReport, ExecutiveSummary, FullReport

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
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()

    if not dataset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataset {dataset_id} not found.",
        )

    # Ownership check — users should only see their own data
    if dataset.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this dataset.",
        )

    try:
        df = pd.read_csv(dataset.file_path)
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
def get_kpis(
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
    kpis = compute_kpis(df)

    return KPIReport(
        dataset_id=dataset.id,
        filename=dataset.filename,
        kpis=kpis,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Endpoint 2: Executive Summary only
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/{dataset_id}/summary", response_model=ExecutiveSummary)
def get_executive_summary(
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
    kpis = compute_kpis(df)
    summary = generate_executive_summary(dataset.id, dataset.filename, kpis)

    return summary


# ─────────────────────────────────────────────────────────────────────────────
# Endpoint 3: Full Report (KPIs + Summary + Chart links)
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/{dataset_id}", response_model=FullReport)
def get_full_report(
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
    report = generate_full_report(dataset.id, dataset.filename, df)

    return report