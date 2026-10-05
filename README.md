<div align="center">

# CX Sentiment & Churn Sentinel


<!-- badges:start -->

![licence](https://img.shields.io/badge/licence-MIT-blue)
[![last commit](https://img.shields.io/github/last-commit/HatemIsmailShalaby1979/cx-sentiment-sentinel)](https://github.com/HatemIsmailShalaby1979/cx-sentiment-sentinel/commits/main)
![status](https://img.shields.io/badge/ci-no CI-lightgrey?label=no CI%20(2026-10-02))

*Measured 2026-10-06 — head `8bf3d2c` (2026-10-02); Python.*

<!-- No static test or coverage count is shown here: a frozen
     number decays silently. Run the suite for a current figure;
     the CI badge above is the live status. -->
<!-- badges:end -->

**A precursor to Helix Prime — a KPI-decay risk scorer (the name overpromises).**

![Status](https://img.shields.io/badge/status-learning--exercise-yellow)
![Type](https://img.shields.io/badge/type-precursor-blue)
![Licence](https://img.shields.io/badge/licence-MIT-blue)
![Python](https://img.shields.io/badge/python-3.12-3776ab)

</div>

## One-line identity

A May–June 2026 learning exercise: a five-stage KPI pipeline that turns customer-experience KPIs into an account-risk signal. The idea was later absorbed into Helix Prime's CX engine.

> [!NOTE]
> **Operating principle — and an honest note on the name.** The repository is called *CX Sentiment & Churn Sentinel*, and that name overpromises. There is **no sentiment analysis and no churn model** anywhere in the code. What is here is a KPI-decay risk scorer: a weighted heuristic with configurable thresholds, not a fitted model. The name is left as-is because the repository is public history; the description below is what the code does. `docker-compose.yml` fails closed if `POSTGRES_PASSWORD` is unset, and `SECURITY_DECISIONS.md` records a real credential-exposure incident and its remediation.

One of four small tools built during the May–June 2026 period, before Helix Prime existed. The idea — turn customer-experience KPIs into an account-risk signal — was later absorbed into Helix Prime's CX engine. This repository is the sketch, not the system.

## What the code is

A five-stage KPI pipeline, written as separate scripts that pass Parquet files to each other on disk:

```
Postgres views  →  raw_kpi.parquet  →  normalized_kpi.parquet  →  scored_clients.parquet
   (SQL)              (extract)            (aggregate + decay)        (score + category)
                                                                    ↓
                                                    Slack alerts / dashboard feed
```

| Module | Lines | What it does |
|---|---:|---|
| `sql_extractor.py` | 67 | Pulls four KPI views from Postgres via SQLAlchemy |
| `kpi_aggregator.py` | 153 | Normalises raw extracts into rolling-window aggregates and computes a directional decay signal per KPI |
| `risk_scorer.py` | 71 | Weighted-decay score, capped at 100, bucketed into Critical / High / Medium / Low |
| `alert_dispatcher.py` | 31 | Posts alerts to a Slack webhook |
| `dashboard_feed.py` | 159 | RAG-coloured feed for a dashboard, read from Postgres |

The four SQL views are in the repository root (`v_client_aht_trend.sql`, `v_client_csat_trend.sql`, `v_client_fcr_trend.sql`, `v_client_sla_trend.sql`).

**The scoring logic, which is the one piece of real thinking here.** Each KPI carries a weight and a direction, because more of a good KPI is not always better:

| KPI | Weight | Worse when |
|---|---:|---|
| CSAT | 0.40 | lower |
| SLA | 0.30 | lower |
| FCR | 0.20 | lower |
| AHT | 0.10 | **higher** |

Risk per KPI is `decay × weight × 100`; the client's score is the sum, capped at 100. Thresholds are Critical ≥ 70, High ≥ 50, Medium ≥ 30. Weights and thresholds are read from `risk_thresholds.yaml`, so the model is configurable rather than hard-coded. That is a weighted heuristic, **not** a fitted model — no training, no coefficients, no validation against outcomes.

`docker-compose.yml` starts Postgres 15 and **fails closed** if `POSTGRES_PASSWORD` is unset. That part is sound and worth keeping.

## What does not work

Stated plainly, because a reader who clones this deserves to know before spending an afternoon on it:

- **The test suite cannot run.** `risk_scorer.py`, `sql_extractor.py`, and `alert_dispatcher.py` all do `from shared_utils import ConfigManager`. There is no `shared_utils` package in this repository — it was never copied across from the WFM calculator, where the same module does exist. Measured: `ModuleNotFoundError: No module named 'shared_utils'`.
- **Two config paths point at directories that do not exist.** `risk_scorer.py` reads `config/risk_thresholds.yaml` and `data/normalized_kpi.parquet`. There is no `config/` directory (the YAML is at the repository root) and no `data/` directory.
- **No input data of any kind is in the repository.** Every stage needs a Parquet file that nothing produces, because the SQL views require a live Postgres instance that is not provided.
- **No sentiment analysis exists.** Nothing in the code reads text. There is no NLP dependency, no language model, and no text-scoring function.
- **No churn model exists.** There is no logistic regression, no scikit-learn, and no fitted coefficients anywhere in the repository.
- **The declared stack is aspirational.** `requirements.txt` is pandas, pyarrow, fastparquet, sqlalchemy, psycopg2-binary, requests, python-dotenv, pyyaml, and numpy. Earlier revisions of this file listed Transformers/OpenAI, Scikit-learn, Prefect, PostgreSQL, and Streamlit; **four of those five are not in the manifest and are not imported anywhere.**
- **`alert_dispatcher.py` is a sketch, not a module.** Its body contains the comment `# Using your existing CRM mapping logic...` and reads a `SLACK_WEBHOOK_URL` key that `config.json` does not define.

## Repository hygiene, and a security record

Four files in this repository are debris and should be removed rather than described:

- `pyvenv.cfg` and `greenlet.h` — virtual-environment artefacts committed by accident.
- `onfig.env.example.txt` — a mistyped duplicate of `.env.example`.
- `src_sql_extractor.py` — an unmodified duplicate of `sql_extractor.py`.
- `config.json` — contains placeholder database fields (`"DB_PASS": "your_password"`). No credential is exposed, but a file with that shape invites someone to fill it in and commit it.

**`SECURITY_DECISIONS.md` is the most valuable file in this repository.** It records that a real `.env` with a plaintext database password was committed to this public repository in `a78d5d8`, how it happened (a `venv`-generated `.gitignore` whose only rule was `*`, plus a GitHub web upload that does not consult `.gitignore`), and five outstanding actions with owners and statuses.

**The credential state, stated precisely: rotated, still present in git history, no longer valid.** The owner confirmed on 2026-09-25 that the exposed credential had already been rotated, so the value that was committed is dead and cannot be used to authenticate against anything. Removing the file from the working tree and the index did not remove it from history — the blob remains reachable from `a78d5d8`, and anyone who cloned before 2026-09-25 still holds it. Because the credential is rotated, `SECURITY_DECISIONS.md` scopes the residual risk as **information disclosure only**: the database host, port, name, and username, plus knowledge of the password format the owner uses elsewhere — and that format is the real concern, because a pattern reused across services is a lateral-movement risk even after one instance is rotated.

What remains genuinely outstanding is the history purge (action 3), enabling GitHub secret scanning and push protection (action 4), and confirming the password pattern is not reused on any other service (action 2). An earlier revision of this file claimed the purge had been done. It had not.

## If you want to run the scoring logic

The engine itself is small and readable, and it works once its dependencies are satisfied. Minimum path:

```bash
# 1. Provide the missing module (or replace the import with plain config reads).
#    shared_utils.ConfigManager is a thin wrapper over config.json + environment.
# 2. Put a normalised KPI Parquet at the path the scorer expects:
#    columns: client_id, kpi, decay_score
# 3. Then:
pip install pandas pyarrow
python -c "from risk_scorer import score_clients; print(score_clients('normalized_kpi.parquet'))"
```

`categorise_risk(score, thresholds)` in `risk_scorer.py` is pure and has no imports beyond the module-level config, so it can be lifted out and used on its own.

> [!WARNING]
> **Honest boundary.** This is a learning exercise. It was never deployed, never connected to a live CRM, telephony, or ticketing system, and never ran against a real account population. It has no authentication, no access control, and no tenant isolation. No revenue was realised. There is no external audit, no certified data isolation, and no signed security review.
>
> Earlier revisions of this file carried business-impact figures (a churn-rate reduction, a detection-latency improvement, a throughput gain, an accuracy claim). None had a recorded baseline, sample, or method, so none are repeated here. The word "Verified" appeared against the sentiment-accuracy row; no accuracy measurement was ever recorded.

## Related work

- [Helix Prime](https://github.com/HatemIsmailShalaby1979/Helix-Prime) — the operations core; its CX engine is where this thinking ended up
- [Helix Education](https://github.com/HatemIsmailShalaby1979/Helix-Education) — event-sourced learning engine
- [Study Studio](https://github.com/HatemIsmailShalaby1979/Study-Studio) — local-first AI tutor
- [L&D Command Center](https://github.com/HatemIsmailShalaby1979/L-D-Command-Center) — desktop learning and career workstation
- [Blue Waves](https://github.com/HatemIsmailShalaby1979/Blue-Waves-) — content studio
- [Full portfolio](https://github.com/HatemIsmailShalaby1979) — how this fits the wider work

### The other 2026 building attempts

- [WFM Forecasting Calculator](https://github.com/HatemIsmailShalaby1979/wfm-forecasting-calculator)
- [RTA Command Center](https://github.com/HatemIsmailShalaby1979/RTA_command_center)
- [Dynamic Ops Automation Engine](https://github.com/HatemIsmailShalaby1979/Dynamic-Ops-Automation-Engine)

## Author

Built by Hatem Ismail Shalaby, Contact Centre Operations & AI Implementation Lead | WFM & CX Transformation. Background: https://github.com/HatemIsmailShalaby1979

## Licence

MIT
