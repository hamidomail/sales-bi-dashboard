"""Build the DuckDB warehouse from data/raw/*.csv by running sql/*.sql in order.

    python scripts/build_warehouse.py
"""
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
DB = ROOT / "data" / "warehouse.duckdb"


def build(db_path: Path = DB, raw: Path = RAW) -> None:
    if not (raw / "orders.csv").exists():
        raise SystemExit("No raw data found. Run: python scripts/generate_data.py")
    con = duckdb.connect(str(db_path))
    for sql_file in sorted((ROOT / "sql").glob("*.sql")):
        con.execute(sql_file.read_text(encoding="utf-8").replace("{raw}", raw.as_posix()))
        print(f"ran {sql_file.name}")
    failures = con.execute("SELECT * FROM dq_failures").fetchall()
    if failures:
        raise SystemExit(f"Data quality checks failed: {failures}")
    for table in ("fct_sales", "fct_marketing", "dim_customer", "dim_product", "dim_date"):
        print(f"  {table:<15} {con.execute(f'SELECT count(*) FROM {table}').fetchone()[0]:>8,} rows")
    con.close()
    print(f"Warehouse ready: {db_path}")


if __name__ == "__main__":
    build()
