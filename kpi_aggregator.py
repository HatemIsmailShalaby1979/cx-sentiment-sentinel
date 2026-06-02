"""
kpi_aggregator.py
-----------------
Transforms raw KPI extracts into normalized, rolling-window aggregates
per client segment. Computes directional decay signals for downstream
risk scoring.

Input:  data/raw_kpi.parquet  (output of sql_extractor.py)
Output: data/normalized_kpi.parquet

KPI directionality:
  AHT  → higher is WORSE  (decay_direction = -1)
  FCR  → lower  is WORSE  (decay_direction = +1)
  SLA  → lower  is WORSE  (decay_direction = +1)
  CSAT → lower  is WORSE  (decay_direction = +1)
"""

import argparse
import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# KPI Configuration
# ---------------------------------------------------------------------------

KPI_CONFIG = {
    "aht":  {"decay_direction": -1, "unit": "seconds"},   # up = bad
    "fcr":  {"decay_direction":  1, "unit": "pct"},        # down = bad
    "sla":  {"decay_direction":  1, "unit": "pct"},        # down = bad
    "csat": {"decay_direction":  1, "unit": "score"},      # down = bad
}

ROLLING_SHORT = 7    # days — fast signal
ROLLING_LONG  = 30   # days — trend baseline


# ---------------------------------------------------------------------------
# Normalization Utilities
# ---------------------------------------------------------------------------

def normalize_series(s: pd.Series) -> pd.Series:
    """Min-max normalize to [0, 1]. Returns 0.5 on flat or single-value series."""
    s_min, s_max = s.min(), s.max()
    if s_max == s_min:
        return pd.Series(0.5, index=s.index)
    return (s - s_min) / (s_max - s_min)


def compute_decay_score(normalized_value: float, direction: int,
                        velocity: float) -> float:
    """
    Convert a normalized KPI value to a decay score in [0, 1].
    decay = 1 means complete deterioration. 0 means healthy.

    direction: +1 if higher is better (FCR, SLA, CSAT)
               -1 if lower is better (AHT)
    velocity_multiplier amplifies recent rapid movement.
    """
    if direction == 1:
        raw_decay = 1.0 - normalized_value       # lower value = more decay
    else:
        raw_decay = normalized_value             # higher value = more decay

    velocity_mult = 1.0 + max(0.0, abs(velocity) * 2.0)   # caps below 3×
    decay = min(1.0, raw_decay * velocity_mult)
    return round(float(decay), 4)


# ---------------------------------------------------------------------------
# Core Aggregator
# ---------------------------------------------------------------------------

def aggregate_client_kpi(df_kpi: pd.DataFrame, kpi_name: str) -> pd.DataFrame:
    """
    For a single KPI DataFrame (already filtered by kpi == kpi_name):
    Compute rolling means, deltas, normalized values, and decay scores.
    Returns one row per (client_id, latest_date).
    """
    direction = KPI_CONFIG[kpi_name]["decay_direction"]
    df        = df_kpi.sort_values(["client_id", "metric_date"]).copy()

    results = []

    for client_id, grp in df.groupby("client_id"):
        grp       = grp.set_index("metric_date").sort_index()
        values    = grp["metric_value"].astype(float)

        if len(values) < 2:
            continue

        roll_7  = values.rolling(ROLLING_SHORT,  min_periods=1).mean()
        roll_30 = values.rolling(ROLLING_LONG,   min_periods=1).mean()

        # Velocity: (current 7d avg - prior 7d avg) / prior 7d avg
        prior_7      = roll_7.shift(ROLLING_SHORT)
        velocity_7d  = ((roll_7 - prior_7) / prior_7.replace(0, np.nan)).fillna(0.0)

        # Most recent values
        latest_date  = values.index[-1]
        current_val  = float(values.iloc[-1])
        r7           = float(roll_7.iloc[-1])
        r30          = float(roll_30.iloc[-1])
        vel          = float(velocity_7d.iloc[-1])

        # Normalize over available history
        norm_val     = float(normalize_series(values).iloc[-1])
        decay        = compute_decay_score(norm_val, direction, vel)

        results.append({
            "client_id":         client_id,
            "kpi":               kpi_name,
            "latest_date":       latest_date,
            "current_value":     round(current_val, 4),
            "roll_7d_avg":       round(r7, 4),
            "roll_30d_avg":      round(r30, 4),
            "velocity_7d":       round(vel, 4),
            "normalized_value":  round(norm_val, 4),
            "decay_score":       decay,
        })

    return pd.DataFrame(results)


def run_aggregation(input_path: str, output_path: str) -> pd.DataFrame:
    raw = pd.read_parquet(input_path)
    raw["metric_date"] = pd.to_datetime(raw["metric_date"])

    frames = []
    for kpi_name in KPI_CONFIG.keys():
        subset = raw[raw["kpi"] == kpi_name].copy()
        if subset.empty:
            print(f"  [Aggregator] No data for KPI: {kpi_name} — skipping")
            continue
        agg = aggregate_client_kpi(subset, kpi_name)
        frames.append(agg)
        print(f"  [Aggregator] {kpi_name.upper():5s} → {len(agg)} client records")

    if not frames:
        raise RuntimeError("No KPI data to aggregate.")

    combined = pd.concat(frames, ignore_index=True)
    combined.to_parquet(output_path, index=False)
    print(f"\n[OK] Aggregation complete → {output_path}  ({len(combined)} rows)")
    return combined


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Aggregate and normalize KPI data")
    parser.add_argument("--input",  default="data/raw_kpi.parquet")
    parser.add_argument("--output", default="data/normalized_kpi.parquet")
    args = parser.parse_args()
    run_aggregation(args.input, args.output)
