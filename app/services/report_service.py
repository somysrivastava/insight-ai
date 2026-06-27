"""
Report Service — Build Day 10
------------------------------
Orchestrates KPI computation → narrative generation → full report assembly.

DESIGN PATTERN: Orchestrator / Façade
    This service doesn't compute anything itself.
    It delegates to kpi_service, interprets the output,
    then assembles a FullReport.

    Real-world analogy:
        Stripe's /charge endpoint orchestrates:
            fraud_service → ledger_service → notification_service
        This is the same pattern, smaller scale.

RULE-BASED NARRATIVE (for now):
    On Day 14 you will replace generate_executive_summary() internals
    with an OpenAI call. The function signature and return type stay
    identical — which means reports.py (the router) changes ZERO lines.
"""

import pandas as pd
from datetime import datetime, timezone

from app.services.kpi_service import compute_kpis
from app.schemas.report import ExecutiveSummary, FullReport


# ─────────────────────────────────────────────────────────────────────────────
# Executive Summary Generator
# ─────────────────────────────────────────────────────────────────────────────

def generate_executive_summary(
    dataset_id: int,
    filename: str,
    kpis: dict,
) -> ExecutiveSummary:
    """
    Converts raw KPI numbers into a human-readable executive narrative.

    Health Score Formula (0–100):
        50 pts  → data completeness
        30 pts  → low duplicate rate
        20 pts  → MoM growth (bonus/penalty)
    """

    # ── Health Score ──────────────────────────────────────────────────────────
    completeness     = kpis.get("data_completeness_pct", 100.0)
    total_records    = kpis.get("total_records", 1)
    duplicates       = kpis.get("duplicate_records", 0)
    mom_growth       = kpis.get("mom_growth_pct", None)

    completeness_score = (completeness / 100) * 50

    dup_ratio  = duplicates / total_records if total_records > 0 else 0
    dup_score  = max(0.0, 30 - (dup_ratio * 100))  # lose points for high dup %

    growth_score = 0.0
    if mom_growth is not None:
        # +ve growth gives up to 20 bonus pts; -ve growth penalises up to -20
        growth_score = max(-20.0, min(20.0, float(mom_growth)))

    health_score = round(
        max(0.0, min(100.0, completeness_score + dup_score + growth_score)),
        1,
    )

    if health_score >= 75:
        health_label = "Healthy"
    elif health_score >= 50:
        health_label = "Moderate"
    else:
        health_label = "At Risk"

    # ── Headline ──────────────────────────────────────────────────────────────
    # Most important signal wins the headline slot
    if mom_growth is not None:
        direction = "grew" if mom_growth > 0 else "declined"
        headline = (
            f"Primary metric {direction} {abs(mom_growth):.1f}% month-over-month."
        )
    elif "total_value" in kpis:
        col = kpis.get("primary_metric_column", "value")
        headline = (
            f"Total {col} across {total_records:,} records: "
            f"{kpis['total_value']:,.2f}."
        )
    else:
        headline = (
            f"Dataset '{filename}' analysed: "
            f"{total_records:,} records, {completeness:.1f}% complete."
        )

    # ── Summary Points ────────────────────────────────────────────────────────
    points: list[str] = []

    points.append(
        f"{total_records:,} records across {kpis.get('total_columns', '?')} columns "
        f"with {completeness:.1f}% data completeness."
    )

    if duplicates > 0:
        points.append(
            f"{duplicates:,} duplicate records detected "
            f"({dup_ratio * 100:.1f}% of total) — consider deduplication."
        )
    else:
        points.append("No duplicate records found — data integrity is clean.")

    if "total_value" in kpis:
        col = kpis["primary_metric_column"]
        points.append(
            f"{col}: total {kpis['total_value']:,.2f} | "
            f"avg {kpis['average_value']:,.2f} | "
            f"median {kpis['median_value']:,.2f}."
        )

    if mom_growth is not None:
        arrow = "↑" if mom_growth > 0 else "↓"
        points.append(f"MoM change: {arrow} {mom_growth:+.1f}% on {kpis.get('primary_metric_column', 'primary metric')}.")

    if "date_range_start" in kpis:
        points.append(
            f"Reporting window: {kpis['date_range_start']} → "
            f"{kpis['date_range_end']} "
            f"({kpis.get('reporting_period_days', '?')} days)."
        )

    if "high_value_records" in kpis:
        points.append(
            f"{kpis['high_value_records']:,} high-value records "
            f"(≥ {kpis['high_value_threshold']:,.2f}) in top 25th percentile."
        )

    if "segment_count" in kpis:
        points.append(
            f"{kpis['segment_count']} distinct segments in "
            f"'{kpis.get('primary_segment_column', 'category')}'."
        )

    # ── Recommendation ────────────────────────────────────────────────────────
    if completeness < 90:
        recommendation = (
            "Data completeness is below 90%. "
            "Address missing values before presenting findings to leadership."
        )
    elif dup_ratio > 0.05:
        recommendation = (
            "Duplicate rate exceeds 5%. Run deduplication before reporting."
        )
    elif mom_growth is not None and mom_growth < -10:
        recommendation = (
            f"Primary metric dropped {abs(mom_growth):.1f}% MoM. "
            "Investigate root cause by segment before next review."
        )
    elif mom_growth is not None and mom_growth > 20:
        recommendation = (
            "Strong MoM growth detected. "
            "Identify the top-performing segment and scale what's working."
        )
    else:
        recommendation = (
            "Metrics are stable. "
            "Set automated alerts for >15% deviation on primary metric."
        )

    return ExecutiveSummary(
        dataset_id=dataset_id,
        filename=filename,
        headline=headline,
        summary_points=points,
        health_score=health_score,
        health_label=health_label,
        recommendation=recommendation,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Full Report Orchestrator
# ─────────────────────────────────────────────────────────────────────────────

def generate_full_report(
    dataset_id: int,
    filename: str,
    df: pd.DataFrame,
) -> FullReport:
    """
    Master function called by the router.

    Steps:
        1. compute_kpis(df)              → raw numbers
        2. generate_executive_summary()  → narrative interpretation
        3. assemble chart_endpoints      → references to Day 9 endpoints
        4. return FullReport
    """

    kpis    = compute_kpis(df)
    summary = generate_executive_summary(dataset_id, filename, kpis)

    # Chart endpoint paths — the frontend calls these to fetch Plotly JSON.
    # These reference your Day 9 /visualize/ router.
    chart_endpoints = {
        "bar_chart":  f"/visualize/{dataset_id}/bar",
        "line_chart": f"/visualize/{dataset_id}/line",
        "pie_chart":  f"/visualize/{dataset_id}/pie",
        "dashboard":  f"/visualize/{dataset_id}/dashboard",
    }

    return FullReport(
        dataset_id=dataset_id,
        filename=filename,
        kpis=kpis,
        executive_summary=summary,
        chart_endpoints=chart_endpoints,
        generated_at=datetime.now(timezone.utc).isoformat(),
    )