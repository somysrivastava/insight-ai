# WHY THIS FILE EXISTS:
# Every exportable thing (an AI query answer, insights, trends, a
# breakdown, a join result, a full report) has a different raw shape.
# build_*_document() normalizes each into one small internal shape —
# title, generated_at, an optional answer/narrative, and either
# table_rows (a list of records) or summary_fields (a flat dict) — so
# the three renderers (CSV/Excel/PDF) each have to understand exactly
# one shape, not six. Adding a 7th exportable thing later means writing
# one new adapter, not touching three renderers.

import io
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import pandas as pd
from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML

from app.services.visualization_service import (
    ACCENT_COLOR,
    PRIMARY_COLOR,
    SECONDARY_COLOR,
    TEXT_COLOR,
)

_TEMPLATE_ENV = Environment(loader=FileSystemLoader(Path(__file__).parent.parent / "templates"))


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── ExportDocument builders ─────────────────────────────────────────────────
# Each returns: {title, generated_at, answer, table_rows, summary_fields, narrative}

def build_query_document(title: str, result: dict) -> dict:
    """Used for both a dataset AI-query result and a join AI-query result — identical shape."""
    data = result.get("data", {})
    table_rows = data.get("records")
    summary_fields = None
    if table_rows is None:
        summary_fields = {k: v for k, v in data.items() if k not in ("operation",)}
    return {
        "title": title,
        "generated_at": _now_iso(),
        "answer": result.get("answer"),
        "table_rows": table_rows,
        "summary_fields": summary_fields,
        "narrative": None,
    }


def build_insights_document(title: str, result: dict) -> dict:
    summary_stats = result.get("summary_stats", {})
    table_rows = [{"column": col, **stats} for col, stats in summary_stats.items()] or None
    summary_fields = dict(result.get("kpis", {}))
    summary_fields["total_rows"] = result.get("total_rows")
    summary_fields["total_columns"] = result.get("total_columns")
    return {
        "title": title,
        "generated_at": _now_iso(),
        "answer": None,
        "table_rows": table_rows,
        "summary_fields": summary_fields,
        "narrative": None,
    }


def build_trends_document(title: str, result: dict) -> dict:
    return {
        "title": title,
        "generated_at": _now_iso(),
        "answer": None,
        "table_rows": result.get("trends") or None,
        "summary_fields": {"date_column": result.get("date column")},
        "narrative": None,
    }


def build_breakdown_document(title: str, result: dict) -> dict:
    return {
        "title": title,
        "generated_at": _now_iso(),
        "answer": None,
        "table_rows": result.get("breakdown") or None,
        "summary_fields": {"group_by": result.get("group_by")},
        "narrative": None,
    }


def build_report_document(title: str, result: dict) -> dict:
    summary = result.get("executive_summary", {})
    return {
        "title": title,
        "generated_at": result.get("generated_at", _now_iso()),
        "answer": None,
        "table_rows": None,
        "summary_fields": dict(result.get("kpis", {})),
        "narrative": {
            "headline": summary.get("headline"),
            "summary_points": summary.get("summary_points", []),
            "health_score": summary.get("health_score"),
            "health_label": summary.get("health_label"),
            "recommendation": summary.get("recommendation"),
        },
    }


# ── Renderers ────────────────────────────────────────────────────────────────

def _document_to_dataframe(doc: dict) -> pd.DataFrame:
    if doc["table_rows"]:
        return pd.DataFrame(doc["table_rows"])
    fields = dict(doc["summary_fields"] or {})
    if doc.get("answer"):
        fields = {"answer": doc["answer"], **fields}
    return pd.DataFrame(list(fields.items()), columns=["field", "value"])


def render_csv(doc: dict) -> bytes:
    buf = io.StringIO()
    _document_to_dataframe(doc).to_csv(buf, index=False)
    return buf.getvalue().encode("utf-8")


def render_excel(doc: dict, is_report: bool = False) -> bytes:
    buf = io.BytesIO()
    if is_report:
        narrative = doc["narrative"] or {}
        kpi_df = pd.DataFrame(list((doc["summary_fields"] or {}).items()), columns=["field", "value"])
        summary_rows = [
            {"field": "headline", "value": narrative.get("headline")},
            {"field": "health_score", "value": narrative.get("health_score")},
            {"field": "health_label", "value": narrative.get("health_label")},
            {"field": "recommendation", "value": narrative.get("recommendation")},
        ] + [{"field": f"summary_point_{i + 1}", "value": p} for i, p in enumerate(narrative.get("summary_points", []))]
        summary_df = pd.DataFrame(summary_rows)
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            kpi_df.to_excel(writer, sheet_name="KPIs", index=False)
            summary_df.to_excel(writer, sheet_name="Executive Summary", index=False)
    else:
        _document_to_dataframe(doc).to_excel(buf, index=False, engine="openpyxl")
    return buf.getvalue()


def render_pdf(doc: dict, is_report: bool = False) -> bytes:
    template = _TEMPLATE_ENV.get_template("export.html")
    table_columns = list(doc["table_rows"][0].keys()) if doc["table_rows"] else None
    try:
        generated_display = datetime.fromisoformat(doc["generated_at"]).strftime("%b %d, %Y, %H:%M UTC")
    except (ValueError, TypeError):
        generated_display = doc["generated_at"]
    html = template.render(
        title=doc["title"],
        generated_at=generated_display,
        answer=doc.get("answer"),
        table_columns=table_columns,
        table_rows=doc["table_rows"],
        summary_fields=doc["summary_fields"],
        narrative=doc["narrative"] if is_report else None,
        primary_color=PRIMARY_COLOR,
        secondary_color=SECONDARY_COLOR,
        accent_color=ACCENT_COLOR,
        text_color=TEXT_COLOR,
    )
    return HTML(string=html).write_pdf()


def render(doc: dict, format: str, is_report: bool = False) -> bytes:
    if format == "csv":
        return render_csv(doc)
    if format == "xlsx":
        return render_excel(doc, is_report=is_report)
    if format == "pdf":
        return render_pdf(doc, is_report=is_report)
    raise ValueError(f"Unsupported export format: {format}")
