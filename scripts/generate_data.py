"""Generate a realistic, fully synthetic e-commerce dataset (24 months).

    python scripts/generate_data.py            # writes data/raw/*.csv

Built-in patterns so the dashboard has real stories to tell: year-over-year
growth, Black Friday & December peaks, summer Outdoor season, repeat-purchase
decay by cohort, higher refund rates on Furniture, and paid channels with very
different returns on ad spend.
"""
from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

SEED = 42
START, END = date(2024, 11, 1), date(2026, 10, 31)
OUT = Path(__file__).resolve().parent.parent / "data" / "raw"
rng = np.random.default_rng(SEED)

COUNTRIES = [  # country, region, weight
    ("France", "Western Europe", 0.20), ("Germany", "Western Europe", 0.17), ("Belgium", "Western Europe", 0.05),
    ("Netherlands", "Western Europe", 0.06), ("United Kingdom", "Western Europe", 0.12),
    ("Spain", "Southern Europe", 0.08), ("Italy", "Southern Europe", 0.08), ("Portugal", "Southern Europe", 0.03),
    ("Sweden", "Northern Europe", 0.04), ("Denmark", "Northern Europe", 0.03),
    ("United States", "North America", 0.09), ("Canada", "North America", 0.05),
]
CHANNELS = {  # acquisition channel: (share of new customers, is paid, cost per acquired customer EUR)
    "Organic search": (0.27, False, 0), "Paid search": (0.22, True, 31), "Social ads": (0.19, True, 44),
    "Email": (0.10, False, 0), "Referral": (0.09, False, 0), "Marketplace": (0.13, True, 19),
}
CATEGORIES = {  # category: (price range EUR, margin range, refund rate, seasonality fn)
    "Lighting": ((35, 240), (0.48, 0.62), 0.035, lambda m: 1.25 if m in (11, 12, 1) else 1.0),
    "Furniture": ((180, 1400), (0.32, 0.45), 0.085, lambda m: 1.0),
    "Textiles": ((20, 160), (0.55, 0.70), 0.045, lambda m: 1.2 if m in (10, 11, 12) else 1.0),
    "Kitchen": ((15, 190), (0.42, 0.58), 0.030, lambda m: 1.35 if m == 12 else 1.0),
    "Decor": ((12, 130), (0.58, 0.72), 0.025, lambda m: 1.4 if m in (11, 12) else 0.95),
    "Outdoor": ((40, 650), (0.36, 0.50), 0.050, lambda m: 1.9 if m in (4, 5, 6, 7) else (0.45 if m in (11, 12, 1, 2) else 1.0)),
}
NAMES = {
    "Lighting": ["Arc Floor Lamp", "Halo Pendant", "Dune Table Lamp", "Prism Wall Light", "Orbit Desk Lamp", "Linen Shade Lamp", "Brass Reading Light", "Globe Pendant", "Ripple Sconce", "Nordic Floor Lamp"],
    "Furniture": ["Oak Dining Table", "Loom Armchair", "Fjord Sofa 3-Seat", "Cane Sideboard", "Arch Bookshelf", "Pebble Coffee Table", "Linen Daybed", "Walnut Desk", "Slat Bench", "Terra Bed Frame"],
    "Textiles": ["Waffle Throw", "Linen Duvet Set", "Wool Rug 160x230", "Velvet Cushion", "Jute Runner", "Cotton Bath Towels", "Bouclé Cushion", "Linen Curtains", "Knit Blanket", "Kilim Rug"],
    "Kitchen": ["Stoneware Dinner Set", "Cast Iron Pot", "Oak Serving Board", "Glass Carafe", "Ceramic Mug Set", "Copper Pan", "Knife Block Set", "Linen Apron", "Salad Bowl", "Espresso Cups"],
    "Decor": ["Ceramic Vase", "Round Mirror", "Scented Candle", "Art Print 50x70", "Rattan Basket", "Bookends", "Clay Planter", "Photo Frame Set", "Wall Clock", "Dried Flower Bunch"],
    "Outdoor": ["Teak Lounger", "Bistro Set", "Outdoor Lantern", "Parasol 3m", "Hammock", "Rope Chair", "Garden Planter", "Fire Bowl", "Outdoor Rug", "String Lights"],
}


def products() -> pd.DataFrame:
    rows = []
    for cat, ((lo, hi), (mlo, mhi), _, _) in CATEGORIES.items():
        for i, name in enumerate(NAMES[cat]):
            price = round(float(np.exp(rng.uniform(np.log(lo), np.log(hi)))), 0) - 0.01
            margin = rng.uniform(mlo, mhi)
            rows.append({"product_id": f"P{len(rows) + 1:03d}", "product_name": name, "category": cat,
                         "list_price": price, "unit_cost": round(price * (1 - margin), 2),
                         "popularity": float(rng.pareto(1.6) + 0.3)})
    return pd.DataFrame(rows)


def day_weight(d: date) -> float:
    months_in = (d.year - START.year) * 12 + d.month - START.month
    growth = 1.0 + 0.022 * months_in                       # ~26% YoY growth
    weekday = [1.0, 1.02, 1.0, 1.03, 0.95, 0.88, 1.12][d.weekday()]
    season = {1: 0.82, 2: 0.78, 3: 0.92, 4: 0.97, 5: 1.0, 6: 0.95, 7: 0.85, 8: 0.8, 9: 0.95, 10: 1.05, 11: 1.35, 12: 1.55}[d.month]
    black_friday = 2.6 if (d.month == 11 and 22 <= d.day <= 30 and d.weekday() == 4) else 1.0
    cyber_week = 1.5 if (d.month == 11 and 24 <= d.day <= 30) or (d.month == 12 and d.day <= 2) else 1.0
    return growth * weekday * season * black_friday * cyber_week


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    prod = products()
    days = [START + timedelta(n) for n in range((END - START).days + 1)]
    weights = np.array([day_weight(d) for d in days])

    # ---- customers: acquisition date follows the same demand curve
    n_customers = 11_500
    acq_idx = rng.choice(len(days), size=n_customers, p=weights / weights.sum())
    ch_names = list(CHANNELS)
    ch_probs = np.array([CHANNELS[c][0] for c in ch_names])
    countries = [c[0] for c in COUNTRIES]
    cprobs = np.array([c[2] for c in COUNTRIES]) / sum(c[2] for c in COUNTRIES)
    customers = pd.DataFrame({
        "customer_id": [f"C{i:05d}" for i in range(1, n_customers + 1)],
        "signup_date": [days[i] for i in acq_idx],
        "acquisition_channel": rng.choice(ch_names, n_customers, p=ch_probs / ch_probs.sum()),
        "country": rng.choice(countries, n_customers, p=cprobs),
    })
    region_of = {c: r for c, r, _ in COUNTRIES}
    customers["region"] = customers["country"].map(region_of)
    # loyalty propensity differs by channel (email & referral customers come back more)
    loyalty = {"Organic search": 0.34, "Paid search": 0.27, "Social ads": 0.21, "Email": 0.48, "Referral": 0.44, "Marketplace": 0.17}

    # ---- orders: first order on signup, then repeat purchases with decaying probability
    orders, lines = [], []
    pop = prod["popularity"].to_numpy()
    for cust in customers.itertuples(index=False):
        order_day = cust.signup_date
        p_repeat = loyalty[cust.acquisition_channel] + rng.normal(0, 0.06)
        n = 0
        while order_day <= END:
            n += 1
            oid = f"O{len(orders) + 1:06d}"
            discount = rng.choice([0, 0, 0, 0.1, 0.15, 0.2], p=[0.55, 0.1, 0.1, 0.12, 0.08, 0.05])
            if order_day.month == 11 and 22 <= order_day.day <= 30:
                discount = max(discount, 0.2)
            seasonal = np.array([CATEGORIES[c][3](order_day.month) for c in prod["category"]])
            p = pop * seasonal
            n_items = rng.choice([1, 2, 3, 4], p=[0.58, 0.27, 0.11, 0.04])
            picks = rng.choice(len(prod), size=n_items, replace=False, p=p / p.sum())
            refunded = False
            for k in picks:
                row = prod.iloc[k]
                qty = int(rng.choice([1, 1, 1, 2, 3])) if row.category in ("Decor", "Kitchen", "Textiles") else 1
                line_refund = rng.random() < CATEGORIES[row.category][2]
                refunded |= line_refund
                lines.append({"order_id": oid, "product_id": row.product_id, "quantity": qty,
                              "unit_price": round(row.list_price * (1 - discount), 2),
                              "unit_cost": row.unit_cost, "is_refunded": line_refund})
            orders.append({"order_id": oid, "customer_id": cust.customer_id, "order_date": order_day,
                           "order_number": n, "discount_rate": discount,
                           "device": rng.choice(["mobile", "desktop", "tablet"], p=[0.61, 0.33, 0.06]),
                           "shipping_fee": 0.0 if rng.random() < 0.6 else 6.9})
            if rng.random() > max(0.05, p_repeat * (0.9 ** (n - 1))):
                break
            gap = int(rng.gamma(2.0, 55)) + 7
            order_day = order_day + timedelta(gap)

    orders_df = pd.DataFrame(orders)
    lines_df = pd.DataFrame(lines)

    # ---- marketing spend: daily, per paid channel, proportional to acquisitions plus noise
    signups = customers.groupby(["signup_date", "acquisition_channel"]).size().rename("n").reset_index()
    spend_rows = []
    for d in days:
        for ch, (_, paid, cpa) in CHANNELS.items():
            if not paid:
                continue
            n = signups[(signups.signup_date == d) & (signups.acquisition_channel == ch)]["n"].sum()
            base = cpa * (n + 0.6) * rng.lognormal(0, 0.18)
            clicks = int(base / rng.uniform(0.55, 1.1))
            spend_rows.append({"date": d, "channel": ch, "spend": round(base, 2), "clicks": clicks,
                               "impressions": int(clicks * rng.uniform(28, 60))})
    spend_df = pd.DataFrame(spend_rows)

    prod.drop(columns="popularity").to_csv(OUT / "products.csv", index=False)
    customers.to_csv(OUT / "customers.csv", index=False)
    orders_df.to_csv(OUT / "orders.csv", index=False)
    lines_df.to_csv(OUT / "order_lines.csv", index=False)
    spend_df.to_csv(OUT / "marketing_spend.csv", index=False)
    print(f"customers {len(customers):,} | orders {len(orders_df):,} | order lines {len(lines_df):,} | "
          f"spend rows {len(spend_df):,} -> {OUT}")


if __name__ == "__main__":
    main()
