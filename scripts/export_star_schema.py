"""Export the star schema (facts + dimensions) as CSV and Parquet so the same
model can be loaded into Power BI, Tableau or Looker Studio.

    python scripts/export_star_schema.py      # writes data/export/
"""
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "export"
TABLES = ["fct_sales", "fct_marketing", "dim_customer", "dim_product", "dim_date"]

if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(ROOT / "data" / "warehouse.duckdb"), read_only=True)
    for t in TABLES:
        con.execute(f"COPY {t} TO '{(OUT / t).as_posix()}.parquet' (FORMAT parquet)")
        con.execute(f"COPY {t} TO '{(OUT / t).as_posix()}.csv' (HEADER, DELIMITER ',')")
        print(f"exported {t}")
    print(f"Done: {OUT}  (relationships: fct_* -> dim_* on customer_id, product_id, order_date = date)")
