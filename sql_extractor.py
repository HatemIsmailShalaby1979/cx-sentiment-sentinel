"""
sql_extractor.py
----------------
Unified SQL extraction engine for CX Sentinel.
Uses shared_utils for configuration and environment management.
"""

import argparse
import pandas as pd
from sqlalchemy import create_engine
from shared_utils import ConfigManager

# Initialize centralized configuration
config = ConfigManager()

# Define Views
KPI_VIEWS = {
    "aht":  "v_client_aht_trend",
    "fcr":  "v_client_fcr_trend",
    "sla":  "v_client_sla_trend",
    "csat": "v_client_csat_trend",
}

def get_engine():
    """Builds connection string from ConfigManager."""
    host   = config.get("DB_HOST", "localhost")
    port   = config.get("DB_PORT", "5432")
    name   = config.get("DB_NAME", "ops_db")
    user   = config.get("DB_USER", "readonly_user")
    pw     = config.get("DB_PASS", "")
    dsn    = f"postgresql+psycopg2://{user}:{pw}@{host}:{port}/{name}"
    return create_engine(dsn, pool_pre_ping=True)

def query_view(engine, view_name: str, rolling_days: int, client_ids: list = None):
    """Executes the query."""
    query = f"SELECT * FROM {view_name} WHERE metric_date >= CURRENT_DATE - INTERVAL '{rolling_days} days'"
    if client_ids:
        query += f" AND client_id IN ({','.join([f"'{c}'" for c in client_ids])})"
    return pd.read_sql(query, engine)

def extract_all_kpis(rolling_days: int = 30, client_ids: list = None, output_path: str = "data/raw_kpi.parquet") -> pd.DataFrame:
    engine = get_engine()
    frames = []

    for kpi_name, view_name in KPI_VIEWS.items():
        print(f"  [Extract] Querying {view_name} (last {rolling_days} days)...")
        try:
            df = query_view(engine, view_name, rolling_days, client_ids)
            df["kpi"] = kpi_name
            frames.append(df)
            print(f"           → {len(df)} rows")
        except Exception as e:
            print(f"  [WARN] Failed to query {view_name}: {e}")

    if not frames:
        raise RuntimeError("All KPI view queries failed. Check DB connectivity.")

    combined = pd.concat(frames, ignore_index=True)
    combined.to_parquet(output_path, index=False)
    print(f"\n[OK] KPI extraction complete → {output_path} ({len(combined)} rows)")
    return combined

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extract KPI data")
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--output", default="data/raw_kpi.parquet")
    args = parser.parse_args()
    extract_all_kpis(args.days, output_path=args.output)