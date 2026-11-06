"""Plotly figures with one shared visual system: thin marks, recessive grid,
one y-axis per chart, categorical colours assigned by entity (never by rank)."""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

FONT = "Manrope, system-ui, sans-serif"
INK, INK_2, INK_3 = "#1b1d1c", "#52514e", "#8a8984"
GRID, SURFACE = "#e8e8e3", "rgba(0,0,0,0)"
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
SEQUENTIAL = ["#f4f8fd", "#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]
PRIOR = "#a9a8a2"  # comparison series: neutral, never a categorical slot

# Fixed colour per entity, so filtering never repaints the survivors.
ENTITY_COLORS = {
    "Lighting": SERIES[0], "Furniture": SERIES[1], "Textiles": SERIES[2], "Kitchen": SERIES[3],
    "Decor": SERIES[4], "Outdoor": SERIES[5],
    "Paid search": SERIES[0], "Social ads": SERIES[1], "Marketplace": SERIES[2],
    "New customers": SERIES[0], "Returning customers": SERIES[1],
}


def eur(v: float, decimals: int = 0) -> str:
    if abs(v) >= 1_000_000:
        return f"€{v / 1_000_000:.2f}M"
    if abs(v) >= 10_000:
        return f"€{v / 1_000:.0f}k"
    return f"€{v:,.{decimals}f}"


def _base(fig: go.Figure, height: int = 320, legend: bool = False) -> go.Figure:
    fig.update_layout(
        height=height, margin=dict(l=8, r=16, t=8, b=8),
        paper_bgcolor=SURFACE, plot_bgcolor=SURFACE,
        font=dict(family=FONT, size=13, color=INK_2),
        hoverlabel=dict(font=dict(family=FONT, size=13), bgcolor="#ffffff", bordercolor=GRID),
        showlegend=legend,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0, font=dict(color=INK_2), title=None),
        bargap=0.28,
    )
    fig.update_xaxes(showgrid=False, linecolor=GRID, tickfont=dict(color=INK_3), ticks="", title=None)
    fig.update_yaxes(gridcolor=GRID, zeroline=False, linecolor=GRID, tickfont=dict(color=INK_3), title=None)
    return fig


def revenue_trend(cur: pd.DataFrame, prior: pd.DataFrame) -> go.Figure:
    """Weekly revenue for the selected period, with the same weeks one year earlier."""
    fig = go.Figure()
    if not prior.empty:
        fig.add_trace(go.Scatter(
            x=prior["week_aligned"], y=prior["revenue"], name="Same weeks last year", mode="lines",
            line=dict(color=PRIOR, width=2, dash="dot"),
            hovertemplate="Last year: %{y:,.0f} €<extra></extra>"))
    fig.add_trace(go.Scatter(
        x=cur["week"], y=cur["revenue"], name="Selected period", mode="lines",
        line=dict(color=SERIES[0], width=2.5),
        hovertemplate="Week of %{x|%d %b %Y}<br>Revenue: %{y:,.0f} €<extra></extra>"))
    if not cur.empty:
        peak = cur.loc[cur["revenue"].idxmax()]
        fig.add_annotation(x=peak["week"], y=peak["revenue"], text=f"Peak {eur(peak['revenue'])}",
                           showarrow=False, yshift=14, font=dict(color=INK, size=12))
    fig = _base(fig, 330, legend=True)
    fig.update_layout(hovermode="x unified")
    fig.update_yaxes(tickprefix="€", tickformat="~s")
    return fig


def ranked_bars(df: pd.DataFrame, value: str = "revenue", label: str = "label", height: int | None = None) -> go.Figure:
    """Horizontal bars, largest first, one hue (magnitude, not identity)."""
    df = df.sort_values(value)
    growth = df["growth"] if "growth" in df else pd.Series([None] * len(df), index=df.index)
    text = [f"{eur(v)}" + (f"  {g:+.0%}" if pd.notna(g) else "") for v, g in zip(df[value], growth)]
    fig = go.Figure(go.Bar(
        x=df[value], y=df[label], orientation="h", marker=dict(color=SERIES[0], cornerradius=4),
        text=text, textposition="outside", cliponaxis=False, textfont=dict(color=INK_2, size=12),
        customdata=df[["margin"]].fillna(0) if "margin" in df else None,
        hovertemplate="%{y}<br>Revenue: %{x:,.0f} €" + ("<br>Gross margin: %{customdata[0]:.1%}" if "margin" in df else "") + "<extra></extra>",
    ))
    fig = _base(fig, height or max(220, 46 * len(df) + 40))
    fig.update_xaxes(showticklabels=False, showgrid=False, range=[0, df[value].max() * 1.32 if len(df) else 1])
    fig.update_yaxes(showgrid=False, tickfont=dict(color=INK, size=13))
    return fig


def stacked_months(df: pd.DataFrame, series_col: str, order: list[str]) -> go.Figure:
    fig = go.Figure()
    for name in order:
        part = df[df[series_col] == name]
        fig.add_trace(go.Bar(
            x=part["month"], y=part["revenue"], name=name,
            marker=dict(color=ENTITY_COLORS.get(name, SERIES[len(fig.data) % 8]), line=dict(color="#fcfcfb", width=1)),
            hovertemplate=f"{name}<br>%{{x|%b %Y}}: %{{y:,.0f}} €<extra></extra>"))
    fig = _base(fig, 320, legend=True)
    fig.update_layout(barmode="stack", bargap=0.18, legend_traceorder="normal")
    fig.update_yaxes(tickprefix="€", tickformat="~s")
    return fig


def category_heatmap(df: pd.DataFrame) -> go.Figure:
    pivot = df.pivot_table(index="category", columns="month", values="revenue", aggfunc="sum").fillna(0)
    pivot = pivot.loc[pivot.sum(axis=1).sort_values().index]
    fig = go.Figure(go.Heatmap(
        z=pivot.values, x=pivot.columns, y=pivot.index, colorscale=[[i / 7, c] for i, c in enumerate(SEQUENTIAL)],
        xgap=2, ygap=2, colorbar=dict(title=None, tickprefix="€", tickformat="~s", thickness=10, outlinewidth=0),
        hovertemplate="%{y}, %{x|%b %Y}<br>Revenue: %{z:,.0f} €<extra></extra>"))
    fig = _base(fig, 300)
    fig.update_xaxes(tickformat="%b<br>%Y", dtick="M2")
    fig.update_yaxes(showgrid=False, tickfont=dict(color=INK))
    return fig


def cohort_heatmap(df: pd.DataFrame) -> go.Figure:
    pivot = df.pivot_table(index="cohort_month", columns="months_since", values="retention")
    sizes = df.groupby("cohort_month")["cohort_size"].first().reindex(pivot.index)
    labels = [f"{d:%b %Y}  ({n:,})" for d, n in zip(pd.to_datetime(pivot.index), sizes)]
    fig = go.Figure(go.Heatmap(
        z=pivot.values, x=[f"M{m}" for m in pivot.columns], y=labels,
        colorscale=[[i / 7, c] for i, c in enumerate(SEQUENTIAL)], zmin=0, zmax=float(df["retention"].quantile(0.97) or 0.2),
        xgap=2, ygap=2, text=[[f"{v:.0%}" if pd.notna(v) else "" for v in row] for row in pivot.values],
        texttemplate="%{text}", textfont=dict(size=11),
        colorbar=dict(tickformat=".0%", thickness=10, outlinewidth=0),
        hovertemplate="Cohort %{y}<br>%{x} after first order<br>%{z:.1%} ordered again<extra></extra>"))
    fig = _base(fig, max(320, 26 * len(labels) + 60))
    fig.update_yaxes(autorange="reversed", showgrid=False, tickfont=dict(color=INK, size=12))
    fig.update_xaxes(side="top")
    return fig


def channel_bars(df: pd.DataFrame, value: str, fmt: str, title_hover: str) -> go.Figure:
    df = df.dropna(subset=[value]).sort_values(value)
    fig = go.Figure(go.Bar(
        x=df[value], y=df["channel"], orientation="h",
        marker=dict(color=[ENTITY_COLORS.get(c, INK_3) for c in df["channel"]], cornerradius=4),
        text=[fmt.format(v) for v in df[value]], textposition="outside", cliponaxis=False,
        textfont=dict(color=INK_2, size=12),
        hovertemplate="%{y}<br>" + title_hover + ": %{x:,.2f}<extra></extra>"))
    fig = _base(fig, max(180, 52 * len(df) + 30))
    fig.update_xaxes(showticklabels=False, range=[0, (df[value].max() or 1) * 1.3])
    fig.update_yaxes(showgrid=False, tickfont=dict(color=INK, size=13))
    return fig


def spend_lines(df: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    for ch in ["Paid search", "Social ads", "Marketplace"]:
        part = df[df["channel"] == ch]
        if part.empty:
            continue
        fig.add_trace(go.Scatter(x=part["month"], y=part["spend"], name=ch, mode="lines+markers",
                                 line=dict(color=ENTITY_COLORS[ch], width=2), marker=dict(size=7),
                                 hovertemplate=f"{ch}<br>%{{x|%b %Y}}: %{{y:,.0f}} €<extra></extra>"))
    fig = _base(fig, 300, legend=True)
    fig.update_yaxes(tickprefix="€", tickformat="~s")
    return fig
