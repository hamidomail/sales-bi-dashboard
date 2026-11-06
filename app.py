"""Lumen & Co. sales performance dashboard.

    streamlit run app.py
"""
from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import streamlit as st

from dashboard import charts
from dashboard.queries import Filters, Warehouse

st.set_page_config(page_title="Lumen & Co. sales dashboard", page_icon="📈", layout="wide")
st.markdown("""
<link href="https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
html, body, [class*="st-"], .stMarkdown, .stMetric { font-family: Manrope, system-ui, sans-serif; }
.block-container { padding-top: 1.6rem; max-width: 1400px; }
h1 { font-weight: 700; letter-spacing: -0.02em; font-size: 1.9rem !important; margin-bottom: 0 !important; }
h3 { font-weight: 650; font-size: 1.05rem !important; letter-spacing: -0.005em; }
[data-testid="stMetric"] { background: #ffffff; border: 1px solid #e8e8e3; border-radius: 10px; padding: 14px 16px 10px; }
[data-testid="stMetricLabel"] p { color: #52514e; font-size: 0.85rem; }
[data-testid="stMetricValue"] { font-weight: 700; font-size: 1.65rem; letter-spacing: -0.02em; }
.subtitle { color: #52514e; margin: 0.15rem 0 1.1rem; }
.insights { background: #ffffff; border: 1px solid #e8e8e3; border-left: 4px solid #2a78d6; border-radius: 10px; padding: 12px 18px; margin: 6px 0 4px; }
.insights ul { margin: 0; padding-left: 1.1rem; } .insights li { margin: 3px 0; color: #1b1d1c; }
.stTabs [data-baseweb="tab"] { font-weight: 600; }
</style>""", unsafe_allow_html=True)


@st.cache_resource
def warehouse() -> Warehouse:
    return Warehouse()


try:
    wh = warehouse()
except FileNotFoundError as err:
    st.error(str(err))
    st.stop()

data_start, data_end = wh.bounds()

# ------------------------------------------------------------------ filters
st.title("Lumen & Co. sales performance")
st.markdown(f'<p class="subtitle">Online home goods store, {data_start:%d %b %Y} to {data_end:%d %b %Y}. '
            "All figures are net of refunds, in euros.</p>", unsafe_allow_html=True)

PRESETS = {
    "Last 90 days": lambda: (data_end - timedelta(89), data_end),
    "Last 12 months": lambda: (data_end - timedelta(364), data_end),
    "Year to date": lambda: (date(data_end.year, 1, 1), data_end),
    "Last full quarter": None,
    "All time": lambda: (data_start, data_end),
    "Custom": None,
}


def last_full_quarter(d: date) -> tuple[date, date]:
    q_start = date(d.year, 3 * ((d.month - 1) // 3) + 1, 1)
    end = q_start - timedelta(1)
    return date(end.year, 3 * ((end.month - 1) // 3) + 1, 1), end


c1, c2, c3, c4 = st.columns([1.3, 1, 1, 1])
with c1:
    preset = st.selectbox("Period", list(PRESETS), index=1)
    if preset == "Custom":
        picked = st.date_input("Dates", (data_end - timedelta(89), data_end), min_value=data_start, max_value=data_end)
        start, end = (picked if isinstance(picked, tuple) and len(picked) == 2 else (data_start, data_end))
    elif preset == "Last full quarter":
        start, end = last_full_quarter(data_end)
    else:
        start, end = PRESETS[preset]()
with c2:
    regions = st.multiselect("Region", wh.options("region"), placeholder="All regions")
with c3:
    channels = st.multiselect("Acquisition channel", wh.options("channel"), placeholder="All channels")
with c4:
    categories = st.multiselect("Category", wh.options("category"), placeholder="All categories")

f = Filters(max(start, data_start), min(end, data_end), tuple(regions), tuple(channels), tuple(categories))
prev = f.previous()
has_prev = prev.start >= data_start

# --------------------------------------------------------------------- KPIs
cur_k = wh.kpis(f)
prev_k = wh.kpis(prev) if has_prev else None


def delta(key: str, kind: str = "pct") -> str | None:
    if not prev_k or not prev_k[key]:
        return None
    if kind == "pts":
        return f"{(cur_k[key] - prev_k[key]) * 100:+.1f} pts"
    return f"{cur_k[key] / prev_k[key] - 1:+.1%}"


cols = st.columns(6)
cols[0].metric("Net revenue", charts.eur(cur_k["revenue"]), delta("revenue"))
cols[1].metric("Orders", f"{cur_k['orders']:,.0f}", delta("orders"))
cols[2].metric("Average order value", charts.eur(cur_k["aov"], 0), delta("aov"))
cols[3].metric("Gross margin", f"{cur_k['gross_margin']:.1%}", delta("gross_margin", "pts"))
cols[4].metric("New customers", f"{cur_k['new_customers']:,.0f}", delta("new_customers"))
cols[5].metric("Refund rate", f"{cur_k['refund_rate']:.1%}", delta("refund_rate", "pts"), delta_color="inverse")
if has_prev:
    st.caption(f"Changes compare with {prev.start:%d %b %Y} to {prev.end:%d %b %Y}, the period of the same length just before.")
else:
    st.caption("No comparison: the previous period of the same length starts before the data does.")

# ----------------------------------------------------------------- insights
by_cat = wh.revenue_by(f, "category")
econ = wh.channel_economics(f)
insights = []
if prev_k and prev_k["revenue"]:
    change = cur_k["revenue"] / prev_k["revenue"] - 1
    insights.append(f"Revenue is <b>{'up' if change >= 0 else 'down'} {abs(change):.0%}</b> on the previous period "
                    f"({charts.eur(cur_k['revenue'])} vs {charts.eur(prev_k['revenue'])}).")
movers = by_cat.dropna(subset=["growth"])
if not movers.empty:
    top = movers.loc[(movers["revenue"] - movers["prev_revenue"]).idxmax()]
    insights.append(f"<b>{top['label']}</b> added the most revenue: {charts.eur(top['revenue'] - top['prev_revenue'])} "
                    f"more than the previous period ({top['growth']:+.0%}).")
paid = econ.dropna(subset=["roas"])
paid = paid[paid["spend"] > 0]
if len(paid) >= 2:
    best, worst = paid.loc[paid["roas"].idxmax()], paid.loc[paid["roas"].idxmin()]
    insights.append(f"<b>{best['channel']}</b> returns {best['roas']:.1f}× its ad spend on first orders, "
                    f"against {worst['roas']:.1f}× for {worst['channel']}.")
refunds = wh.top_products(f, 60)
if not refunds.empty:
    r = refunds.sort_values("refund_rate", ascending=False).iloc[0]
    if r["refund_rate"] > cur_k["refund_rate"] * 1.5:
        insights.append(f"<b>{r['product']}</b> has the highest refund rate ({r['refund_rate']:.0%}), "
                        f"well above the {cur_k['refund_rate']:.1%} average.")
if insights:
    st.markdown('<div class="insights"><ul>' + "".join(f"<li>{i}</li>" for i in insights) + "</ul></div>",
                unsafe_allow_html=True)

# --------------------------------------------------------------------- tabs
CHART_CFG = {"displaylogo": False, "modeBarButtonsToRemove": ["lasso2d", "select2d"]}
overview, products, customers, marketing = st.tabs(["Overview", "Products", "Customers", "Marketing"])

with overview:
    st.subheader("Weekly revenue")
    cur_w = wh.revenue_by_full_week(f)
    ly = Filters(f.start - timedelta(364), f.end - timedelta(364), f.regions, f.channels, f.categories)
    prior_w = wh.revenue_by_full_week(ly) if ly.start >= data_start - timedelta(6) else pd.DataFrame()
    if not prior_w.empty:
        prior_w["week_aligned"] = pd.to_datetime(prior_w["week"]) + pd.Timedelta(days=364)
    st.plotly_chart(charts.revenue_trend(cur_w, prior_w), width="stretch", config=CHART_CFG)

    left, right = st.columns(2)
    with left:
        st.subheader("Revenue by category")
        st.plotly_chart(charts.ranked_bars(by_cat), width="stretch", config=CHART_CFG)
    with right:
        st.subheader("Revenue by region")
        st.plotly_chart(charts.ranked_bars(wh.revenue_by(f, "region")), width="stretch", config=CHART_CFG)
    st.caption("Percentages next to each bar compare with the previous period.")

with products:
    st.subheader("Top 15 products")
    top = wh.top_products(f)
    top[["margin", "refund_rate"]] = top[["margin", "refund_rate"]].astype(float) * 100
    top["revenue"] = top["revenue"].astype(float).round(0)
    st.dataframe(
        top, hide_index=True, width="stretch", height=35 * (len(top) + 1) + 3,
        column_config={
            "product": "Product", "category": "Category", "units": st.column_config.NumberColumn("Units", format="localized"),
            "revenue": st.column_config.ProgressColumn("Net revenue (€)", format="localized", min_value=0,
                                                       max_value=float(top["revenue"].max() if len(top) else 1)),
            "margin": st.column_config.NumberColumn("Gross margin", format="%.1f%%"),
            "refund_rate": st.column_config.NumberColumn("Refund rate", format="%.1f%%"),
        })
    st.subheader("Seasonality by category")
    st.plotly_chart(charts.category_heatmap(wh.category_by_month(f)), width="stretch", config=CHART_CFG)

with customers:
    left, right = st.columns([1.1, 1])
    with left:
        st.subheader("Revenue from new and returning customers")
        st.plotly_chart(charts.stacked_months(wh.new_vs_returning(f), "segment", ["New customers", "Returning customers"]),
                        width="stretch", config=CHART_CFG)
    with right:
        st.subheader("Customer segments")
        seg = wh.segments(f).round(0)
        st.dataframe(seg, hide_index=True, width="stretch", column_config={
            "segment": "Segment", "customers": st.column_config.NumberColumn("Customers", format="localized"),
            "revenue": st.column_config.NumberColumn("Revenue (€)", format="localized"),
            "revenue_per_customer": st.column_config.NumberColumn("Per customer (€)", format="localized"),
            "avg_days_since_last_order": st.column_config.NumberColumn("Days since last order", format="%.0f"),
        })
        st.caption("Champions: 3+ orders, last within 120 days. Loyal: 2+ orders within 180 days. "
                   "At risk: repeat buyers gone quiet.")
    st.subheader("Repeat purchase rate by cohort")
    st.caption("Share of customers acquired each month who ordered again N months after their first order. "
               "Cohort size in brackets.")
    cohorts = wh.cohort_retention(f)
    if cohorts.empty:
        st.info("No cohorts start inside the selected period. Choose a longer period to see repeat purchase rates.")
    else:
        st.plotly_chart(charts.cohort_heatmap(cohorts), width="stretch", config=CHART_CFG)

with marketing:
    paid_econ = econ[econ["spend"] > 0]
    left, right = st.columns(2)
    with left:
        st.subheader("Return on ad spend (first orders)")
        st.plotly_chart(charts.channel_bars(paid_econ, "roas", "{:.2f}×", "ROAS"), width="stretch", config=CHART_CFG)
    with right:
        st.subheader("Cost to acquire a customer")
        st.plotly_chart(charts.channel_bars(paid_econ, "cac", "€{:.0f}", "CAC (€)"), width="stretch", config=CHART_CFG)
    st.subheader("Monthly ad spend")
    st.plotly_chart(charts.spend_lines(wh.spend_by_month(f)), width="stretch", config=CHART_CFG)
    st.subheader("All acquisition channels")
    table = econ.astype({"spend": float, "first_order_revenue": float, "revenue": float}).round(0)
    table["cac"] = [f"€{v:,.0f}" if pd.notna(v) else "no ad spend" for v in econ["cac"]]
    table["roas"] = [f"{v:.2f}×" if pd.notna(v) else "no ad spend" for v in econ["roas"]]
    st.dataframe(table, hide_index=True, width="stretch", column_config={
        "channel": "Channel", "spend": st.column_config.NumberColumn("Ad spend (€)", format="localized"),
        "new_customers": st.column_config.NumberColumn("New customers", format="localized"),
        "first_order_revenue": st.column_config.NumberColumn("First-order revenue (€)", format="localized"),
        "revenue": st.column_config.NumberColumn("Total revenue (€)", format="localized"),
        "cac": st.column_config.TextColumn("CAC"),
        "roas": st.column_config.TextColumn("ROAS"),
    })

# ------------------------------------------------------------------- export
st.divider()
summary = by_cat.rename(columns={"label": "category"})
st.download_button("Download category summary (CSV)", summary.to_csv(index=False).encode(),
                   file_name=f"category_summary_{f.start}_{f.end}.csv", mime="text/csv")
