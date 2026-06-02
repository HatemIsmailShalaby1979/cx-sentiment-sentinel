"""
sql_extractor.py
----------------
Connects to the Data Warehouse, extracts rolling KPI metrics for all active
clients using predefined SQL views, and exports the dataset to a Parquet file.
"""

import os
import argparse
import pandas as pd
from pathlib import Path
from sqlalchemy import create_engine
from dotenv import load_dotenv

load_dotenv("config/.env")

VIEWS = [
    ("aht", "v_client_aht_trend"),
    ("fcr", "v_client_fcr_trend"),
    ("sla", "v_client_sla_trend"),
    ("csat", "v_client_csat_trend")
]

def extract_data(output_path: str):
    db_url = os.getenv("DW_CONNECTION_STRING", "sqlite:///:memory:")
    engine = create_engine(db_url)
    
    frames = []
    for kpi, view_name in VIEWS:
        print(f"  [Extractor] Querying {view_name}...")
        try:
            df = pd.read_sql(f"SELECT * FROM {view_name}", engine)
            df['kpi'] = kpi
            frames.append(df)
        except Exception as e:
            print(f"  [Extractor] WARNING: Could not read {view_name}. {e}")
            
    if not frames:
        raise RuntimeError("No data extracted. Verify warehouse connection and views.")
        
    combined = pd.concat(frames, ignore_index=True)
    
    out_file = Path(output_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    combined.to_parquet(out_file, index=False)
    
    print(f"[OK] Extraction complete → {output_path} ({len(combined)} rows)")
    return combined

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="data/raw_kpi.parquet")
    args = parser.parse_args()
    extract_data(args.output)