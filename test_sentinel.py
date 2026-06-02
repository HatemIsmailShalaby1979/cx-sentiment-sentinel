import pandas as pd
import pytest
from unittest.mock import patch, MagicMock
from risk_scorer import score_clients, categorise_risk


# ── Unit: categorise_risk ────────────────────────────────────────────────────

def test_categorise_risk_critical():
    thresholds = {"critical": 70.0, "high": 50.0, "medium": 30.0, "low": 0.0}
    assert categorise_risk(85.0, thresholds) == "Critical"

def test_categorise_risk_high():
    thresholds = {"critical": 70.0, "high": 50.0, "medium": 30.0, "low": 0.0}
    assert categorise_risk(60.0, thresholds) == "High"

def test_categorise_risk_medium():
    thresholds = {"critical": 70.0, "high": 50.0, "medium": 30.0, "low": 0.0}
    assert categorise_risk(40.0, thresholds) == "Medium"

def test_categorise_risk_low():
    thresholds = {"critical": 70.0, "high": 50.0, "medium": 30.0, "low": 0.0}
    assert categorise_risk(10.0, thresholds) == "Low"

def test_categorise_risk_exact_boundary():
    thresholds = {"critical": 70.0, "high": 50.0, "medium": 30.0, "low": 0.0}
    assert categorise_risk(70.0, thresholds) == "Critical"
    assert categorise_risk(50.0, thresholds) == "High"
    assert categorise_risk(30.0, thresholds) == "Medium"


# ── Integration: score_clients ───────────────────────────────────────────────

MOCK_CONFIG = {
    "weights": {"csat": 0.40, "sla": 0.30, "fcr": 0.20, "aht": 0.10},
    "thresholds": {"critical": 70.0, "high": 50.0, "medium": 30.0, "low": 0.0},
}


def _make_normalised_df(client_id: str, kpi: str, decay_score: float) -> pd.DataFrame:
    """Helper: single-row normalised parquet substitute."""
    return pd.DataFrame([
        {
            "client_id": client_id,
            "kpi": kpi,
            "decay_score": decay_score,
            "metric_date": pd.Timestamp("2026-05-29"),
        }
    ])


@patch("risk_scorer.load_config", return_value=MOCK_CONFIG)
@patch("risk_scorer.pd.read_parquet")
def test_risk_scoring_critical(mock_read_parquet, mock_load_config):
    """
    A decay_score of 0.85 on CSAT (weight 0.40) should produce:
        risk_score = 0.85 * 0.40 * 100 = 34.0  → "Medium"

    For a Critical score we need risk_score >= 70.
    Using decay_score=1.0 across all KPIs:
        (1.0*0.40 + 1.0*0.30 + 1.0*0.20 + 1.0*0.10) * 100 = 100.0 → "Critical"
    """
    # Single KPI, single client — verifies the core arithmetic
    mock_read_parquet.return_value = _make_normalised_df("test-client-01", "csat", 0.85)
    result = score_clients(output_path="/tmp/test_scored.parquet")

    assert len(result) == 1
    row = result.iloc[0]
    assert row["client_id"] == "test-client-01"
    assert row["risk_score"] == pytest.approx(34.0, abs=0.01)   # 0.85 * 0.40 * 100
    assert row["risk_category"] == "Medium"


@patch("risk_scorer.load_config", return_value=MOCK_CONFIG)
@patch("risk_scorer.pd.read_parquet")
def test_risk_scoring_max_decay_is_critical(mock_read_parquet, mock_load_config):
    """All KPIs at maximum decay (1.0) must produce risk_score=100 and Critical."""
    rows = [
        {"client_id": "test-client-02", "kpi": kpi, "decay_score": 1.0,
         "metric_date": pd.Timestamp("2026-05-29")}
        for kpi in ["csat", "sla", "fcr", "aht"]
    ]
    mock_read_parquet.return_value = pd.DataFrame(rows)
    result = score_clients(output_path="/tmp/test_scored_max.parquet")

    assert len(result) == 1
    row = result.iloc[0]
    assert row["risk_score"] == pytest.approx(100.0, abs=0.01)
    assert row["risk_category"] == "Critical"


@patch("risk_scorer.load_config", return_value=MOCK_CONFIG)
@patch("risk_scorer.pd.read_parquet")
def test_risk_scoring_zero_decay_is_low(mock_read_parquet, mock_load_config):
    """All KPIs at zero decay must produce risk_score=0 and Low."""
    rows = [
        {"client_id": "test-client-03", "kpi": kpi, "decay_score": 0.0,
         "metric_date": pd.Timestamp("2026-05-29")}
        for kpi in ["csat", "sla", "fcr", "aht"]
    ]
    mock_read_parquet.return_value = pd.DataFrame(rows)
    result = score_clients(output_path="/tmp/test_scored_zero.parquet")

    assert len(result) == 1
    row = result.iloc[0]
    assert row["risk_score"] == pytest.approx(0.0, abs=0.01)
    assert row["risk_category"] == "Low"


@patch("risk_scorer.load_config", return_value=MOCK_CONFIG)
@patch("risk_scorer.pd.read_parquet")
def test_risk_scoring_missing_columns_raises(mock_read_parquet, mock_load_config):
    """Parquet missing required columns must raise ValueError, not silently score 0."""
    mock_read_parquet.return_value = pd.DataFrame([{"client_id": "x", "kpi": "csat"}])
    with pytest.raises(ValueError, match="missing required columns"):
        score_clients(output_path="/tmp/test_scored_err.parquet")