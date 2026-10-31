import pandas as pd

COLUMN_METHODS = ("sum", "mean", "count", "count_distinct")
COMBINES = ("value", "divide", "subtract", "add", "subtract_over", "over_sum")

# Kept so older saved metrics still calculate.
LEGACY_AGGREGATIONS = (
    "sum",
    "mean",
    "count",
    "count_distinct",
    "ratio_of_sums",
    "aov",
)


def _clean(value):
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except TypeError:
        pass
    if hasattr(value, "item"):
        value = value.item()
    if isinstance(value, float):
        return round(value, 6)
    if isinstance(value, int) and not isinstance(value, bool):
        return int(value)
    return value


def _require_numeric(df: pd.DataFrame, column: str) -> None:
    if not pd.api.types.is_numeric_dtype(df[column]):
        raise ValueError(f"Column '{column}' must be numeric for sum or average")


def _aggregate(df: pd.DataFrame, column: str, method: str):
    if method == "sum":
        _require_numeric(df, column)
        return df[column].sum()
    if method == "mean":
        _require_numeric(df, column)
        return df[column].mean()
    if method == "count":
        return df[column].count()
    if method == "count_distinct":
        return df[column].nunique(dropna=True)
    raise ValueError(f"Unsupported column calculation: {method}")


def _combine(values: list, combine: str):
    first = values[0]
    if combine == "value":
        return _clean(first)
    second = values[1]
    if combine == "divide":
        if second == 0 or pd.isna(second):
            return None
        return _clean(first / second)
    if combine == "subtract":
        return _clean(first - second)
    if combine == "add":
        total = first
        for value in values[1:]:
            total = total + value
        return _clean(total)
    third = values[2]
    if combine == "subtract_over":
        if third == 0 or pd.isna(third):
            return None
        return _clean((first - second) / third)
    if combine == "over_sum":
        denominator = second + third
        if denominator == 0 or pd.isna(denominator):
            return None
        return _clean(first / denominator)
    raise ValueError(f"Unsupported combination: {combine}")


def _parts_value(df: pd.DataFrame, parts: list[dict], combine: str):
    values = [_aggregate(df, part["column"], part["method"]) for part in parts]
    return _combine(values, combine)


def _iter_groups(df: pd.DataFrame, group_by: list[str]):
    grouped = df.groupby(group_by, dropna=False)
    for key, part in grouped:
        if not isinstance(key, tuple):
            key = (key,)
        label = {column: _clean(value) for column, value in zip(group_by, key)}
        yield label, part


def _calculate_from_parts(df: pd.DataFrame, metric: dict) -> dict:
    result = {
        "id": metric.get("id"),
        "name": metric.get("name", "metric"),
        "description": metric.get("description", ""),
        "aggregation": metric.get("combine") or "value",
    }
    parts = metric.get("parts") or []
    combine = metric.get("combine") or ("value" if len(parts) == 1 else "")
    group_by = [c for c in (metric.get("group_by") or []) if c]

    if not parts:
        return {**result, "status": "error", "message": "Metric has no columns"}
    if combine not in COMBINES:
        return {**result, "status": "error", "message": f"Unsupported combination: {combine}"}
    if combine == "value" and len(parts) != 1:
        return {**result, "status": "error", "message": "A single result needs exactly one column"}
    if combine in ("divide", "subtract") and len(parts) != 2:
        return {**result, "status": "error", "message": "This combination needs exactly two columns"}
    if combine in ("subtract_over", "over_sum") and len(parts) != 3:
        return {**result, "status": "error", "message": "This combination needs exactly three columns"}
    if combine == "add" and len(parts) < 2:
        return {**result, "status": "error", "message": "Add needs at least two columns"}

    needed = [part.get("column") or "" for part in parts] + group_by
    if any(not column for column in needed):
        return {**result, "status": "error", "message": "Metric is missing a column name"}
    missing = [column for column in needed if column not in df.columns]
    if missing:
        return {**result, "status": "error", "message": f"Missing columns: {missing}"}

    if not group_by:
        return {**result, "status": "success", "value": _parts_value(df, parts, combine), "rows": None}

    rows = []
    for label, part in _iter_groups(df, group_by):
        rows.append({**label, "value": _parts_value(part, parts, combine)})
    return {**result, "status": "success", "value": None, "rows": rows}


def _legacy_required(metric: dict) -> list[str]:
    agg = metric.get("aggregation")
    if agg in ("sum", "mean", "count", "count_distinct"):
        return [metric.get("column") or ""]
    if agg == "ratio_of_sums":
        return [metric.get("numerator") or "", metric.get("denominator") or ""]
    if agg == "aov":
        return [metric.get("revenue_column") or "", metric.get("order_column") or ""]
    return []


def _legacy_scalar(df: pd.DataFrame, metric: dict):
    agg = metric["aggregation"]
    if agg in COLUMN_METHODS:
        return _clean(_aggregate(df, metric["column"], agg))
    if agg == "ratio_of_sums":
        return _parts_value(
            df,
            [
                {"column": metric["numerator"], "method": "sum"},
                {"column": metric["denominator"], "method": "sum"},
            ],
            "divide",
        )
    if agg == "aov":
        return _parts_value(
            df,
            [
                {"column": metric["revenue_column"], "method": "sum"},
                {"column": metric["order_column"], "method": "count_distinct"},
            ],
            "divide",
        )
    raise ValueError(f"Unsupported aggregation: {agg}")


def _legacy(df: pd.DataFrame, metric: dict) -> dict:
    result = {
        "id": metric.get("id"),
        "name": metric.get("name", "metric"),
        "description": metric.get("description", ""),
        "aggregation": metric.get("aggregation"),
    }
    aggregation = metric.get("aggregation")
    if aggregation not in LEGACY_AGGREGATIONS:
        return {**result, "status": "error", "message": f"Unsupported aggregation: {aggregation}"}

    group_by = [c for c in (metric.get("group_by") or []) if c]
    needed = _legacy_required(metric) + group_by
    if any(not column for column in _legacy_required(metric)):
        return {**result, "status": "error", "message": "Metric is missing a required column name"}
    missing = [column for column in needed if column not in df.columns]
    if missing:
        return {**result, "status": "error", "message": f"Missing columns: {missing}"}

    if not group_by:
        return {**result, "status": "success", "value": _legacy_scalar(df, metric), "rows": None}
    rows = []
    for label, part in _iter_groups(df, group_by):
        rows.append({**label, "value": _legacy_scalar(part, metric)})
    return {**result, "status": "success", "value": None, "rows": rows}


def calculate_custom_metric(df: pd.DataFrame, metric: dict) -> dict:
    """Compute one saved metric. Never executes user-written code."""
    try:
        if metric.get("parts"):
            return _calculate_from_parts(df, metric)
        return _legacy(df, metric)
    except Exception as exc:
        return {
            "id": metric.get("id"),
            "name": metric.get("name", "metric"),
            "description": metric.get("description", ""),
            "aggregation": metric.get("combine") or metric.get("aggregation"),
            "status": "error",
            "message": str(exc),
        }
