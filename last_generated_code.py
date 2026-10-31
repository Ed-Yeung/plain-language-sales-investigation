import sys
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

path = sys.argv[1]
try:
    df = pd.read_csv(path, encoding="utf-8")
except UnicodeDecodeError:
    df = pd.read_csv(path, encoding="latin-1")

df["Order Date"] = pd.to_datetime(df["Order Date"], errors="coerce")

# Figure 0: Sales by Category
sales_by_cat = df.groupby("Category", as_index=False)["Sales"].sum().sort_values("Sales", ascending=False)
fig0 = px.bar(sales_by_cat, x="Category", y="Sales", title="Sales by Category",
              text="Sales", color="Category")
fig0.update_layout(xaxis_title="Category", yaxis_title="Total Sales")
fig0.write_json("fig0.json", engine="json")

# Figure 1: Profit by Category
profit_by_cat = df.groupby("Category", as_index=False)["Profit"].sum().sort_values("Profit", ascending=False)
fig1 = px.bar(profit_by_cat, x="Category", y="Profit", title="Profit by Category",
              text="Profit", color="Category")
fig1.update_layout(xaxis_title="Category", yaxis_title="Total Profit")
fig1.write_json("fig1.json", engine="json")

# Figure 2: Sales vs Profit Relationship
fig2 = px.scatter(df, x="Sales", y="Profit", color="Category", size="Sales",
                  hover_data=["Order ID"], title="Sales vs Profit Relationship")
fig2.update_layout(xaxis_title="Sales", yaxis_title="Profit")
fig2.write_json("fig2.json", engine="json")

# Figure 3: Sales Trend Over Time
trend = df.sort_values("Order Date")
fig3 = px.line(trend, x="Order Date", y="Sales", markers=True,
               hover_data=["Order ID", "Category"], title="Sales Trend Over Time")
fig3.update_layout(xaxis_title="Order Date", yaxis_title="Sales")
fig3.write_json("fig3.json", engine="json")

# Figure 4: Profit Margin Distribution
df["Profit Margin (%)"] = (df["Profit"] / df["Sales"] * 100).round(2)
fig4 = px.histogram(df, x="Profit Margin (%)", nbins=10, title="Profit Margin Distribution",
                    color="Category")
fig4.update_layout(xaxis_title="Profit Margin (%)", yaxis_title="Number of Orders")
fig4.write_json("fig4.json", engine="json")
