from typing import TypedDict, Annotated, Optional, Any
import operator

class AnalysisState(TypedDict):
    csv_path: str
    data_summary: dict[str, Any]
    plan: list[dict]

    generated_code: str
    figures: list
    error: Optional[str]
    retry_count: int
    attempts_log: Annotated[list, operator.add]

    insights: str
    custom_metric_results: list


def initial_state(csv_path: str) -> AnalysisState:
    """Construct the initial state that will be passed to the graph."""
    return {
        "csv_path": csv_path,
        "data_summary": {},
        "plan": [],
        "generated_code": "",
        "figures": [],
        "error": None,
        "retry_count": 0,
        "attempts_log": [],
        "insights": "",
        "custom_metric_results": [],
    }