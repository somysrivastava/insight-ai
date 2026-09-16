import pandas as pd
import numpy as np

from app.services.storage_service import load_dataframe

def generate_insights(file_path: str) -> dict:
    df =load_dataframe(file_path)
# summary statistics
    numeric_cols=df.select_dtypes(include=[np.number]).columns.tolist()

    summary_stats ={}

    def _safe_round(value, digits=2):
        # NaN (e.g. std() of a single-row column, or any stat on an
        # all-null column) isn't valid JSON — json.dumps emits the
        # literal token `NaN` without erroring, which every prior
        # caller (an HTTP response) silently tolerated, but Postgres
        # JSONB correctly rejects as malformed (Day 21 caches this
        # dict, surfacing the bug for the first time). None serializes
        # cleanly everywhere NaN doesn't.
        value = float(value)
        return None if np.isnan(value) else round(value, digits)

    for col in numeric_cols:
        summary_stats[col] = {
            "mean": _safe_round(df[col].mean()),
            "median": _safe_round(df[col].median()),
            "std": _safe_round(df[col].std()),
            "min": _safe_round(df[col].min()),
            "max": _safe_round(df[col].max()),
            "sum": _safe_round(df[col].sum()),
        }

#kpi () key performance indicators
    kpis ={}

    revenue_col =next((c for c in df.columns if "revenue" in c.lower()), None)
    profit_col = next((c for c in df.columns if "profit" in c.lower()), None)
    cost_col = next((c for c in df.columns if "cost" in c.lower()), None)
    units_col = next((c for c in df.columns if "units" in c.lower() and "sold" in c.lower()), None) 

    if revenue_col:
        kpis["total_revenue"] = round(float(df[revenue_col].sum()), 2)
        kpis[" avg_order_revenue"] = round(float(df[revenue_col].mean()), 2)

    if profit_col:
        kpis["total_profit"] = round(float(df[profit_col].sum()), 2)

    if revenue_col and profit_col:
        total_rev=df[revenue_col].sum()
        total_prof=df[profit_col].sum()
        if total_rev > 0:
            kpis["profit_margin_pct"] = round(float(total_prof / total_rev * 100), 2)

    if units_col:
        kpis["total_units_sold"] = round(float(df[units_col].sum()), 2)

    kpis["total_records"] = len(df)

    # top_performer
    top_performers ={}
    categorical_cols = df.select_dtypes(include="object").columns.tolist()

    if revenue_col:
        for cat_col in categorical_cols:
            if df[cat_col].nunique() >50:             # Skip columns with too many unique values (like IDs or dates)
                continue
            grouped= df.groupby(cat_col)[revenue_col].sum().sort_values(ascending=False)
            top_performers[cat_col]= {
                "top": str(grouped.index[0]),
                "top_value": round(float(grouped.iloc[0]), 2),
                "bottom": str(grouped.index[-1]),
                "bottom_value": round(float(grouped.iloc[-1]), 2)
            }

    correlaation ={}
    if len(numeric_cols)>1:
        corr_matrix = df[numeric_cols].corr().round(3)
        for col in corr_matrix.columns:
            correlaation[col] = {
                k: (None if np.isnan(v) else v)
                for k, v in corr_matrix[col].to_dict().items()
                
            }
    return {
        "total_rows": len(df),
        "total_columns": len(df.columns),
        "numeric_columns": numeric_cols,
        "kpis": kpis,
        "summary_stats": summary_stats,
        "top_performers": top_performers,
        "correlation": correlaation,
    }

def generate_trends(file_path: str) -> dict:
    df = load_dataframe(file_path)
    date_col = None
    for col in df.columns:
        if "date" in col.lower():
            try:
                df[col] = pd.to_datetime(df[col])
                date_col = col
                break
            except Exception:
                continue
    if not date_col:
        return {"message": "No date column found in this dataset", "trends": []}
    df["_year"] = df[date_col].dt.year
    df["_month"] = df[date_col].dt.month
    df["_month_name"] = df[date_col].dt.strftime("%b")
    df["_period"] = df[date_col].dt.to_period("M").astype(str)

    revenue_col = next((c for c in df.columns if "revenue" in c.lower()), None)
    profit_col = next((c for c in df.columns if "profit" in c.lower()), None)
    units_col = next((c for c in df.columns if "unit" in c.lower() and "sold" in c.lower()), None)

    agg_dict = {}
    if revenue_col:
        agg_dict[revenue_col] = "sum"
    if profit_col:
        agg_dict[profit_col] = "sum"
    if units_col:
        agg_dict[units_col] = "sum"
    if not agg_dict:
        trends = df.groupby("_period").size().reset_index(name="count")
        trends = trends.sort_values("_period")
        return { "date column": date_col, 
            "trends": trends.to_dict(orient="records")}
    trends = df.groupby("_period").agg(agg_dict).reset_index()
    trends = trends.sort_values("_period")
    for col in [revenue_col, profit_col, units_col]:
        if col and col in trends.columns:
            trends[col] = trends[col].round(2)
    return { "date column": date_col, 
        "trends": trends.to_dict(orient="records")}

def generate_breakdown(file_path: str, group_by: str) -> dict:
    df = load_dataframe(file_path)
    if group_by not in df.columns:
        raise ValueError(f"Column '{group_by}' not found in the dataset")
    revenue_col = next((c for c in df.columns if "revenue" in c.lower()), None)
    profit_col = next((c for c in df.columns if "profit" in c.lower()), None)
    units_col = next((c for c in df.columns if "unit" in c.lower() and "sold" in c.lower()), None)

    agg_dict = {"_count": "size"}  # always count records per group
    
        # Build aggregation dynamically based on what columns exist
    agg_cols = {}
    if revenue_col:
        agg_cols[revenue_col] = "sum"
    if profit_col:
        agg_cols[profit_col] = "sum"
    if units_col:
        agg_cols[units_col] = "sum"

    if agg_cols:
        grouped = df.groupby(group_by).agg(agg_cols).reset_index()
    else:
        grouped = df.groupby(group_by).size().reset_index(name="count")

    count_series = df.groupby(group_by).size().reset_index(name="record_count")
    grouped = grouped.merge(count_series, on=group_by)

    if revenue_col and revenue_col in grouped.columns:
        grouped = grouped.sort_values(revenue_col, ascending=False)
        grouped[revenue_col] = grouped[revenue_col].round(2)
    if profit_col and profit_col in grouped.columns:
        grouped[profit_col] = grouped[profit_col].round(2)
    
    return {
        "group_by": group_by,
        "breakdown": grouped.to_dict(orient="records")
    }


def _validate_query_column(df: pd.DataFrame, col_name, label: str) -> None:
    if col_name and col_name not in df.columns:
        raise ValueError(
            f"{label} '{col_name}' not found in dataset. Available columns: {list(df.columns)}"
        )


_NULL_PLACEHOLDERS = {"", "null", "none", "n/a", "na"}


def _normalize(value):
    """
    The model is instructed to use JSON null for an unused column/metric,
    but isn't perfectly reliable about it in practice (observed empty
    string and the literal text "null" for the same field on different
    calls at temperature=0). Treat all of those as "not provided" rather
    than trusting the model's exact spelling.
    """
    if isinstance(value, str) and value.strip().lower() in _NULL_PLACEHOLDERS:
        return None
    return value


def execute_structured_query(df: pd.DataFrame, query: dict) -> dict:
    """
    Executes a structured query (as parsed by ai_service.py from a natural-
    language question) against an already-loaded DataFrame.

    Every column referenced by the query is validated against the real
    DataFrame before use — the query may have been produced by an LLM that
    was never shown the dataset's actual values, so this is the point where
    hallucinated columns/values get caught and turned into a clean error
    instead of a raw pandas KeyError.
    """
    operation = query["operation"]
    column = _normalize(query.get("column"))
    metric = _normalize(query.get("metric"))
    aggregate = _normalize(query.get("aggregate")) or "sum"
    filter_value = _normalize(query.get("filter_value"))
    filter_operator = _normalize(query.get("filter_operator")) or "eq"
    limit = query.get("limit") or 10
    ascending = query.get("direction") == "asc"

    if operation == "groupby":
        _validate_query_column(df, column, "column")
        _validate_query_column(df, metric, "metric")
        if not column or not metric:
            raise ValueError("groupby requires both 'column' and 'metric'")
        grouped = (
            df.groupby(column)[metric]
            .agg(aggregate)
            .reset_index()
            .sort_values(metric, ascending=ascending)
            .head(limit)
        )
        grouped[metric] = grouped[metric].round(2)
        return {
            "operation": operation,
            "records": grouped.to_dict(orient="records"),
            "row_count": len(grouped),
        }

    if operation == "filter":
        _validate_query_column(df, column, "column")
        if not column:
            raise ValueError("filter requires 'column'")
        if filter_value is None:
            raise ValueError("filter requires 'filter_value'")

        if filter_operator == "eq":
            mask = df[column].astype(str).str.strip().str.lower() == str(filter_value).strip().lower()
        else:
            try:
                threshold = float(filter_value)
            except (TypeError, ValueError):
                raise ValueError(
                    f"filter_operator '{filter_operator}' requires a numeric filter_value, got '{filter_value}'."
                )
            numeric_col = pd.to_numeric(df[column], errors="coerce")
            comparisons = {
                "gt": numeric_col > threshold,
                "gte": numeric_col >= threshold,
                "lt": numeric_col < threshold,
                "lte": numeric_col <= threshold,
            }
            if filter_operator not in comparisons:
                raise ValueError(f"Unsupported filter_operator '{filter_operator}'.")
            mask = comparisons[filter_operator]

        if not mask.any():
            raise ValueError(f"No rows match {column} {filter_operator} {filter_value}.")

        filtered = df[mask]

        if metric:
            _validate_query_column(df, metric, "metric")
            if aggregate == "count":
                value = int(mask.sum())
            else:
                series = pd.to_numeric(filtered[metric], errors="coerce").dropna()
                value = round(float(getattr(series, aggregate)()), 2)
            return {
                "operation": operation,
                "column": column,
                "filter_value": filter_value,
                "filter_operator": filter_operator,
                "metric": metric,
                "aggregate": aggregate,
                "value": value,
                "row_count": int(mask.sum()),
            }

        result = filtered.head(limit)
        return {
            "operation": operation,
            "records": result.to_dict(orient="records"),
            "row_count": int(mask.sum()),
        }

    if operation == "sort":
        sort_col = metric or column
        _validate_query_column(df, sort_col, "metric/column")
        if not sort_col:
            raise ValueError("sort requires 'metric' or 'column'")
        sorted_df = df.sort_values(sort_col, ascending=ascending).head(limit)
        return {
            "operation": operation,
            "records": sorted_df.to_dict(orient="records"),
            "row_count": len(sorted_df),
        }

    if operation == "aggregate":
        _validate_query_column(df, metric, "metric")
        if not metric:
            raise ValueError("aggregate requires 'metric'")
        series = pd.to_numeric(df[metric], errors="coerce").dropna()
        value = getattr(series, aggregate)()
        return {
            "operation": operation,
            "metric": metric,
            "aggregate": aggregate,
            "value": round(float(value), 2),
            "row_count": len(df),
        }

    if operation == "correlate":
        _validate_query_column(df, column, "column")
        _validate_query_column(df, metric, "metric")
        if not column or not metric:
            raise ValueError("correlate requires both 'column' and 'metric'")
        series_a = pd.to_numeric(df[column], errors="coerce")
        series_b = pd.to_numeric(df[metric], errors="coerce")
        corr = series_a.corr(series_b)
        return {
            "operation": operation,
            "column": column,
            "metric": metric,
            "correlation": None if pd.isna(corr) else round(float(corr), 3),
            "row_count": len(df),
        }

    raise ValueError(f"Unsupported operation: {operation}")
