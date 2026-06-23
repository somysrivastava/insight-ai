from functools import total_ordering
from tomllib import load

import pandas as pd
import numpy as np
from pathlib import Path

from pandas.core.interchange.from_dataframe import categorical_column_to_series

def load_dataframe(file_path: str) -> pd.DataFrame:
    path = Path(file_path)
    if path.suffix == '.csv':
        return pd.read_csv(path)
    elif path.suffix in [".xlsx", ".xls"]:
        return pd.read_excel(path)
    raise ValueError(f"Unsupported file type: {path.suffix}")

def generate_insights(file_path: str) -> dict:
    df =load_dataframe(file_path)
# summary statistics
    numeric_cols=df.select_dtypes(include=[np.number]).columns.tolist()

    summary_stats ={}

    for col in numeric_cols:
        summary_stats[col] = {
            "mean": round(float(df[col].mean()),2),
            "median": round(float(df[col].median()),2),
            "std": round(float(df[col].std()),2),
            "min": round(float(df[col].min()),2),
            "max": round(float(df[col].max()),2),
            "sum": round(float(df[col].sum()),2),
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
