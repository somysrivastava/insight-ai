from typing import Any

import numpy as np
import pandas as pd


def compute_kpis(df: pd.DataFrame) -> dict[str, Any]:
    kpis: dict[str, Any] = {}
    total_cells = df.shape[0] * df.shape[1]
    missing_cells = int(df.isnull().sum().sum())
    kpis["total_records"] = int(df.shape[0])
    kpis["total_columns"] = int(df.shape[1])
    kpis["missing_cells"] = missing_cells
    kpis["data_completeness_pct"] = (
        round((total_cells - missing_cells) / total_cells * 100, 2)
        if total_cells > 0
        else 0.0
    )
    kpis["duplicate_records"] = int(df.duplicated().sum())

    numeric_cols=df.select_dtypes(include=[np.number]).columns.tolist()
    if numeric_cols:
        value_keywords=["amount", "revenue", "sales", "price", "value", "total", "cost", "profit"]
        primary_col=next((col for col in numeric_cols if any(kw in col.lower() for kw in value_keywords)), numeric_cols[0])
        series=df[primary_col].dropna()

        kpis["primary_metric_column"] = primary_col
        kpis["total_value"] = round(float(series.sum()), 2)
        kpis["average_value"] = round(float(series.mean()), 2)
        kpis["median_value"] = round(float(series.median()), 2)
        kpis["max_value"] = round(float(series.max()), 2)
        kpis["min_value"] = round(float(series.min()), 2)
        kpis["std_deviation"] = round(float(series.std()), 2)

        if series.mean()!=0:
            kpis["coeff_of_variation"] = round(float(series.std() / series.mean()), 4)

        q75 =float(series.quantile(0.75))
        kpis["high_value_records"] =  int((series >= q75).sum())
        kpis["high_value_threshold"] = round(q75, 2)

    date_cols = df.select_dtypes(include=["datetime64[ns]", "datetime64[ns, UTC]"]).columns.tolist()

    if not date_cols:
        for col in df.select_dtypes(include=["object"]).columns:
            try:
                # infer_datetime_format was a no-op hint even when pandas
                # still accepted it (deprecated in 2.x); this pandas
                # version has dropped the kwarg entirely, so passing it
                # raised TypeError on every single call here — silently
                # swallowed by the except below, which meant this whole
                # auto-detect branch never actually parsed anything.
                # Found by Day 27's tests, not by inspection: pandas
                # infers the format on its own regardless.
                parsed = pd.to_datetime(df[col], errors="coerce")
                if parsed.notna().sum() > len(df) * 0.7:
                    df = df.copy()
                    df[col] = parsed
                    date_cols.append(col)
                    break
            except Exception:  # pragma: no cover
                # pd.to_datetime(..., errors="coerce") coerces every
                # exotic input tried (dicts, bytes, complex numbers,
                # nested lists, out-of-range strings) to NaT rather than
                # raising — confirmed by hand, not assumed — so this has
                # no known reachable trigger. Left as a defensive
                # fallback, not deleted, in case a future pandas version
                # reintroduces a raising case here.
                pass

    if date_cols:
        primary_date_col =date_cols[0]
        data_series=pd.to_datetime(df[primary_date_col], errors="coerce").dropna()

        kpis["date_column"] = primary_date_col
        kpis["date_range_start"] = str(data_series.min().date())
        kpis["date_range_end"] = str(data_series.max().date())
        kpis["reporting_period_days"] = int((data_series.max() - data_series.min()).days)

        if numeric_cols and "primary_metric_column" in kpis:
            try:
                temp=df[[primary_date_col, kpis["primary_metric_column"]]].copy()
                temp[primary_date_col] = pd.to_datetime(temp[primary_date_col], errors="coerce")
                temp = temp.dropna()
                temp["_month"] = temp[primary_date_col].dt.to_period("M")
                # Summing only the metric column, not .groupby().sum()
                # on the whole frame — this pandas version raises
                # TypeError ("datetime64 type does not support operation
                # 'sum'") the moment the still-present date column is
                # summed alongside it, which the except below silently
                # swallowed on every call. Also found by Day 27's tests.
                monthly = temp.groupby("_month")[kpis["primary_metric_column"]].sum()
                if len(monthly) >= 2:
                    last=float(monthly.iloc[-1])
                    prev=float(monthly.iloc[-2])
                    if prev != 0:
                        kpis["mom_growth_pct"] = round(((last - prev) / prev) * 100, 2)

            except Exception:  # pragma: no cover
                # Same as above — tried nullable Int64 metrics, extreme
                # historical dates, and the datetime-sum bug fixed above
                # trying to find a live trigger; none raise here anymore
                # under this pandas version. Kept as a safety net.
                pass
    categorical_cols = df.select_dtypes(include=["object", "category"]).columns.tolist()
    if categorical_cols:
        segment_cols = [col for col in categorical_cols if 2 < df[col].nunique() < 50]
        if segment_cols:
            top_segment_col = segment_cols[0]
            kpis["primary_segment_column"] = top_segment_col
            kpis["segment_count"] = int(df[top_segment_col].nunique())
    return kpis