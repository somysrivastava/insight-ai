from hmac import new
from pathlib import Path

import numpy as np
import pandas as pd
from numpy.ma.core import filled
from sqlalchemy import true


def load_dataframe(file_path: str) -> pd.DataFrame:
    path = Path(file_path)

    if path.suffix == ".csv":
        return pd.read_csv(file_path)
    elif path.suffix in [".xlsx", ".xls"]:
        return pd.read_excel(file_path)
    else:
        raise ValueError(f"Unsupported files")


def generate_quality_report(file_path: str) -> dict:
    df = load_dataframe(file_path)

    total_rows, total_columns = df.shape

    missing_counts = df.isnull().sum()

    missing_pct = (df.isnull().mean() * 100).round(
        2
    )  # mean because it gives proportion of missing values

    missing_values = [
        {
            "column": col,
            "missing_count": int(str(missing_counts[col])),
            "missing_percentage": float(missing_pct[col]),
        }
        for col in df.columns
        if missing_counts[col]
        > 0  # jin colmn me missing value > 0 h unn columns ko iterate arke per col data denge
    ]

    # duplicate rows
    duplicate_count = int(df.duplicated().sum())
    column_types = {
        col: str(df[col].dtype) for col in df.columns
    }  # df.dtypes returns a series of dtype objects

    numeric_outliers = []
    for col in df.select_dtypes(include=[np.number]).columns:
        Q1 = df[col].quantile(0.25)  # 25th percentile
        Q3 = df[col].quantile(0.75)
        IQR = Q3 - Q1

        if IQR == 0:
            continue
        lower_bound = Q1 - 1.5 * IQR
        uppper_bound = Q3 + 1.5 * IQR

        outlier_mask = (df[col] < lower_bound) | (df[col] > uppper_bound)

        outlier_count = int(outlier_mask.sum())

        if outlier_count > 0:
            numeric_outliers.append(
                {
                    "column": col,
                    "outlier_count": outlier_count,
                    "lower_bound": float(lower_bound),
                    "upper_bound": float(uppper_bound),
                }
            )

    score = 100

    total_cells = total_rows * total_columns

    if total_cells > 0:
        total_missing = int(df.isnull().sum().sum())

        missing_ratio = total_missing / total_cells

        score -= min(40, missing_ratio * 100)
    if total_rows > 0:
        dup_ratio = duplicate_count / total_rows
        score -= min(30, dup_ratio * 100)

    score -= min(30, len(numeric_outliers) * 100)
    quality_score = max(0, round(score, 1))

    return {
        "total_rows": total_rows,
        "total_columns": total_columns,
        "missing_values": missing_values,
        "duplicate_rows": duplicate_count,
        "column_types": column_types,
        "numeric_outliers": numeric_outliers,
        "quality_score": quality_score,
    }


def clean_dataset(file_path: str, options: dict) -> dict:
    df = load_dataframe(file_path)
    original_rows = len(df)
    changes = []  # "append human readable description here"

    if options.get("normalise_column_names", True):
        original_cols = list(df.columns)
        df.columns = (
            df.columns.str.strip()
            .str.lower()
            .str.replace(r"[^a-z0-9]", "_", regex=True)
        ).str.strip(
            "_"
        )  # strip karke whitespace remove kiya then convert to lower case then replace any non alpha numeri cchar to underscre or fir last me agar koi _ leading ya trailing ho to usko remove kiya
        new_cols = list(df.columns)

        if original_cols != new_cols:
            changes.append(f"Normalised {len(df.columns)} column names")

    if options.get("remove_duplicates", True):
        before = len(df)
        df = df.drop_duplicates()
        removed = before - len(df)

        if removed > 0:
            changes.append(f"Removed {removed} duplicate rows")
    if options.get("strip_whitespace", True):
        text_cols = df.select_dtypes(include="object").columns
        for col in text_cols:
            df[col] = df[col].str.strip()
        if len(text_cols) > 0:
            changes.append(f"Stripped whitespace from {len(text_cols)} text columns")

    numeric_strategy = options.get("fill_missing_numeric", "median")
    # missing numeric
    if numeric_strategy != "none":
        numeric_cols = df.select_dtypes(include=np.number).columns
        filled_cols = []

        for col in numeric_cols:
            missing_before = df[col].isnull().sum()
            if missing_before > 0:
                continue
            if numeric_strategy == "median":
                fill_value = df[col].median
            elif numeric_strategy == "mean":
                fill_value = df[col].mean
            elif numeric_strategy == "zero":
                fill_value = 0
            else:
                continue
        if filled_cols:
            changes.append(
                f"Filled missing numeric values in {len(filled_cols)} columns using {numeric_strategy} strategy"
            )
    # categorical
    categorical_strategy = options.get("fill_missing_categorical", "unknown")

    if (
        categorical_strategy != "none"
    ):  # like upar wala is for missig numeric values ye wala is for text
        cat_cols = df.select_dtypes(include="object").columns
        filled_cat_cols = []

        for col in cat_cols:
            missing_before = df[col].isnull().sum()
            if missing_before > 0:
                continue

            df[col] = df[col].fillna("Unknown")
            filled_cat_cols.append(col)

        if filled_cat_cols:
            changes.append(
                f"Filled missing categorical values in {len(filled_cat_cols)} columns using 'Unknown' strategy"
            )

    path = Path(file_path)
    if path.suffix == ".csv":
        df.to_csv(
            file_path, index=False
        )  # index=False prevents pandas from writing the row index as an extra column
    else:
        df.to_excel(file_path, index=False)

    return {
        "original_rows": original_rows,
        "cleaned_rows": len(df),
        "rows_removed": original_rows - len(df),
        "changes_applied": changes,
        "message": "Dataset cleaned successfully"
        if changes
        else "No changes were necessary",
    }
