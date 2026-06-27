# WHY THIS FILE EXISTS:
# All chart-building logic lives here, NOT in the router.
# Routers handle HTTP (parse request, return response).
# Services handle business logic (load data, build chart, return JSON).
# This separation means you can call visualization logic from background jobs,
# other services, or tests — without going through HTTP.

import os
import json
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.models.dataset import Dataset
from app.schemas.visualization import (
    BarChartRequest,
    LineChartRequest,
    PieChartRequest,
    ScatterChartRequest,
    DashboardRequest,
)

# ── InsightAI brand colors ──────────────────────────────────────────────────
# WHY CONSTANTS: Consistent palette across all charts makes the product look
# professional. Never hardcode hex values in chart functions — change here, 
# updates everywhere.
PRIMARY_COLOR = "#667EEA"
SECONDARY_COLOR = "#764BA2"
ACCENT_COLOR = "#F093FB"
BACKGROUND_COLOR = "#FFFFFF"
GRID_COLOR = "#F0F0F0"
TEXT_COLOR = "#2D3748"

COLOR_PALETTE = [
    "#667EEA", "#764BA2", "#F093FB", "#4ECDC4",
    "#45B7D1", "#96CEB4", "#FFEAA7", "#DDA0DD",
    "#98D8C8", "#F7DC6F"
]

UPLOAD_DIR = "app/uploads"


# ── Internal Helpers ────────────────────────────────────────────────────────

def _load_dataset(dataset_id: int, user_id: int, db: Session) -> pd.DataFrame:
    """
    Fetch dataset record from DB, load CSV into DataFrame.
    
    WHY CENTRALIZED: Every chart endpoint needs the same load + auth check.
    Extract it once. If the file storage changes (e.g. move to S3 on Build Day 12),
    you update only this function.
    """
    # Auth check: ensure this dataset belongs to the requesting user
    dataset = db.query(Dataset).filter(
        Dataset.id == dataset_id,
        Dataset.user_id == user_id
    ).first()

    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")

    file_path = dataset.file_path
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Dataset file not found on disk")

    try:
        df = pd.read_csv(file_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read dataset: {str(e)}")

    return df


def _validate_columns(df: pd.DataFrame, *columns: str) -> None:
    """
    Validate that requested columns exist in the DataFrame.
    
    WHY: If the user passes a wrong column name, pandas raises a confusing
    KeyError deep in the stack. This catches it early and returns a clean
    400 error with a helpful message.
    """
    available = list(df.columns)
    for col in columns:
        if col and col not in df.columns:
            raise HTTPException(
                status_code=400,
                detail=f"Column '{col}' not found. Available columns: {available}"
            )


def _apply_theme(fig: go.Figure) -> go.Figure:
    """
    Apply InsightAI visual theme to any Plotly figure.
    
    WHY: Every chart shares the same layout settings. Centralizing this means:
    1. One change updates all charts
    2. No copy-paste bugs between chart functions
    3. Product looks consistent — important for portfolio demos
    """
    fig.update_layout(
        paper_bgcolor=BACKGROUND_COLOR,
        plot_bgcolor=GRID_COLOR,
        font=dict(family="Inter, Arial, sans-serif", color=TEXT_COLOR, size=13),
        title_font=dict(size=18, color=TEXT_COLOR, family="Inter, Arial, sans-serif"),
        margin=dict(l=50, r=30, t=70, b=50),
        hoverlabel=dict(
            bgcolor="#1A1A2E",
            font_color="white",
            font_family="Inter, Arial, sans-serif"
        ),
        colorway=COLOR_PALETTE,
    )
    # Subtle grid lines on axes — easier to read values
    fig.update_xaxes(showgrid=False, linecolor="#E2E8F0")
    fig.update_yaxes(showgrid=True, gridcolor="#E2E8F0", linecolor="#E2E8F0")
    return fig


def _fig_to_response(fig: go.Figure, chart_type: str, columns: dict, row_count: int) -> dict:
    """
    Serialize a Plotly figure into the standard API response dict.
    
    WHY fig.to_json(): Plotly figures are Python objects. HTTP responses are text.
    fig.to_json() converts the entire figure (data, layout, config) into a JSON string
    that the frontend can deserialize and render with Plotly.js.
    """
    return {
        "chart_json": fig.to_json(),
        "chart_type": chart_type,
        "columns_used": columns,
        "row_count": row_count
    }


# ── Chart Builders ──────────────────────────────────────────────────────────

def build_bar_chart(
    dataset_id: int,
    user_id: int,
    request: BarChartRequest,
    db: Session
) -> dict:
    """
    Build a bar chart: top N categories by aggregated value.
    
    Real-world use: "Show me top 10 products by revenue this quarter."
    """
    df = _load_dataset(dataset_id, user_id, db)
    _validate_columns(df, request.category_column, request.value_column)

    # Ensure value column is numeric
    df[request.value_column] = pd.to_numeric(df[request.value_column], errors="coerce")

    # Aggregate: sum value per category, take top N, sort descending
    # WHY groupby+sum: A dataset may have multiple rows per category
    # (e.g. daily sales per product). We sum to get the total per category.
    agg = (
        df.groupby(request.category_column)[request.value_column]
        .sum()
        .reset_index()
        .sort_values(request.value_column, ascending=False)
        .head(request.top_n)
    )

    title = request.title or f"Top {request.top_n} {request.category_column} by {request.value_column}"

    fig = px.bar(
        agg,
        x=request.category_column,
        y=request.value_column,
        title=title,
        color=request.category_column,   # each bar gets a distinct color
        color_discrete_sequence=COLOR_PALETTE,
        text=request.value_column
    )

    # Format text labels on bars (e.g. 45,000 instead of 45000)
    fig.update_traces(
        texttemplate="%{text:,.0f}",
        textposition="outside",
        marker_line_width=0      # no outline on bars — cleaner look
    )
    fig.update_layout(showlegend=False, xaxis_title=None)
    fig = _apply_theme(fig)

    return _fig_to_response(
        fig, "bar",
        {"category": request.category_column, "value": request.value_column},
        len(df)
    )


def build_line_chart(
    dataset_id: int,
    user_id: int,
    request: LineChartRequest,
    db: Session
) -> dict:
    """
    Build a line chart showing value trend over time (or ordered periods).
    
    Real-world use: "Show me monthly revenue for the last year."
    """
    df = _load_dataset(dataset_id, user_id, db)
    _validate_columns(df, request.date_column, request.value_column, request.group_by)

    df[request.value_column] = pd.to_numeric(df[request.value_column], errors="coerce")

    # Parse dates — pd.to_datetime handles most formats automatically
    # WHY: If date column is stored as string, groupby won't sort chronologically.
    # Converting to datetime ensures correct time ordering.
    try:
        df[request.date_column] = pd.to_datetime(df[request.date_column])
        df["_period"] = df[request.date_column].dt.to_period("M").astype(str)
    except Exception:
        # Fallback: treat the column as categorical (e.g. "Jan", "Feb", "Q1")
        df["_period"] = df[request.date_column].astype(str)

    group_cols = ["_period"]
    if request.group_by:
        group_cols.append(request.group_by)

    # Aggregate by period (and optionally by group)
    agg = (
        df.groupby(group_cols)[request.value_column]
        .sum()
        .reset_index()
        .sort_values("_period")
    )

    title = request.title or f"{request.value_column} Trend Over Time"

    fig = px.line(
        agg,
        x="_period",
        y=request.value_column,
        color=request.group_by if request.group_by else None,
        title=title,
        markers=True,     # dots at each data point — easier to read
        color_discrete_sequence=COLOR_PALETTE,
        labels={"_period": "Period"}
    )

    fig.update_traces(line_width=2.5)
    fig = _apply_theme(fig)

    return _fig_to_response(
        fig, "line",
        {"date": request.date_column, "value": request.value_column, "group": request.group_by},
        len(df)
    )


def build_pie_chart(
    dataset_id: int,
    user_id: int,
    request: PieChartRequest,
    db: Session
) -> dict:
    """
    Build a donut chart showing category share of total.
    
    Real-world use: "What's our revenue split across product categories?"
    
    WHY DONUT (hole=0.4): Donut charts are easier to read than full pies
    because the center area can show a KPI value. Standard in modern dashboards.
    """
    df = _load_dataset(dataset_id, user_id, db)
    _validate_columns(df, request.category_column, request.value_column)

    df[request.value_column] = pd.to_numeric(df[request.value_column], errors="coerce")

    agg = (
        df.groupby(request.category_column)[request.value_column]
        .sum()
        .reset_index()
        .sort_values(request.value_column, ascending=False)
    )

    # WHY "Other" grouping: Pie charts with 10+ slices are unreadable.
    # We keep top N and collapse the rest into a single "Other" slice.
    if len(agg) > request.top_n:
        top = agg.head(request.top_n)
        other_value = agg.iloc[request.top_n:][request.value_column].sum()
        other_row = pd.DataFrame({
            request.category_column: ["Other"],
            request.value_column: [other_value]
        })
        agg = pd.concat([top, other_row], ignore_index=True)

    title = request.title or f"{request.value_column} Distribution by {request.category_column}"

    fig = px.pie(
        agg,
        names=request.category_column,
        values=request.value_column,
        title=title,
        hole=0.4,
        color_discrete_sequence=COLOR_PALETTE
    )

    fig.update_traces(
        textposition="inside",
        textinfo="percent+label",
        hovertemplate="<b>%{label}</b><br>Value: %{value:,.0f}<br>Share: %{percent}"
    )
    fig = _apply_theme(fig)

    return _fig_to_response(
        fig, "pie",
        {"category": request.category_column, "value": request.value_column},
        len(df)
    )


def build_scatter_chart(
    dataset_id: int,
    user_id: int,
    request: ScatterChartRequest,
    db: Session
) -> dict:
    """
    Build a scatter plot to visualize correlation between two numeric columns.
    
    Real-world use: "Does more marketing spend lead to higher revenue?"
    """
    df = _load_dataset(dataset_id, user_id, db)
    _validate_columns(df, request.x_column, request.y_column, request.color_column)

    df[request.x_column] = pd.to_numeric(df[request.x_column], errors="coerce")
    df[request.y_column] = pd.to_numeric(df[request.y_column], errors="coerce")
    df = df.dropna(subset=[request.x_column, request.y_column])

    title = request.title or f"{request.x_column} vs {request.y_column}"

    fig = px.scatter(
        df,
        x=request.x_column,
        y=request.y_column,
        color=request.color_column,
        title=title,
        trendline="ols",    # Adds linear regression line — shows direction of correlation
        color_discrete_sequence=COLOR_PALETTE,
        opacity=0.7         # Slight transparency so overlapping points are visible
    )

    fig = _apply_theme(fig)

    return _fig_to_response(
        fig, "scatter",
        {"x": request.x_column, "y": request.y_column, "color": request.color_column},
        len(df)
    )


def build_dashboard(
    dataset_id: int,
    user_id: int,
    request: DashboardRequest,
    db: Session
) -> dict:
    """
    Build a multi-chart executive dashboard using subplots.
    
    Layout:
      Row 1: Bar chart (top categories) | Pie chart (distribution)
      Row 2: Line chart (trend) — only if date_column provided
    
    WHY SUBPLOTS: One API call, one JSON blob, one render on the client.
    This is how real BI tools (Metabase, Looker) generate dashboard snapshots.
    
    WHY make_subplots: Plotly's subplot system positions multiple independent
    charts on a shared canvas with aligned spacing and a unified title.
    """
    df = _load_dataset(dataset_id, user_id, db)
    _validate_columns(df, request.category_column, request.value_column)

    df[request.value_column] = pd.to_numeric(df[request.value_column], errors="coerce")

    has_date = request.date_column and request.date_column in df.columns

    # ── Layout decision ──────────────────────────────────────────────────
    # 2 rows if we have a date column (adds trend chart), else 1 row
    rows = 2 if has_date else 1
    specs = [[{"type": "xy"}, {"type": "domain"}]]  # row 1: bar + pie
    subplot_titles = [
        f"Top {request.top_n} by {request.value_column}",
        f"{request.value_column} Distribution"
    ]

    if has_date:
        specs.append([{"type": "xy", "colspan": 2}, None])  # row 2: full-width line
        subplot_titles.append(f"{request.value_column} Trend Over Time")

    fig = make_subplots(
        rows=rows,
        cols=2,
        specs=specs,
        subplot_titles=subplot_titles,
        vertical_spacing=0.15,
        horizontal_spacing=0.1
    )

    # ── Bar chart data ───────────────────────────────────────────────────
    bar_agg = (
        df.groupby(request.category_column)[request.value_column]
        .sum()
        .reset_index()
        .sort_values(request.value_column, ascending=False)
        .head(request.top_n)
    )

    fig.add_trace(
        go.Bar(
            x=bar_agg[request.category_column],
            y=bar_agg[request.value_column],
            name="By Category",
            marker_color=COLOR_PALETTE[:len(bar_agg)],
            showlegend=False
        ),
        row=1, col=1
    )

    # ── Pie chart data ───────────────────────────────────────────────────
    pie_agg = bar_agg.copy()  # reuse top N already computed above

    fig.add_trace(
        go.Pie(
            labels=pie_agg[request.category_column],
            values=pie_agg[request.value_column],
            hole=0.4,
            showlegend=True,
            marker_colors=COLOR_PALETTE[:len(pie_agg)]
        ),
        row=1, col=2
    )

    # ── Line chart data (optional) ───────────────────────────────────────
    if has_date:
        try:
            df[request.date_column] = pd.to_datetime(df[request.date_column])
            df["_period"] = df[request.date_column].dt.to_period("M").astype(str)
        except Exception:
            df["_period"] = df[request.date_column].astype(str)

        line_agg = (
            df.groupby("_period")[request.value_column]
            .sum()
            .reset_index()
            .sort_values("_period")
        )

        fig.add_trace(
            go.Scatter(
                x=line_agg["_period"],
                y=line_agg[request.value_column],
                mode="lines+markers",
                name="Trend",
                line=dict(color=PRIMARY_COLOR, width=2.5),
                showlegend=False
            ),
            row=2, col=1
        )

    # ── Final layout ─────────────────────────────────────────────────────
    fig.update_layout(
        title_text=request.title,
        title_font=dict(size=20, color=TEXT_COLOR),
        height=700 if has_date else 420,
        paper_bgcolor=BACKGROUND_COLOR,
        font=dict(family="Inter, Arial, sans-serif", color=TEXT_COLOR),
        margin=dict(l=50, r=30, t=80, b=50)
    )

    return _fig_to_response(
        fig, "dashboard",
        {
            "category": request.category_column,
            "value": request.value_column,
            "date": request.date_column
        },
        len(df)
    )