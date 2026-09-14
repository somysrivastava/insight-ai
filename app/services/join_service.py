# WHY THIS FILE EXISTS:
# Owns everything about turning a join request (dataset ids + aliases +
# join steps) into one pandas DataFrame: loading each dataset with the
# same access_control.py workspace check every other endpoint uses,
# confirming they all share one workspace (that becomes the join's
# scope), and executing the merge itself. ai_service.py then runs a
# question against the result via answer_query_for_df() — it never sees
# the individual datasets or performs the join.

from typing import Any

import pandas as pd
from sqlalchemy.orm import Session

from app.services.access_control import get_dataset_for_user
from app.services.storage_service import load_dataframe

_FLIP_TYPE = {"left": "right", "right": "left", "inner": "inner"}


def _as_dict(obj: Any) -> dict:
    return obj if isinstance(obj, dict) else obj.model_dump()


def load_and_validate_datasets(db: Session, user_id: int, dataset_refs: list) -> tuple[dict[str, pd.DataFrame], int]:
    """
    Loads every dataset referenced in a join, checking workspace access
    for each exactly as any other endpoint would (access_control.py) —
    a saved join's stored dataset ids get no special trust, checked
    fresh every time this runs. Every dataset in one join must belong to
    the same workspace; that workspace becomes the join's (and, if
    saved, the SavedJoin row's) scope.

    Returns ({alias: DataFrame}, workspace_id).
    """
    aliases_seen: set[str] = set()
    dataframes: dict[str, pd.DataFrame] = {}
    workspace_id = None

    for ref in dataset_refs:
        ref = _as_dict(ref)
        dataset_id, alias = ref["id"], ref["alias"]

        if "." in alias:
            raise ValueError(f"Alias '{alias}' cannot contain '.' — used internally as a column-name separator.")
        if alias in aliases_seen:
            raise ValueError(f"Duplicate alias '{alias}' — each dataset in a join needs a unique alias.")
        aliases_seen.add(alias)

        dataset = get_dataset_for_user(db, dataset_id, user_id)

        if workspace_id is None:
            workspace_id = dataset.workspace_id
        elif dataset.workspace_id != workspace_id:
            raise ValueError(
                "All datasets in a join must belong to the same workspace "
                f"(dataset {dataset_id} is in a different workspace than the others)."
            )

        dataframes[alias] = load_dataframe(dataset.file_path)

    return dataframes, workspace_id


def execute_join(dataframes: dict[str, pd.DataFrame], joins: list) -> pd.DataFrame:
    """
    Executes join steps in the given order. Each step must connect one
    already-merged alias to one not-yet-merged alias — a three-way join
    is two steps, the same shape as writing `FROM a JOIN b ON ... JOIN c
    ON ...` in SQL. A step's "new" alias may appear as either
    left_alias or right_alias; when it's left_alias, the pandas merge's
    left/right roles are the reverse of the step's own left/right, so
    both the `on` columns and the join `type` get flipped accordingly —
    otherwise a "left" join would silently keep rows from the wrong
    side whenever the new table happened to be written as left_alias.

    Every column is prefixed with its alias before merging
    ("orders.order_id", "delivery.order_id") — one consistent rule, no
    special-casing join keys, so a three-way merge never produces
    pandas' ambiguous stacked _x/_y suffixes.
    """
    if not joins:
        raise ValueError("At least one join step is required.")

    steps = [_as_dict(s) for s in joins]

    prefixed = {
        alias: df.rename(columns={c: f"{alias}.{c}" for c in df.columns})
        for alias, df in dataframes.items()
    }

    first_alias = steps[0]["left_alias"]
    if first_alias not in dataframes:
        raise ValueError(f"Join references unknown alias '{first_alias}'.")

    merged = prefixed[first_alias]
    merged_aliases = {first_alias}

    for step in steps:
        left_alias, right_alias = step["left_alias"], step["right_alias"]
        for a in (left_alias, right_alias):
            if a not in dataframes:
                raise ValueError(f"Join references unknown alias '{a}'.")

        if left_alias in merged_aliases and right_alias not in merged_aliases:
            anchor_side, new_alias = "left", right_alias
        elif right_alias in merged_aliases and left_alias not in merged_aliases:
            anchor_side, new_alias = "right", left_alias
        elif left_alias in merged_aliases and right_alias in merged_aliases:
            raise ValueError(
                f"Both '{left_alias}' and '{right_alias}' are already part of the join — "
                "additional conditions between already-joined datasets aren't supported."
            )
        else:
            raise ValueError(
                f"Join step connects '{left_alias}' and '{right_alias}', but neither is joined "
                "yet — reorder steps so each one connects to an already-included dataset."
            )

        raw_left, raw_right = dataframes[left_alias], dataframes[right_alias]
        for pair in step["on"]:
            if pair["left"] not in raw_left.columns:
                raise ValueError(f"Column '{pair['left']}' not found in dataset '{left_alias}'.")
            if pair["right"] not in raw_right.columns:
                raise ValueError(f"Column '{pair['right']}' not found in dataset '{right_alias}'.")

        step_type = step.get("type", "left")
        if anchor_side == "left":
            # pandas' left arg == `merged` == left_alias's data already; right arg == the new frame.
            merge_left_on = [f"{left_alias}.{pair['left']}" for pair in step["on"]]
            merge_right_on = [f"{right_alias}.{pair['right']}" for pair in step["on"]]
            merge_how = step_type
        else:
            # right_alias is the anchor (already `merged`), so it plays pandas' left role here —
            # the step's own left/right are reversed relative to pandas, so flip both.
            merge_left_on = [f"{right_alias}.{pair['right']}" for pair in step["on"]]
            merge_right_on = [f"{left_alias}.{pair['left']}" for pair in step["on"]]
            merge_how = _FLIP_TYPE[step_type]

        merged = merged.merge(prefixed[new_alias], left_on=merge_left_on, right_on=merge_right_on, how=merge_how)
        merged_aliases.add(new_alias)

    missing = set(dataframes.keys()) - merged_aliases
    if missing:
        raise ValueError(
            f"Dataset alias(es) {sorted(missing)} were never joined — every dataset must be "
            "connected via the joins list."
        )

    return merged
