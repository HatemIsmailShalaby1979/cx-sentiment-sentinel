"""
risk_scorer.py
--------------
Computes risk scores based on decay metrics.
Uses unified ConfigManager.
"""
import pandas as pd
import logging
from pathlib import Path
from shared_utils import ConfigManager

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# Initialize Config
config = ConfigManager(config_path="config/risk_thresholds.yaml")

def categorise_risk(score: float, thresholds: dict) -> str:
    if score >= thresholds["critical"]: return "Critical"
    elif score >= thresholds["high"]: return "High"
    elif score >= thresholds["medium"]: return "Medium"
    return "Low"

def score_clients(
    normalised_path: str = "data/normalized_kpi.parquet",
    output_path: str = "data/scored_clients.parquet",
) -> pd.DataFrame:
    # Load weights/thresholds from unified config
    weights = config.get("weights")
    thresholds = config.get("thresholds")

    df = pd.read_parquet(normalised_path)
    records = []

    for client_id, group in df.groupby("client_id"):
        total_score = 0.0
        kpi_breakdown = {}

        for _, row in group.iterrows():
            kpi = row["kpi"].lower()
            decay = row["decay_score"]
            weight = weights.get(kpi, 0)
            
            kpi_risk = decay * weight * 100
            total_score += kpi_risk
            kpi_breakdown[kpi] = round(kpi_risk, 4)

        risk_score = round(min(total_score, 100.0), 2)
        risk_category = categorise_risk(risk_score, thresholds)

        records.append({
            "client_id": client_id,
            "risk_score": risk_score,
            "risk_category": risk_category,
            **kpi_breakdown,
        })

    scored = pd.DataFrame(records)
    scored.to_parquet(output_path, index=False)
    logger.info(f"Scoring complete. Output → {output_path}")
    return scored