# WHY THIS FILE EXISTS:
# Owns ColumnMapping CRUD plus the GPT-backed auto_suggest. Deliberately
# synchronous, no Celery task — this feature's own spec calls it fast
# enough not to need one, unlike Day 14/17's AI calls which got async
# variants because they're on a hot request path with heavier payloads.
# Framework-agnostic (raises ValueError, not HTTPException), same as
# access_control.py, so the router translates errors to HTTP status.

import json
import os
from typing import Optional

import pandas as pd
from dotenv import load_dotenv
from openai import OpenAI
from sqlalchemy.orm import Session

from app.models.column_mapping import ColumnMapping
from app.models.dataset import Dataset
from app.services.storage_service import load_dataframe

load_dotenv()

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    return _client


def get_dictionary(db: Session, dataset_id: int) -> dict[str, ColumnMapping]:
    rows = db.query(ColumnMapping).filter(ColumnMapping.dataset_id == dataset_id).all()
    return {row.column_name: row for row in rows}


def _load_columns(dataset: Dataset) -> list[str]:
    return list(load_dataframe(dataset.file_path).columns)


def get_mapping(db: Session, dataset_id: int, column_name: str) -> Optional[ColumnMapping]:
    return (
        db.query(ColumnMapping)
        .filter(ColumnMapping.dataset_id == dataset_id, ColumnMapping.column_name == column_name)
        .first()
    )


def upsert_mapping(
    db: Session,
    dataset: Dataset,
    column_name: str,
    display_name: str,
    description: Optional[str] = None,
    unit: Optional[str] = None,
    is_metric: bool = False,
    is_dimension: bool = False,
) -> ColumnMapping:
    if column_name not in _load_columns(dataset):
        raise ValueError(f"Column '{column_name}' not found in dataset.")

    mapping = get_mapping(db, dataset.id, column_name)
    if mapping is None:
        mapping = ColumnMapping(dataset_id=dataset.id, column_name=column_name)
        db.add(mapping)

    mapping.display_name = display_name
    mapping.description = description
    mapping.unit = unit
    mapping.is_metric = is_metric
    mapping.is_dimension = is_dimension

    db.commit()
    db.refresh(mapping)
    return mapping


def update_mapping(db: Session, mapping: ColumnMapping, **updates) -> ColumnMapping:
    """PATCH — caller (routers/dictionary.py) guarantees `mapping` already exists."""
    for field, value in updates.items():
        setattr(mapping, field, value)
    db.commit()
    db.refresh(mapping)
    return mapping


def delete_mapping(db: Session, mapping: ColumnMapping) -> None:
    db.delete(mapping)
    db.commit()


SUGGEST_SCHEMA = {
    "type": "object",
    "properties": {
        "suggestions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "column_name": {"type": "string"},
                    "display_name": {"type": "string"},
                    "description": {"type": "string"},
                    "unit": {"type": ["string", "null"]},
                },
                "required": ["column_name", "display_name", "description", "unit"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["suggestions"],
    "additionalProperties": False,
}

SUGGEST_SYSTEM_PROMPT = """You are helping build a data dictionary for InsightAI. \
Given a dataset's schema (column names, types, and statistics only — no actual row \
values), suggest a human-readable display_name, a one-sentence description, and a \
unit for EVERY column listed, even ones whose name already looks clear.

Rules:
- "column_name" must exactly match one of the given column names, unchanged.
- "display_name" is a short, human-readable label (e.g. "del_t" -> "Delivery Time", \
"cust_id_v2" -> "Customer ID").
- "unit" is a short physical/measurement unit when the column is a quantity (e.g. \
"minutes", "INR", "km", "%") — use JSON null for identifiers, names, categories, or \
dates, never the placeholder text "null" or "n/a".
- Base your suggestions only on the column name and the statistics given (dtype, \
numeric range/mean, or categorical distinct-count) — you are not shown any actual \
data values, so don't guess at specific values or ranges you weren't given.
"""


def _build_schema_context(df: pd.DataFrame, columns: list[str]) -> list[dict]:
    """
    Same column-names/dtypes/stats-only shape as ai_service.py's own
    dataset context — no raw cell values, per ADR-009's no-raw-values
    policy, explicitly re-confirmed for this endpoint (ADR-017) rather
    than quietly reinterpreted.
    """
    entries = []
    for col in columns:
        entry: dict = {"name": col, "dtype": str(df[col].dtype)}
        if pd.api.types.is_numeric_dtype(df[col]):
            series = df[col].dropna()
            if len(series):
                entry["min"] = round(float(series.min()), 2)
                entry["max"] = round(float(series.max()), 2)
                entry["mean"] = round(float(series.mean()), 2)
        else:
            entry["unique_count"] = int(df[col].nunique())
        entries.append(entry)
    return entries


def auto_suggest(db: Session, dataset: Dataset) -> tuple[list[ColumnMapping], list[str]]:
    """
    Suggests display_name/description/unit for every column that
    doesn't already have a saved mapping — one OpenAI call covers every
    target column at once, not one call per column. Columns that
    already have a mapping are left untouched (your explicit choice —
    protects manual edits from being overwritten by a re-run) and
    returned separately as `skipped_existing`. is_metric/is_dimension
    aren't part of what GPT suggests (per your literal field list) —
    they default to False here, same as any other new mapping, left for
    manual curation via PUT/PATCH.

    Returns (newly_saved_mappings, skipped_existing_column_names).
    """
    df = load_dataframe(dataset.file_path)
    existing = get_dictionary(db, dataset.id)
    target_columns = [c for c in df.columns if c not in existing]

    if not target_columns:
        return [], list(existing.keys())

    schema_context = _build_schema_context(df, target_columns)

    client = _get_client()
    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        temperature=0,
        messages=[
            {"role": "system", "content": SUGGEST_SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps({"columns": schema_context})},
        ],
        response_format={
            "type": "json_schema",
            "json_schema": {"name": "column_suggestions", "strict": True, "schema": SUGGEST_SCHEMA},
        },
    )

    raw = response.choices[0].message.content
    if not raw:
        raise ValueError("Model returned no output for dictionary suggestions.")
    parsed = json.loads(raw)

    target_set = set(target_columns)
    saved = []
    for item in parsed["suggestions"]:
        if item["column_name"] not in target_set:
            continue  # ignore anything hallucinated outside the requested column set
        mapping = upsert_mapping(
            db,
            dataset,
            column_name=item["column_name"],
            display_name=item["display_name"],
            description=item.get("description"),
            unit=item.get("unit"),
        )
        saved.append(mapping)

    return saved, list(existing.keys())
