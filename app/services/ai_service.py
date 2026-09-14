# WHY THIS FILE EXISTS:
# Orchestrator/Façade, same shape as report_service.py (Day 10) — it
# doesn't compute anything itself. It builds a dataset schema summary,
# gets a structured query back from the model, delegates execution to
# analytics_service.execute_structured_query(), and formats the result
# into plain English. All pandas logic stays in analytics_service.py.
#
# PRIVACY NOTE: the dataset summary sent to the model contains no actual
# cell values — column names, dtypes, numeric min/max/mean/median, and
# categorical unique-value *counts* only. Filter values used in a query
# come from the user's own question text, not from anything we tell the
# model about the dataset, and are validated against the real data
# locally in analytics_service.py, not trusted from the model's output.

import json
import os

import pandas as pd
from dotenv import load_dotenv
from openai import OpenAI

from app.services.analytics_service import execute_structured_query
from app.services.storage_service import load_dataframe

load_dotenv()

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    return _client


QUERY_SCHEMA = {
    "type": "object",
    "properties": {
        "operation": {
            "type": "string",
            "enum": ["groupby", "filter", "sort", "aggregate", "correlate"],
        },
        "column": {"type": ["string", "null"]},
        "metric": {"type": ["string", "null"]},
        "aggregate": {"type": "string", "enum": ["sum", "mean", "count", "max", "min"]},
        "filter_value": {"type": ["string", "null"]},
        "filter_operator": {"type": "string", "enum": ["eq", "gt", "gte", "lt", "lte"]},
        "limit": {"type": "integer"},
        "direction": {"type": "string", "enum": ["asc", "desc"]},
        "explanation": {"type": "string"},
    },
    "required": [
        "operation",
        "column",
        "metric",
        "aggregate",
        "filter_value",
        "filter_operator",
        "limit",
        "direction",
        "explanation",
    ],
    "additionalProperties": False,
}

SYSTEM_PROMPT = """You are a data query parser for InsightAI. Given a dataset's \
schema (column names, types, and statistics only — no actual row values) \
and a user's natural-language question, output a single structured query \
describing how to answer it from the dataset.

Rules:
- "column" and "metric", when used, must be real column names taken from \
the dataset schema you're given. Never invent a column name.
- Match column names holistically against the schema's actual column list. \
Don't strip words like "total", "average", or "sum" from the question \
before matching — the real column may itself be named "Total Revenue" or \
"Total Profit", in which case that whole phrase is the column name, not an \
aggregation instruction to apply on top of a shorter column name that \
doesn't exist.
- Required fields per operation:
  - "groupby": "column" (the category to group by) and "metric" (the \
numeric column to aggregate with "aggregate"). Use this — not "sort" — \
whenever the question asks to rank or compare *categories* by a value \
(e.g. "top 3 regions by revenue" groups by region and sums revenue; it is \
not a row-level sort).
  - "filter": "column" and "filter_value". Set "filter_operator" to \
match the comparison the question describes — "eq" for "is"/"equals"/a \
named category (e.g. "from Europe"), "gt"/"gte"/"lt"/"lte" for \
"above"/"at least"/"below"/"at most" a numeric threshold (e.g. "orders \
above 500" is filter_operator "gt", filter_value "500", column the \
numeric field being thresholded). If the question also asks for a \
computed number among the matches (e.g. "total revenue from Europe", "how \
many orders from Europe", "average delivery time for orders above 500") \
rather than just "show me the matching rows", also set "metric" (numeric \
column, or the column itself for a plain count) and "aggregate" \
accordingly.
  - "sort": "metric" (or "column" if no numeric field is being ranked) — \
the field individual *rows* are ranked by. Use this only for row-level \
ranking, not for ranking categories/groups (use "groupby" for that).
  - "aggregate": "metric" and "aggregate" — a single computed value over \
the whole dataset, no grouping or filtering.
  - "correlate": both "column" and "metric" must be set to the two numeric \
columns being compared. This operation is meaningless with either one \
missing — never leave both null when the question names two columns.
- For "filter", set "filter_value" to the value mentioned in the question, \
exactly as the user wrote it. It does not need to match the schema — it is \
validated separately against the real data after you respond.
- Every field must still be present even when an operation doesn't use it. \
Use JSON null for an unused "column", "metric", or "filter_value" — never \
the placeholder text "null", "none", or an empty string. Use "sum" as the \
harmless placeholder for an unused "aggregate", and "eq" as the harmless \
placeholder for an unused "filter_operator".
- "limit" defaults to 10 unless the question specifies a different number.
- "direction" defaults to "desc" ("top", "highest", "most") unless the \
question asks for the lowest/smallest/bottom values, in which case use \
"asc".
- "explanation" is one sentence describing what the query does, written \
before you see the result.
"""


def _build_dataset_context(df: pd.DataFrame) -> dict:
    columns = []
    for col in df.columns:
        entry: dict = {"name": col, "dtype": str(df[col].dtype)}
        if pd.api.types.is_numeric_dtype(df[col]):
            series = df[col].dropna()
            if len(series):
                entry["min"] = round(float(series.min()), 2)
                entry["max"] = round(float(series.max()), 2)
                entry["mean"] = round(float(series.mean()), 2)
                entry["median"] = round(float(series.median()), 2)
        else:
            entry["unique_count"] = int(df[col].nunique())
        columns.append(entry)
    return {"row_count": len(df), "columns": columns}


def _format_answer(query: dict, result: dict) -> str:
    operation = result["operation"]
    explanation = (query.get("explanation") or "").strip()

    if operation == "groupby":
        records = result["records"]
        if not records:
            body = "No matching records were found."
        else:
            column, metric = query["column"], query["metric"]
            parts = [f"{r[column]}: {r[metric]:,.2f}" for r in records]
            body = f"{query['aggregate']} of {metric} by {column} — " + ", ".join(parts) + "."

    elif operation == "filter":
        if "value" in result:
            value = result["value"]
            formatted_value = f"{value:,}" if result["aggregate"] == "count" else f"{value:,.2f}"
            symbol = {"eq": "=", "gt": ">", "gte": ">=", "lt": "<", "lte": "<="}.get(
                result.get("filter_operator", "eq"), "="
            )
            body = (
                f"{result['aggregate']} of {result['metric']} where "
                f"{result['column']} {symbol} {result['filter_value']}: {formatted_value} "
                f"(across {result['row_count']:,} matching records)."
            )
        else:
            row_count = result["row_count"]
            body = f"Found {row_count} matching record{'s' if row_count != 1 else ''}."

    elif operation == "sort":
        row_count = result["row_count"]
        body = f"Returning {row_count} record{'s' if row_count != 1 else ''}."

    elif operation == "aggregate":
        value = result["value"]
        formatted_value = f"{int(value):,}" if query["aggregate"] == "count" else f"{value:,.2f}"
        body = (
            f"{query['aggregate']} of {query['metric']}: {formatted_value} "
            f"(across {result['row_count']:,} records)."
        )

    elif operation == "correlate":
        corr = result["correlation"]
        if corr is None:
            body = f"Correlation between {query['column']} and {query['metric']} could not be computed."
        else:
            strength = "strong" if abs(corr) >= 0.7 else "moderate" if abs(corr) >= 0.3 else "weak"
            direction = "positive" if corr >= 0 else "negative"
            body = (
                f"Correlation between {query['column']} and {query['metric']}: "
                f"{corr} ({strength} {direction})."
            )

    else:
        body = ""

    return f"{explanation} {body}".strip()


def answer_query(dataset, question: str) -> dict:
    df = load_dataframe(dataset.file_path)
    return answer_query_for_df(df, question)


def answer_query_for_df(df: pd.DataFrame, question: str) -> dict:
    """
    Same pipeline as answer_query(), operating directly on an in-memory
    DataFrame rather than loading one from a Dataset row's storage. Used
    by the joins feature (Day 17) to run a question against an
    already-joined result — the model never sees or performs the join
    itself, only this already-computed DataFrame.
    """
    context = _build_dataset_context(df)

    client = _get_client()
    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        temperature=0,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": json.dumps({"dataset_schema": context, "question": question}),
            },
        ],
        response_format={
            "type": "json_schema",
            "json_schema": {"name": "structured_query", "strict": True, "schema": QUERY_SCHEMA},
        },
    )

    raw = response.choices[0].message.content
    if not raw:
        raise ValueError("Model returned no output for this question.")
    query = json.loads(raw)

    result = execute_structured_query(df, query)
    answer = _format_answer(query, result)

    return {
        "answer": answer,
        "data": result,
        "query_used": query,
        "tokens_used": response.usage.total_tokens if response.usage else 0,
    }
