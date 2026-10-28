# Sales Check

A store manager asks one plain-language question about sales. The app plans a short investigation, runs read-only queries against a DuckDB table, and returns charts plus an evidence-backed first answer. It is an initial check, not a replacement for a governed BI report.

## Use case

A non-technical store manager sees that a region looks weak and does not want to wait for the BI team before deciding what to look at. The manager types a question such as "Why is Kowloon down this week?" The app compares the latest seven days in the file with the seven days before them, then drills into the weakest region or category. The answer states the finding, the numbers behind it, the comparison, and what the data cannot explain.

The sample is a single retail chain, Lane & Co., with stores in Kowloon, Hong Kong Island, and New Territories. Categories are Beverage, Snacks, Household, and Fresh.

## Data

The page reads one DuckDB table, `sales`. There is no file upload.

| | |
|---|---|
| Grain | One row per day, region, and category |
| Rows | 1,416 |
| Dates | 1 Jul 2026 to 26 Oct 2026 |
| Columns | `date`, `year`, `month`, `weekday`, `region`, `category`, `sales`, `cost`, `units`, `orders` |

`data/sample_sales.csv` is only the source file. `python build_db.py` loads it into `data/sales.duckdb`. Rebuild only after the CSV changes.

"This week" is not a fixed date and not the calendar week on the computer. The app takes the latest date in the table, uses that day and the six days before it, and compares those seven days with the previous seven.

## Data flow

Question, then Explorer, Planner, Coder, Execute, and Writer.

- Explorer reads `sales` and records the columns, category values, and the two week windows.
- Planner turns the question into 1 to 3 steps, or refuses it.
- Coder writes one Python script for the current step.
- Execute runs that script against DuckDB and keeps the chart and the table.
- The next step repeats Coder, up to 3 rounds. A failed script is retried once.
- Writer writes the answer from those tables only.

## Logic

Explorer does not call the model. It profiles the table in Python. Planner calls DeepSeek and must return a structured plan: purpose, columns, chart type, and one instruction per step. A ranking is one step. A "why" question is two or three. A question that needs a missing field, such as weather or staff, is refused.

Coder calls DeepSeek once per step and returns one Python script. The script may only `SELECT` from `sales`, using a read-only connection. Profit margin is `SUM(sales - cost) / SUM(sales)`, not the average of row-level ratios. Execute checks the script, runs it in a temporary folder, and reads `fig0.json` and `result.json`. Writer sees the result tables, not the source rows. It uses four headings: Finding, Evidence, Comparison, and Limit.

The model chooses the comparison. Python executes it and checks the boundary.

## Stack

Python, LangGraph, DeepSeek API, Pydantic, DuckDB, Pandas, Plotly, Streamlit.

## Benefit

- A non-technical user can start from a business question instead of a dashboard filter.
- The investigation can take a second and third step, instead of answering from one query.
- Calculations stay in DuckDB. The model does not invent the figures in the tables.
- Each chart has the rows and the script that produced it.
- The date window follows the latest row, so it stays correct after the table is rebuilt.

## Limitations

- One table and one demo dataset. It does not connect to a warehouse or support several users.
- The sample is synthetic. The Kowloon beverage drop is planted so the flow can be demonstrated.
- At most three rounds, and one retry per script. A bad script ends the investigation early.
- The answer is only as good as the query the model writes. There is no certified metric catalog.
- "This week" means the last seven dates in the file, not a business calendar week.
- The writer is instructed to quote only returned numbers, but it can still phrase a comparison poorly.
- Questions about causes outside the table, such as rent, staff, or promotion spend, cannot be answered.
- Nothing is saved. Refreshing the page clears the result.
