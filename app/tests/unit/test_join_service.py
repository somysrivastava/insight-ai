import pandas as pd
import pytest

from app.services.join_service import execute_join


@pytest.fixture
def orders():
    return pd.DataFrame({"order_id": [1, 2, 3], "customer_id": [10, 20, 30], "amount": [100, 200, 300]})


@pytest.fixture
def customers():
    return pd.DataFrame({"id": [10, 20], "name": ["Alice", "Bob"]})


@pytest.fixture
def deliveries():
    return pd.DataFrame({"order_id": [1, 2], "status": ["delivered", "pending"]})


def test_columns_are_alias_prefixed(orders, customers):
    dataframes = {"orders": orders, "customers": customers}
    joins = [{"left_alias": "orders", "right_alias": "customers", "on": [{"left": "customer_id", "right": "id"}], "type": "inner"}]
    result = execute_join(dataframes, joins)

    assert "orders.order_id" in result.columns
    assert "customers.name" in result.columns
    assert "order_id" not in result.columns  # unprefixed name must not survive


def test_inner_join_drops_unmatched_rows(orders, customers):
    dataframes = {"orders": orders, "customers": customers}
    joins = [{"left_alias": "orders", "right_alias": "customers", "on": [{"left": "customer_id", "right": "id"}], "type": "inner"}]
    result = execute_join(dataframes, joins)
    # order 3 (customer_id=30) has no matching customer -> dropped by inner join
    assert len(result) == 2
    assert set(result["orders.order_id"]) == {1, 2}


def test_left_join_keeps_unmatched_left_rows(orders, customers):
    dataframes = {"orders": orders, "customers": customers}
    joins = [{"left_alias": "orders", "right_alias": "customers", "on": [{"left": "customer_id", "right": "id"}], "type": "left"}]
    result = execute_join(dataframes, joins)
    assert len(result) == 3
    unmatched = result[result["orders.order_id"] == 3]
    assert pd.isna(unmatched["customers.name"].iloc[0])


def test_three_way_join_step_ordering_new_alias_as_right(orders, customers, deliveries):
    dataframes = {"orders": orders, "customers": customers, "deliveries": deliveries}
    joins = [
        {"left_alias": "orders", "right_alias": "customers", "on": [{"left": "customer_id", "right": "id"}], "type": "inner"},
        {"left_alias": "orders", "right_alias": "deliveries", "on": [{"left": "order_id", "right": "order_id"}], "type": "left"},
    ]
    result = execute_join(dataframes, joins)
    assert "deliveries.status" in result.columns
    assert len(result) == 2  # inner join already dropped order 3


def test_three_way_join_when_new_alias_is_left_side_of_step(orders, customers, deliveries):
    # Second step writes the not-yet-joined alias (deliveries) as
    # left_alias and the already-joined one (orders) as right_alias —
    # execute_join must flip pandas' left/right roles (and the join
    # type) accordingly rather than silently keeping the wrong side.
    dataframes = {"orders": orders, "customers": customers, "deliveries": deliveries}
    joins = [
        {"left_alias": "orders", "right_alias": "customers", "on": [{"left": "customer_id", "right": "id"}], "type": "inner"},
        {"left_alias": "deliveries", "right_alias": "orders", "on": [{"left": "order_id", "right": "order_id"}], "type": "right"},
    ]
    result = execute_join(dataframes, joins)
    assert "deliveries.status" in result.columns
    assert len(result) == 2


def test_no_joins_raises():
    with pytest.raises(ValueError, match="At least one join step"):
        execute_join({"a": pd.DataFrame({"x": [1]})}, [])


def test_unknown_alias_in_first_step_raises(orders, customers):
    joins = [{"left_alias": "ghost", "right_alias": "customers", "on": [{"left": "customer_id", "right": "id"}], "type": "inner"}]
    with pytest.raises(ValueError, match="unknown alias"):
        execute_join({"orders": orders, "customers": customers}, joins)


def test_reordered_step_connecting_two_unjoined_aliases_raises(orders, customers, deliveries):
    # A 4th, otherwise-unrelated alias: step 1 anchors on {orders,
    # customers}; step 2 tries to connect {deliveries, extra} — neither
    # side is joined to the anchor yet, which is exactly the "reorder
    # your steps" case (distinct from an alias that's simply never
    # referenced by any step at all, covered separately below).
    extra = pd.DataFrame({"code": [1, 2]})
    dataframes = {"orders": orders, "customers": customers, "deliveries": deliveries, "extra": extra}
    joins = [
        {"left_alias": "orders", "right_alias": "customers", "on": [{"left": "customer_id", "right": "id"}], "type": "inner"},
        {"left_alias": "deliveries", "right_alias": "extra", "on": [{"left": "order_id", "right": "code"}], "type": "inner"},
    ]
    with pytest.raises(ValueError, match="neither is joined"):
        execute_join(dataframes, joins)


def test_missing_join_column_raises(orders, customers):
    joins = [{"left_alias": "orders", "right_alias": "customers", "on": [{"left": "nonexistent_col", "right": "id"}], "type": "inner"}]
    with pytest.raises(ValueError, match="Column 'nonexistent_col' not found"):
        execute_join({"orders": orders, "customers": customers}, joins)


def test_unjoined_alias_left_out_of_steps_raises(orders, customers, deliveries):
    # deliveries is present in dataframes but never referenced by any step.
    dataframes = {"orders": orders, "customers": customers, "deliveries": deliveries}
    joins = [{"left_alias": "orders", "right_alias": "customers", "on": [{"left": "customer_id", "right": "id"}], "type": "inner"}]
    with pytest.raises(ValueError, match="were never joined"):
        execute_join(dataframes, joins)


def test_accepts_pydantic_like_objects_via_model_dump():
    class FakeStep:
        def model_dump(self):
            return {"left_alias": "a", "right_alias": "b", "on": [{"left": "id", "right": "id"}], "type": "inner"}

    dataframes = {"a": pd.DataFrame({"id": [1, 2]}), "b": pd.DataFrame({"id": [1, 2], "val": ["x", "y"]})}
    result = execute_join(dataframes, [FakeStep()])
    assert "b.val" in result.columns
