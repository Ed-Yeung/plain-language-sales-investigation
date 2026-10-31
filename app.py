import os
import tempfile

import pandas as pd
import plotly.io as pio
import streamlit as st

from calculator import calculate_custom_metric
from custom_store import add_metric, delete_metric, load_metrics, set_use_for_insights
from data_io import DataLoadError, load_dataframe
from graph import build_graph
from state import initial_state

METHOD_LABELS = {
    "sum": "Sum of values",
    "mean": "Average of values",
    "count": "Count of non-empty rows",
    "count_distinct": "Count of unique values",
}
METHOD_SHORT = {
    "sum": "sum",
    "mean": "average",
    "count": "count",
    "count_distinct": "unique count",
}


st.set_page_config(page_title="Data Analyst multi-agents", page_icon="📊", layout="wide")
st.title("Data Analyst multi-agents")
st.caption(
    "Upload a CSV. Four agents (Explorer, Planner, Coder, Writer) analyze it. "
    "Custom metrics you save are calculated by the app, not by the model."
)


@st.cache_resource
def get_app():
    return build_graph()


graph = get_app()


def remember_columns(uploaded) -> list[str]:
    frame = pd.read_csv(uploaded, nrows=20)
    uploaded.seek(0)
    columns = [str(column) for column in frame.columns]
    st.session_state["csv_columns"] = columns
    return columns


def formula_text(parts: list[dict], combine: str, group_by: list[str]) -> str:
    labels = [f"{METHOD_SHORT[part['method']]}({part['column']})" for part in parts]
    if combine == "divide":
        text = f"{labels[0]} / {labels[1]}"
    elif combine == "subtract":
        text = f"{labels[0]} - {labels[1]}"
    elif combine == "add":
        text = " + ".join(labels)
    elif combine == "subtract_over":
        text = f"({labels[0]} - {labels[1]}) / {labels[2]}"
    elif combine == "over_sum":
        text = f"{labels[0]} / ({labels[1]} + {labels[2]})"
    else:
        text = labels[0]
    if group_by:
        text += f", split by {', '.join(group_by)}"
    return text


def _formula(metric: dict) -> str:
    parts = metric.get("parts") or []
    if parts:
        return formula_text(parts, metric.get("combine") or "value", metric.get("group_by") or [])
    group_by = metric.get("group_by") or []
    group = f", split by {', '.join(group_by)}" if group_by else ""
    agg = metric.get("aggregation")
    if agg in METHOD_SHORT:
        return f"{METHOD_SHORT[agg]}({metric.get('column')}){group}"
    if agg == "ratio_of_sums":
        return f"sum({metric.get('numerator')}) / sum({metric.get('denominator')}){group}"
    if agg == "aov":
        return f"sum({metric.get('revenue_column')}) / unique count({metric.get('order_column')}){group}"
    return str(agg or "metric")


def render_saved_metrics() -> None:
    metrics = load_metrics()
    if not metrics:
        st.info("No custom metrics yet.")
        return

    st.subheader("Saved metrics")
    for metric in metrics:
        use_key = f"use_metric_{metric['id']}"
        if use_key not in st.session_state:
            st.session_state[use_key] = bool(metric.get("use_for_insights"))

        info, toggle, remove = st.columns([4, 1.6, 0.8])
        with info:
            st.markdown(f"**{metric['name']}**")
            if metric.get("description"):
                st.caption(metric["description"])
            st.caption(_formula(metric))
        with toggle:
            checked = st.checkbox("Use for insights", key=use_key)
        with remove:
            if st.button("Delete", key=f"del_metric_{metric['id']}"):
                delete_metric(metric["id"])
                st.rerun()

        if checked != bool(metric.get("use_for_insights")):
            set_use_for_insights(metric["id"], checked)
            st.rerun()


def render_metric_form() -> None:
    st.subheader("Add a custom metric")
    st.caption("Pick columns from your CSV. You do not write a formula.")

    columns = st.session_state.get("csv_columns") or []
    if not columns:
        sample = st.file_uploader(
            "Upload a CSV first, so the column list can be filled in",
            type="csv",
            key="metric_column_csv",
        )
        if sample is not None:
            remember_columns(sample)
            st.rerun()
        return

    st.caption("Columns: " + ", ".join(columns))

    name = st.text_input("Metric name", placeholder="Profit margin by category")
    description = st.text_area("What does this number mean?", placeholder="Total profit divided by total sales")

    st.markdown("**1. Choose the columns to calculate**")
    count = st.radio(
        "How many columns?",
        [1, 2, 3],
        horizontal=True,
        format_func=lambda n: {
            1: "1 — one number",
            2: "2 — then combine",
            3: "3 — then combine",
        }[n],
    )

    parts = []
    for index in range(count):
        left, right = st.columns(2)
        column = left.selectbox(f"Column {index + 1}", columns, key=f"metric_col_{index}")
        method = right.selectbox(
            f"Calculate column {index + 1} as",
            list(METHOD_LABELS),
            format_func=lambda key: METHOD_LABELS[key],
            key=f"metric_method_{index}",
        )
        parts.append({"column": column, "method": method})

    combine = "value"
    if count == 1:
        st.caption("One column: the metric is just that calculation. Nothing else to combine.")
    else:
        st.markdown("**2. Combine those results**")
        if count == 2:
            options = {
                "divide": "Divide — column 1 ÷ column 2",
                "subtract": "Subtract — column 1 − column 2",
                "add": "Add — column 1 + column 2",
            }
        else:
            options = {
                "add": "Add all — column 1 + column 2 + column 3",
                "subtract_over": "(column 1 − column 2) ÷ column 3",
                "over_sum": "column 1 ÷ (column 2 + column 3)",
            }
        combine = st.selectbox(
            "How should the column results be combined?",
            list(options),
            format_func=lambda key: options[key],
        )

    st.markdown("**3. Split by a group? Optional**")
    st.caption("Leave empty for one number for the whole file. Example: choose Category to get one number per category.")
    group_by = st.multiselect("Group by", columns)

    st.info("This metric will calculate: " + formula_text(parts, combine, group_by))
    use_for_insights = st.checkbox("Use this metric for insights", value=True)

    if st.button("Save metric"):
        cleaned = name.strip()
        if not cleaned:
            st.error("Name is required.")
            return
        if any(item["name"].strip().lower() == cleaned.lower() for item in load_metrics()):
            st.error("A metric with this name already exists.")
            return
        add_metric({
            "name": cleaned,
            "description": description.strip(),
            "parts": parts,
            "combine": combine,
            "group_by": group_by,
            "use_for_insights": use_for_insights,
        })
        st.success(f"Saved '{cleaned}'.")
        st.rerun()


def compute_selected_metrics(csv_path: str) -> list[dict]:
    selected = [metric for metric in load_metrics() if metric.get("use_for_insights")]
    if not selected:
        return []
    frame = load_dataframe(csv_path)
    return [calculate_custom_metric(frame, metric) for metric in selected]


def render_metric_results(results: list[dict]) -> None:
    if not results:
        return
    st.subheader("Custom metrics")
    st.caption("These numbers were calculated by the app from the saved definitions.")
    for result in results:
        st.markdown(f"**{result.get('name')}**")
        if result.get("description"):
            st.caption(result["description"])
        if result.get("status") != "success":
            st.error(result.get("message", "Calculation failed"))
            continue
        if result.get("rows") is not None:
            st.dataframe(pd.DataFrame(result["rows"]), use_container_width=True)
        else:
            value = result.get("value")
            st.write("Undefined (division by zero)." if value is None else value)


tab_analysis, tab_metrics = st.tabs(["Analysis", "Custom metrics"])

with tab_metrics:
    render_saved_metrics()
    render_metric_form()

with tab_analysis:
    enabled = [metric for metric in load_metrics() if metric.get("use_for_insights")]
    if enabled:
        st.caption("Insights will include: " + ", ".join(metric["name"] for metric in enabled))
    else:
        st.caption("No custom metric is marked for insights. Chart analysis still runs.")

    uploaded = st.file_uploader("Choose a CSV file", type="csv")
    if uploaded is not None:
        remember_columns(uploaded)

    run = st.button("Start the analysis", disabled=(uploaded is None))

    if run and uploaded is not None:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as tmp:
            tmp.write(uploaded.getbuffer())
            csv_path = tmp.name

        try:
            metric_results = compute_selected_metrics(csv_path)
            final_state, seen = None, set()
            with st.status("Multi-agent analysis in progress...", expanded=True) as status:
                state0 = initial_state(csv_path)
                state0["custom_metric_results"] = metric_results
                for snap in graph.stream(state0, stream_mode="values"):
                    final_state = snap

                    if snap.get("data_summary") and "exp" not in seen:
                        seen.add("exp")
                        summary = snap["data_summary"]
                        st.write(
                            "Data exploration complete: "
                            f"{summary['n_rows']} rows, {summary['n_cols']} columns"
                        )
                        with st.expander("Dataset summary"):
                            st.write(f"**Numerical columns:** {summary['numerical_columns']}")
                            st.write(f"**Categorical columns:** {summary['categorical_columns']}")
                            st.write(f"**Date columns:** {summary['datetime_columns']}")
                            missing = summary.get("missing_value") or {}
                            if missing:
                                st.write(f"**Missing values:** {missing}")

                    if snap.get("plan") and "plan" not in seen:
                        seen.add("plan")
                        plan = snap["plan"]
                        st.write(f"Plan ready: {len(plan)} analyses")
                        with st.expander("Analysis plan"):
                            for i, task in enumerate(plan, start=1):
                                st.markdown(
                                    f"**{i}. {task['title']}**\n\n"
                                    f"- Chart: `{task['chart_type']}`\n"
                                    f"- Columns: {task['columns']}\n"
                                    f"- Why: {task.get('rationale', '-')}"
                                )

                    if (snap.get("figures") or snap.get("error")) and "code" not in seen:
                        seen.add("code")
                        if snap.get("error") and not snap.get("figures"):
                            st.write("Code generation failed after the retry limit")
                        else:
                            st.write("Code generated and executed")

                    if snap.get("insights") and "writ" not in seen:
                        seen.add("writ")
                        st.write("Insights written")

                status.update(label="Analysis complete", state="complete")

            st.session_state["result"] = final_state

        except DataLoadError as exc:
            st.error(f"Problem with the file: {exc}")
        except Exception as exc:
            st.error(f"The analysis failed: {exc}")
            st.info("Check the API key in .env and the server logs.")
        finally:
            os.unlink(csv_path)

    result = st.session_state.get("result")
    if result:
        render_metric_results(result.get("custom_metric_results") or [])

        figures = result.get("figures") or []
        if figures:
            st.subheader(f"Charts ({len(figures)})")
            for fig_json in figures:
                fig = pio.from_json(fig_json)
                st.plotly_chart(fig, use_container_width=True)

        st.subheader("Insights")
        st.markdown(result.get("insights") or "_(no insights)_")