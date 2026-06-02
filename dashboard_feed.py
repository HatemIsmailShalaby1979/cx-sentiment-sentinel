import pandas as pd
import logging
from pathlib import Path
from datetime import datetime
from sqlalchemy import create_engine, text

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


# ── Colour helpers ────────────────────────────────────────────────────────────

RAG_COLOURS = {
    "Critical": "#FF4444",
    "High":     "#FF8C00",
    "Medium":   "#FFD700",
    "Low":      "#44BB44",
}

def _rag_colour(risk_category: str) -> str:
    return RAG_COLOURS.get(risk_category, "#AAAAAA")


# ── CSV export ────────────────────────────────────────────────────────────────

def export_csv(
    scored_path: str = "data/scored_clients.parquet",
    normalised_path: str = "data/normalized_kpi.parquet",
    output_dir: str = "data/exports",
) -> None:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)

    scored = pd.read_parquet(scored_path)
    normalised = pd.read_parquet(normalised_path)

    scored.to_csv(output / "scored_clients.csv", index=False)
    normalised.to_csv(output / "normalized_kpi.csv", index=False)
    logger.info(f"CSV exports written to {output_dir}/")


# ── HTML report ───────────────────────────────────────────────────────────────

def generate_html_report(
    scored_path: str = "data/scored_clients.parquet",
    output_path: str = "data/exports/risk_report.html",
) -> None:
    scored = pd.read_parquet(scored_path)
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    generated_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    rows_html = ""
    for _, row in scored.iterrows():
        # FIX: was row["rag"] and row["cri"] — columns do not exist in scorer output.
        # Correct column names from risk_scorer.py are risk_category and risk_score.
        risk_category = row["risk_category"]
        risk_score    = row["risk_score"]
        colour        = _rag_colour(risk_category)

        rows_html += f"""
        <tr>
            <td>{row['client_id']}</td>
            <td style="color:{colour}; font-weight:bold;">{risk_category}</td>
            <td>{risk_score:.1f}</td>
        </tr>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8"/>
    <title>CX Sentinel — Risk Report</title>
    <style>
        body      {{ font-family: Arial, sans-serif; margin: 2rem; background: #f9f9f9; }}
        h1        {{ color: #1A1A2E; }}
        p.meta    {{ color: #666; font-size: 0.9rem; }}
        table     {{ border-collapse: collapse; width: 100%; background: #fff; }}
        th        {{ background: #1A1A2E; color: #E0E0FF; padding: 10px 14px; text-align: left; }}
        td        {{ padding: 8px 14px; border-bottom: 1px solid #e0e0e0; }}
        tr:hover  {{ background: #f0f4ff; }}
    </style>
</head>
<body>
    <h1>CX Sentinel — Client Risk Report</h1>
    <p class="meta">Generated: {generated_at} &nbsp;|&nbsp; Clients scored: {len(scored)}</p>
    <table>
        <thead>
            <tr>
                <th>Client ID</th>
                <th>Risk Category</th>
                <th>Risk Score (0–100)</th>
            </tr>
        </thead>
        <tbody>
            {rows_html}
        </tbody>
    </table>
</body>
</html>"""

    Path(output_path).write_text(html, encoding="utf-8")
    logger.info(f"HTML risk report written to {output_path}")


# ── PostgreSQL staging ────────────────────────────────────────────────────────

def write_to_staging_db(
    scored_path: str = "data/scored_clients.parquet",
    normalised_path: str = "data/normalized_kpi.parquet",
    db_url: str | None = None,
) -> None:
    """
    Atomically replace staging tables using a single transaction.

    FIX: Previously used TRUNCATE then to_sql(if_exists='append') across two
    separate transactions. If the process died between truncate and reload the
    staging tables were left empty. Now the entire operation is wrapped in a
    single engine.begin() block — either both tables are fully replaced or
    neither is touched.
    """
    if db_url is None:
        import os
        db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        logger.warning("DATABASE_URL not set — skipping staging DB write.")
        return

    scored     = pd.read_parquet(scored_path)
    normalised = pd.read_parquet(normalised_path)

    engine = create_engine(db_url)

    # FIX: single engine.begin() transaction — atomic replace of both tables.
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE TABLE staging_scored_clients"))
        scored.to_sql("staging_scored_clients", conn, if_exists="append", index=False)

        conn.execute(text("TRUNCATE TABLE staging_normalized_kpi"))
        normalised.to_sql("staging_normalized_kpi", conn, if_exists="append", index=False)

    logger.info("Staging tables replaced atomically.")


# ── Orchestrator ──────────────────────────────────────────────────────────────

def run_dashboard_feed(
    scored_path: str = "data/scored_clients.parquet",
    normalised_path: str = "data/normalized_kpi.parquet",
    output_dir: str = "data/exports",
    db_url: str | None = None,
) -> None:
    logger.info("Dashboard feed starting.")
    export_csv(scored_path, normalised_path, output_dir)
    generate_html_report(scored_path, output_path=f"{output_dir}/risk_report.html")
    write_to_staging_db(scored_path, normalised_path, db_url)
    logger.info("Dashboard feed complete.")


if __name__ == "__main__":
    run_dashboard_feed()