import pandas as pd
import pytest

from app.models.alert_history import AlertHistory
from app.models.alert_rule import AlertRule
from app.services.anomaly_service import check_statistical, check_threshold, evaluate_alert_rule, run_alerts_for_dataset
from app.tests.conftest import create_owned_dataset, create_user


@pytest.fixture
def df():
    return pd.DataFrame({"revenue": [100.0, 200.0, 300.0, None], "region": ["W", "E", "W", "E"]})


class TestCheckThreshold:
    def test_gt_triggers_when_value_exceeds_threshold(self, df):
        triggered, value = check_threshold(df, "revenue", "sum", "gt", 500)
        assert value == 600.0
        assert triggered is True

    def test_gt_does_not_trigger_when_value_below_threshold(self, df):
        triggered, value = check_threshold(df, "revenue", "sum", "gt", 1000)
        assert triggered is False

    def test_lt_condition(self, df):
        triggered, value = check_threshold(df, "revenue", "mean", "lt", 1000)
        assert value == 200.0
        assert triggered is True

    def test_eq_condition(self, df):
        triggered, value = check_threshold(df, "revenue", "max", "eq", 300)
        assert triggered is True

    def test_count_metric_counts_only_non_null(self, df):
        triggered, value = check_threshold(df, "revenue", "count", "eq", 3)
        assert value == 3.0
        assert triggered is True

    def test_unknown_column_raises(self, df):
        with pytest.raises(ValueError, match="not found"):
            check_threshold(df, "nope", "sum", "gt", 0)

    def test_non_numeric_column_raises(self, df):
        with pytest.raises(ValueError, match="no numeric values"):
            check_threshold(df, "region", "sum", "gt", 0)

    def test_unsupported_metric_raises(self, df):
        with pytest.raises(ValueError, match="Unsupported metric"):
            check_threshold(df, "revenue", "median", "gt", 0)


class TestCheckStatistical:
    def test_not_enough_history_never_triggers(self, df):
        triggered, value, z_score = check_statistical(df, "revenue", "sum", 2.0, history=[500.0, 550.0])
        assert triggered is False
        assert z_score is None
        assert value == 600.0

    def test_zero_variance_history_never_triggers(self, df):
        history = [500.0] * 10
        triggered, value, z_score = check_statistical(df, "revenue", "sum", 2.0, history=history)
        assert triggered is False
        assert z_score is None

    def test_outlier_beyond_z_threshold_triggers(self, df):
        # Tight, stable history around 500-520; today's 600 is a real outlier.
        history = [500.0, 505.0, 495.0, 510.0, 500.0, 502.0, 498.0, 500.0, 501.0, 499.0]
        triggered, value, z_score = check_statistical(df, "revenue", "sum", 2.0, history=history)
        assert value == 600.0
        assert z_score is not None
        assert triggered is True

    def test_value_within_normal_range_does_not_trigger(self, df):
        history = [590.0, 610.0, 595.0, 605.0, 600.0, 598.0, 602.0, 600.0, 601.0, 599.0]
        triggered, value, z_score = check_statistical(df, "revenue", "sum", 2.0, history=history)
        assert triggered is False

    def test_only_most_recent_rolling_window_used(self, df):
        # 10 old, wildly different values followed by exactly
        # ROLLING_WINDOW=30 recent, tight ones — history[-30:] should
        # pick up only the 30 recent entries and none of the stale ones,
        # so today's 600 still reads as a clean outlier against them.
        old = [10_000.0] * 10
        recent = [500.0, 505.0, 495.0, 510.0, 500.0, 502.0, 498.0, 500.0, 501.0, 499.0] * 3
        assert len(recent) == 30
        triggered, value, z_score = check_statistical(df, "revenue", "sum", 2.0, history=old + recent)
        assert triggered is True


def _make_rule(db, dataset, **overrides) -> AlertRule:
    fields = dict(
        workspace_id=dataset.workspace_id,
        created_by=dataset.user_id,
        name="Test rule",
        dataset_id=dataset.id,
        column="revenue",
        metric="sum",
        condition="gt",
        threshold=100.0,
        use_statistical=False,
        z_score_threshold=2.0,
        frequency="on_upload",
        recipients=["ops@example.com"],
        is_active=True,
    )
    fields.update(overrides)
    rule = AlertRule(**fields)
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


class TestEvaluateAlertRule:
    def test_threshold_only_when_use_statistical_false(self, db):
        dataset = create_owned_dataset(db)
        rule = _make_rule(db, dataset, use_statistical=False)
        df = pd.DataFrame({"revenue": [100.0, 200.0, 300.0]})

        results = evaluate_alert_rule(rule, df, db)

        assert len(results) == 1
        assert results[0]["alert_type"] == "threshold"
        assert results[0]["triggered"] is True  # sum=600 > threshold=100

    def test_statistical_check_added_when_enabled_using_real_history(self, db):
        dataset = create_owned_dataset(db)
        rule = _make_rule(db, dataset, use_statistical=True, z_score_threshold=2.0)

        # 10 stable past threshold-check rows (oldest first isn't
        # required here — evaluate_alert_rule/check_statistical only
        # needs enough rows to clear MIN_HISTORY_FOR_STATISTICAL).
        for value in [500.0, 505.0, 495.0, 510.0, 500.0, 502.0, 498.0, 500.0, 501.0, 499.0]:
            db.add(AlertHistory(alert_rule_id=rule.id, triggered=False, actual_value=value, z_score=None, alert_type="threshold"))
        db.commit()

        df = pd.DataFrame({"revenue": [1000.0]})  # today's sum is a sharp outlier vs. ~500 history
        results = evaluate_alert_rule(rule, df, db)

        assert len(results) == 2
        assert results[1]["alert_type"] == "statistical"
        assert results[1]["triggered"] is True
        assert results[1]["z_score"] is not None


class TestRunAlertsForDataset:
    def test_no_rules_returns_empty_list(self, db):
        dataset = create_owned_dataset(db)
        assert run_alerts_for_dataset(dataset.id, db) == []

    def test_skips_rule_whose_creator_lost_workspace_access(self, db):
        dataset = create_owned_dataset(db)
        outsider = create_user(db)  # never added as a member of dataset's workspace
        _make_rule(db, dataset, created_by=outsider.id)

        # Would raise FileNotFoundError trying to actually load the
        # dataset's file if it got that far — it must not, since
        # get_dataset_for_user raises PermissionError first and the
        # rule is skipped before any file read is attempted.
        results = run_alerts_for_dataset(dataset.id, db)
        assert results == []
