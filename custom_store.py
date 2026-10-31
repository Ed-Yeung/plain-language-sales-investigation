import json
import os
import uuid
from datetime import datetime, timezone

STORE_PATH = "custom_metrics.json"


def load_metrics() -> list[dict]:
    if not os.path.exists(STORE_PATH):
        return []
    with open(STORE_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        return []
    return data


def save_metrics(metrics: list[dict]) -> None:
    with open(STORE_PATH, "w", encoding="utf-8") as f:
        json.dump(metrics, f, ensure_ascii=False, indent=2)


def add_metric(metric: dict) -> dict:
    metrics = load_metrics()
    saved = {
        "id": uuid.uuid4().hex[:8],
        "name": metric["name"].strip(),
        "description": metric.get("description", "").strip(),
        "parts": metric.get("parts") or [],
        "combine": metric.get("combine") or "",
        "group_by": [c for c in metric.get("group_by") or [] if c],
        "use_for_insights": bool(metric.get("use_for_insights", False)),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "aggregation": metric.get("aggregation") or metric.get("combine") or "",
        "column": metric.get("column") or "",
        "numerator": metric.get("numerator") or "",
        "denominator": metric.get("denominator") or "",
        "revenue_column": metric.get("revenue_column") or "",
        "order_column": metric.get("order_column") or "",
    }
    metrics.append(saved)
    save_metrics(metrics)
    return saved


def delete_metric(metric_id: str) -> None:
    save_metrics([m for m in load_metrics() if m.get("id") != metric_id])


def set_use_for_insights(metric_id: str, enabled: bool) -> None:
    metrics = load_metrics()
    for metric in metrics:
        if metric.get("id") == metric_id:
            metric["use_for_insights"] = bool(enabled)
    save_metrics(metrics)