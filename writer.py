import json
import plotly.io as pio
import base64
import numpy as np

from langchain_core.messages import SystemMessage, HumanMessage

from state import AnalysisState
from config import get_llm


def _fmt(v):
    """Format a number; otherwise return it unchanged."""
    try:
        return f"{float(v):,.2f}"
    except (TypeError, ValueError):
        return str(v)


def _decode(v):
    """Decode a binary-encoded Plotly array into a list."""
    if isinstance(v, dict) and "bdata" in v:
        raw = base64.b64decode(v["bdata"])
        return np.frombuffer(raw, dtype=np.dtype(v["dtype"])).tolist()
    if v is None:
        return []
    return list(v)


def describe_figure(fig_json: str, max_points: int = 40) -> str:
    """Convert a Plotly figure (JSON) into a concise textual summary."""
    try:
        fig = pio.from_json(fig_json)
    except Exception:
        return "Unreadable figure"

    title = fig.layout.title.text if (fig.layout.title and fig.layout.title.text) else "No title"
    out = [f'Figure: "{title}"']

    for tr in fig.data:
        ttype = tr.type or "?"
        name = tr.name or ""
        x = _decode(getattr(tr, "x", None))
        y = _decode(getattr(tr, "y", None))
        labels = _decode(getattr(tr, "labels", None))
        values = _decode(getattr(tr, "values", None))

        if labels and values:
            pairs = "; ".join(f"{l}: {_fmt(v)}" for l, v in zip(labels, values))
            out.append(f"   (pie) {pairs}")
        elif x and y and len(x) <= max_points:
            pairs = "; ".join(f"{a}: {_fmt(b)}" for a, b in zip(x, y))
            out.append(f"   ({ttype}) {name} {pairs}".rstrip())
        elif x and y:
            try:
                ynum = [float(v) for v in y if v is not None]
                out.append(
                    f"({ttype}) {name} {len(x)} points; "
                    f"start {_fmt(y[0])}, end {_fmt(y[-1])}, "
                    f"min {_fmt(min(ynum))}, max {_fmt(max(ynum))}".rstrip()
                )
            except Exception:
                out.append(f"   ({ttype}) {name} {len(x)} points")
        elif x:
            out.append(f"   ({ttype}) {len(x)} values")
    return "\n ".join(out)


def format_metric_results(results: list, max_rows: int = 40) -> str:
    """Turn controlled metric results into text the writer may cite."""
    if not results:
        return ""
    lines = [
        "CUSTOM METRICS (already computed by the application; do not recalculate).",
        "A null value means the metric is undefined, for example division by zero.",
    ]
    for result in results:
        name = result.get("name", "metric")
        description = result.get("description") or result.get("aggregation") or ""
        if result.get("status") != "success":
            lines.append(f"- {name}: ERROR — {result.get('message', 'unknown error')}")
            continue
        if result.get("rows") is not None:
            rows = result["rows"]
            lines.append(f"- {name} ({description}):")
            for row in rows[:max_rows]:
                lines.append(f"    {json.dumps(row, ensure_ascii=False)}")
            if len(rows) > max_rows:
                lines.append(f"    ... {len(rows) - max_rows} more rows omitted")
        else:
            lines.append(f"- {name} ({description}): {result.get('value')}")
    return "\n".join(lines)


SYSTEM_PROMPT = """You are a data analyst. You write clear business insights in English.

RULES:
- Use ONLY the chart descriptions and custom metric results provided. Do NOT invent numbers.
- Custom metric values were computed by application code. Treat them as verified.
- If a metric value is null, say it is undefined. Do not replace it with zero.
- For each chart: 1 to 2 concrete insights (what we learn, not a description of the chart).
- If custom metrics are present, explain what they show, including grouped comparisons.
- Separate observed facts from guesses. If the data cannot explain a cause, say so.
- End with a short summary (2–3 sentences).
- Keep the writing professional and accessible."""


def writer_node(state: AnalysisState) -> dict:
    """Summarize charts and any verified custom metrics, then ask the LLM to write insights."""
    figures = state.get("figures") or []
    error = state.get("error")
    metric_text = format_metric_results(state.get("custom_metric_results") or [])

    if error and not figures and not metric_text:
        last = error.splitlines()[-1] if error else ""
        msg = (
            f"The automatic analysis failed after {state.get('retry_count', 0)} attempt(s). "
            f"No charts were produced.\nLast error: {last}"
        )
        print("[Writer] failed, no figures")
        return {"insights": msg}

    parts = []
    if error and not figures:
        last = error.splitlines()[-1] if error else ""
        parts.append(
            "Charts could not be generated after "
            f"{state.get('retry_count', 0)} attempt(s). Last error: {last}"
        )
    elif figures:
        digest_text = "\n\n".join(describe_figure(f) for f in figures)
        print("=== DIGEST SENT TO WRITER ===")
        print(digest_text)
        print("=== END DIGEST ===")
        parts.append("Generated charts:\n\n" + digest_text)

    if metric_text:
        parts.append(metric_text)

    llm = get_llm(temperature=0.5)
    resp = llm.invoke([
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content="\n\n".join(parts)),
    ])
    insights = resp.content
    print(f"[Writer] written insights ({len(insights)} characters)")
    return {"insights": insights}


if __name__ == "__main__":
    fail_state = {"error": "KeyError: 'Revenue'", "figures": [], "retry_count": 3, "custom_metric_results": []}
    print("=== Failed test ===")
    print(writer_node(fail_state)["insights"])

    fake_fig = json.dumps({
        "data": [{"type": "bar",
                  "x": ["West", "East", "Central", "South"],
                  "y": [725458, 678781, 501240, 391722]}],
        "layout": {"title": {"text": "Sales by region"}},
    })
    print("\n=== Success test ===")
    ok_state = {
        "error": None,
        "figures": [fake_fig],
        "retry_count": 1,
        "custom_metric_results": [{
            "status": "success",
            "name": "Profit margin",
            "description": "Total profit divided by total sales",
            "aggregation": "ratio_of_sums",
            "value": 0.12,
            "rows": None,
        }],
    }
    print(writer_node(ok_state)["insights"])

               