# WHY THIS FILE EXISTS:
# Two independent checks per rule, same shape as everywhere else in
# this app splits "pure computation" from "orchestration" (see
# analytics_service.py). check_threshold/check_statistical take an
# already-loaded DataFrame and do no I/O; evaluate_alert_rule and
# run_alerts_for_dataset own the DB/storage access.
#
# STATISTICAL CHECK DESIGN (see ADR-015 for the full reasoning): a
# single dataset snapshot only ever gives one aggregate scalar — there's
# no distribution to z-score it against within one snapshot. So
# check_statistical compares today's aggregate(column, metric) against
# a rolling window of this *same rule's* past evaluations (from
# AlertHistory), not against this dataset's own rows. That needs a
# representative sample of ordinary past values, not just past
# triggers — which is why AlertHistory logs every evaluation, not only
# the ones that fired (see app/models/alert_history.py).

from typing import Optional

import pandas as pd
from sqlalchemy.orm import Session

MIN_HISTORY_FOR_STATISTICAL = 10
ROLLING_WINDOW = 30

_CONDITIONS = {
    "gt": lambda value, threshold: value > threshold,
    "lt": lambda value, threshold: value < threshold,
    "gte": lambda value, threshold: value >= threshold,
    "lte": lambda value, threshold: value <= threshold,
    "eq": lambda value, threshold: value == threshold,
}


def _aggregate(df: pd.DataFrame, column: str, metric: str) -> float:
    if column not in df.columns:
        raise ValueError(f"Column '{column}' not found in dataset.")
    series = pd.to_numeric(df[column], errors="coerce").dropna()
    if series.empty:
        raise ValueError(f"Column '{column}' has no numeric values to evaluate.")
    if metric == "count":
        return float(len(series))
    if metric not in ("mean", "sum", "max", "min"):
        raise ValueError(f"Unsupported metric: {metric}")
    return round(float(getattr(series, metric)()), 4)


def check_threshold(df: pd.DataFrame, column: str, metric: str, condition: str, threshold: float) -> tuple[bool, float]:
    value = _aggregate(df, column, metric)
    triggered = _CONDITIONS[condition](value, threshold)
    return triggered, value


def check_statistical(
    df: pd.DataFrame, column: str, metric: str, z_score_threshold: float, history: list[float]
) -> tuple[bool, float, Optional[float]]:
    """
    `history` is this rule's past threshold-check actual_values, most
    recent last (see evaluate_alert_rule) — every evaluation produces
    exactly one threshold-type row, so that's the guaranteed-complete
    time series regardless of whether use_statistical was on in the
    past. Returns (triggered, current_value, z_score) — z_score is None
    when there isn't enough history yet to compute one.
    """
    value = _aggregate(df, column, metric)

    if len(history) < MIN_HISTORY_FOR_STATISTICAL:
        return False, value, None

    window = pd.Series(history[-ROLLING_WINDOW:])
    mean, std = window.mean(), window.std()
    if std == 0 or pd.isna(std):
        return False, value, None

    z_score = round(float((value - mean) / std), 4)
    triggered = abs(z_score) > z_score_threshold
    return triggered, value, z_score


def evaluate_alert_rule(rule, df: pd.DataFrame, db: Session) -> list[dict]:
    """
    Runs the threshold check (always) and, if rule.use_statistical, the
    statistical check too — up to two entries in the returned list, one
    per check performed (not just the triggered ones; the caller decides
    what to persist/email). Each entry:
    {alert_type, triggered, actual_value, z_score}.
    """
    from app.models.alert_history import AlertHistory

    results = []

    triggered, value = check_threshold(df, rule.column, rule.metric, rule.condition, rule.threshold)
    results.append({"alert_type": "threshold", "triggered": triggered, "actual_value": value, "z_score": None})

    if rule.use_statistical:
        history_rows = (
            db.query(AlertHistory.actual_value)
            .filter(AlertHistory.alert_rule_id == rule.id, AlertHistory.alert_type == "threshold")
            .order_by(AlertHistory.checked_at.desc())
            .limit(ROLLING_WINDOW)
            .all()
        )
        history = [row[0] for row in reversed(history_rows)]  # oldest first

        triggered_stat, value_stat, z_score = check_statistical(
            df, rule.column, rule.metric, rule.z_score_threshold, history
        )
        results.append(
            {"alert_type": "statistical", "triggered": triggered_stat, "actual_value": value_stat, "z_score": z_score}
        )

    return results


def run_alerts_for_dataset(dataset_id: int, db: Session, frequency_filter: tuple[str, ...] = ("on_upload", "both")) -> list[dict]:
    """
    Evaluates every active AlertRule watching `dataset_id` whose
    frequency is in `frequency_filter`. Returns one dict per check
    performed across all matching rules:
    {rule, alert_type, triggered, actual_value, z_score}.
    Loads the dataset once, reused across every rule that watches it.
    """
    from app.models.alert_rule import AlertRule
    from app.services.access_control import get_dataset_for_user
    from app.services.storage_service import load_dataframe

    rules = (
        db.query(AlertRule)
        .filter(
            AlertRule.dataset_id == dataset_id,
            AlertRule.is_active.is_(True),
            AlertRule.frequency.in_(frequency_filter),
        )
        .all()
    )
    if not rules:
        return []

    df = None
    all_results = []

    for rule in rules:
        try:
            dataset = get_dataset_for_user(db, dataset_id, rule.created_by)
        except (ValueError, PermissionError):
            # The rule creator no longer has access (e.g. removed from
            # the workspace since creating it) — skip this rule rather
            # than failing every other rule watching the same dataset.
            continue

        if df is None:
            df = load_dataframe(dataset.file_path)

        for result in evaluate_alert_rule(rule, df, db):
            all_results.append({"rule": rule, **result})

    return all_results
