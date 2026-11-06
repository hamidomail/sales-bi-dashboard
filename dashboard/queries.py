"""All SQL used by the dashboard. Every query takes the same Filters object,
so each chart respects the date range, region, channel and category filters."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

import duckdb
import pandas as pd

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "warehouse.duckdb"


@dataclass(frozen=True)
class Filters:
    start: date
    end: date
    regions: tuple[str, ...] = ()
    channels: tuple[str, ...] = ()
    categories: tuple[str, ...] = ()

    def previous(self) -> "Filters":
        """Same-length period immediately before this one (for KPI deltas)."""
        length = (self.end - self.start).days + 1
        return Filters(self.start - timedelta(length), self.start - timedelta(1),
                       self.regions, self.channels, self.categories)

    def where(self, date_col: str = "order_date", dims: bool = True) -> tuple[str, list]:
        clauses, params = [f"{date_col} BETWEEN ? AND ?"], [self.start, self.end]
        if dims:
            for col, values in (("region", self.regions), ("channel", self.channels), ("category", self.categories)):
                if values:
                    clauses.append(f"{col} IN ({', '.join('?' for _ in values)})")
                    params.extend(values)
        return " AND ".join(clauses), params


class Warehouse:
    def __init__(self, path: Path = DB_PATH):
        if not path.exists():
            raise FileNotFoundError(
                f"{path} not found. Run `python scripts/generate_data.py && python scripts/build_warehouse.py`.")
        self.con = duckdb.connect(str(path), read_only=True)

    def df(self, sql: str, params: list | None = None) -> pd.DataFrame:
        return self.con.execute(sql, params or []).df()

    # ------------------------------------------------------------ metadata
    def bounds(self) -> tuple[date, date]:
        lo, hi = self.con.execute("SELECT min(order_date), max(order_date) FROM fct_sales").fetchone()
        return lo, hi

    def options(self, column: str) -> list[str]:
        return [r[0] for r in self.con.execute(f"SELECT DISTINCT {column} FROM fct_sales ORDER BY 1").fetchall()]

    # ------------------------------------------------------------ overview
    def kpis(self, f: Filters) -> dict:
        where, params = f.where()
        row = self.df(f"""
            SELECT sum(net_revenue)                                   AS revenue,
                   count(DISTINCT order_id)                           AS orders,
                   sum(net_revenue) / nullif(count(DISTINCT order_id), 0) AS aov,
                   sum(gross_profit) / nullif(sum(net_revenue), 0)    AS gross_margin,
                   count(DISTINCT CASE WHEN is_first_order THEN customer_id END) AS new_customers,
                   sum(refunded_amount) / nullif(sum(gross_revenue), 0) AS refund_rate
            FROM fct_sales WHERE {where}""", params).iloc[0]
        return {k: (float(v) if pd.notna(v) else 0.0) for k, v in row.items()}

    def revenue_by_week(self, f: Filters) -> pd.DataFrame:
        where, params = f.where()
        return self.df(f"""
            SELECT date_trunc('week', order_date)::DATE AS week, sum(net_revenue) AS revenue,
                   count(DISTINCT order_id) AS orders
            FROM fct_sales WHERE {where} GROUP BY 1 ORDER BY 1""", params)

    def revenue_by_full_week(self, f: Filters) -> pd.DataFrame:
        """Weekly revenue keeping only weeks fully inside the period, so partial
        edge weeks don't show up as false dips."""
        weeks = self.revenue_by_week(f)
        if weeks.empty:
            return weeks
        start = pd.to_datetime(weeks["week"])
        full = weeks[(start >= pd.Timestamp(f.start)) & (start + pd.Timedelta(days=6) <= pd.Timestamp(f.end))]
        return full if len(full) >= 2 else weeks

    def revenue_by(self, f: Filters, dim: str) -> pd.DataFrame:
        where, params = f.where()
        prev_where, prev_params = f.previous().where()
        return self.df(f"""
            WITH cur AS (SELECT {dim} AS label, sum(net_revenue) AS revenue,
                                sum(gross_profit) / nullif(sum(net_revenue), 0) AS margin
                         FROM fct_sales WHERE {where} GROUP BY 1),
                 prev AS (SELECT {dim} AS label, sum(net_revenue) AS prev_revenue
                          FROM fct_sales WHERE {prev_where} GROUP BY 1)
            SELECT cur.*, prev.prev_revenue,
                   cur.revenue / nullif(prev.prev_revenue, 0) - 1 AS growth
            FROM cur LEFT JOIN prev USING (label) ORDER BY revenue DESC""", params + prev_params)

    # ------------------------------------------------------------ products
    def top_products(self, f: Filters, limit: int = 15) -> pd.DataFrame:
        where, params = f.where()
        return self.df(f"""
            SELECT p.product_name AS product, s.category, sum(s.quantity) AS units,
                   sum(s.net_revenue) AS revenue,
                   sum(s.gross_profit) / nullif(sum(s.net_revenue), 0) AS margin,
                   sum(s.refunded_amount) / nullif(sum(s.gross_revenue), 0) AS refund_rate
            FROM fct_sales s JOIN (SELECT product_id, product_name FROM dim_product) p USING (product_id)
            WHERE {where} GROUP BY 1, 2 ORDER BY revenue DESC LIMIT {int(limit)}""", params)

    def category_by_month(self, f: Filters) -> pd.DataFrame:
        where, params = f.where()
        return self.df(f"""
            SELECT date_trunc('month', order_date)::DATE AS month, category, sum(net_revenue) AS revenue
            FROM fct_sales WHERE {where} GROUP BY 1, 2 ORDER BY 1, 2""", params)

    # ------------------------------------------------------------ customers
    def new_vs_returning(self, f: Filters) -> pd.DataFrame:
        where, params = f.where()
        return self.df(f"""
            SELECT date_trunc('month', order_date)::DATE AS month,
                   CASE WHEN is_first_order THEN 'New customers' ELSE 'Returning customers' END AS segment,
                   sum(net_revenue) AS revenue
            FROM fct_sales WHERE {where} GROUP BY 1, 2 ORDER BY 1, 2""", params)

    def cohort_retention(self, f: Filters, max_months: int = 12) -> pd.DataFrame:
        """Share of each acquisition cohort that ordered again N months later."""
        where, params = f.where("c.cohort_month", dims=False)
        dims, dim_params = [], []
        for col, values in (("c.region", f.regions), ("c.acquisition_channel", f.channels)):
            if values:
                dims.append(f"{col} IN ({', '.join('?' for _ in values)})")
                dim_params.extend(values)
        extra = (" AND " + " AND ".join(dims)) if dims else ""
        return self.df(f"""
            WITH activity AS (
                SELECT DISTINCT c.customer_id, c.cohort_month,
                       datediff('month', c.cohort_month, date_trunc('month', s.order_date)) AS months_since
                FROM dim_customer c JOIN fct_sales s USING (customer_id)
                WHERE {where}{extra}),
            sizes AS (SELECT cohort_month, count(DISTINCT customer_id) AS cohort_size FROM activity GROUP BY 1)
            SELECT a.cohort_month, a.months_since, sizes.cohort_size,
                   count(DISTINCT a.customer_id) / sizes.cohort_size AS retention
            FROM activity a JOIN sizes USING (cohort_month)
            WHERE a.months_since BETWEEN 1 AND {int(max_months)}
            GROUP BY 1, 2, 3 ORDER BY 1, 2""", params + dim_params)

    def segments(self, f: Filters) -> pd.DataFrame:
        """Simple RFM-style segments as of the end of the selected period."""
        where, params = f.where()
        return self.df(f"""
            WITH c AS (
                SELECT customer_id, count(DISTINCT order_id) AS orders, sum(net_revenue) AS revenue,
                       datediff('day', max(order_date), ?::DATE) AS days_since
                FROM fct_sales WHERE {where} GROUP BY 1)
            SELECT CASE
                     WHEN orders >= 3 AND days_since <= 120 THEN 'Champions'
                     WHEN orders >= 2 AND days_since <= 180 THEN 'Loyal'
                     WHEN orders = 1 AND days_since <= 60 THEN 'New'
                     WHEN orders >= 2 THEN 'At risk'
                     ELSE 'One-time, lapsed'
                   END AS segment,
                   count(*) AS customers, sum(revenue) AS revenue, avg(revenue) AS revenue_per_customer,
                   avg(days_since) AS avg_days_since_last_order
            FROM c GROUP BY 1 ORDER BY revenue DESC""", [f.end] + params)

    # ------------------------------------------------------------ marketing
    def channel_economics(self, f: Filters) -> pd.DataFrame:
        """Spend, new customers, CAC and first-order ROAS per paid channel."""
        where, params = f.where()
        m_where, m_params = f.where("date", dims=False)
        ch_filter, ch_params = "", []
        if f.channels:
            ch_filter = f" AND channel IN ({', '.join('?' for _ in f.channels)})"
            ch_params = list(f.channels)
        return self.df(f"""
            WITH spend AS (SELECT channel, sum(spend) AS spend, sum(clicks) AS clicks
                           FROM fct_marketing WHERE {m_where}{ch_filter} GROUP BY 1),
                 acq AS (SELECT channel, count(DISTINCT CASE WHEN is_first_order THEN customer_id END) AS new_customers,
                                sum(CASE WHEN is_first_order THEN net_revenue ELSE 0 END) AS first_order_revenue,
                                sum(net_revenue) AS revenue
                         FROM fct_sales WHERE {where} GROUP BY 1)
            SELECT acq.channel, coalesce(spend.spend, 0) AS spend, acq.new_customers, acq.first_order_revenue, acq.revenue,
                   spend.spend / nullif(acq.new_customers, 0) AS cac,
                   acq.first_order_revenue / nullif(spend.spend, 0) AS roas
            FROM acq LEFT JOIN spend USING (channel)
            ORDER BY spend DESC NULLS LAST, revenue DESC""", m_params + ch_params + params)

    def spend_by_month(self, f: Filters) -> pd.DataFrame:
        m_where, m_params = f.where("date", dims=False)
        ch_filter, ch_params = "", []
        if f.channels:
            ch_filter = f" AND channel IN ({', '.join('?' for _ in f.channels)})"
            ch_params = list(f.channels)
        return self.df(f"""
            SELECT date_trunc('month', date)::DATE AS month, channel, sum(spend) AS spend
            FROM fct_marketing WHERE {m_where}{ch_filter} GROUP BY 1, 2 ORDER BY 1, 2""", m_params + ch_params)
