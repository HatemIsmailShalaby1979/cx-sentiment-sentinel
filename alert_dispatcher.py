"""
alert_dispatcher.py
-------------------
Dispatches risk alerts to Slack.
"""
import requests
import pandas as pd
from shared_utils import ConfigManager

# Load shared config (expects SLACK_WEBHOOK_URL in config.json or env)
config = ConfigManager()

def dispatch_alerts(scored_path: str, crm_path: str):
    df = pd.read_parquet(scored_path)
    # Using your existing CRM mapping logic...
    # (Assuming you keep crm_mapping.yaml as a static reference)
    
    webhook_url = config.get("SLACK_WEBHOOK_URL")
    actionable_risk = df[df["risk_category"].isin(["Critical", "High"])]
    
    if actionable_risk.empty:
        print("[OK] No critical or high-risk clients.")
        return
        
    for _, row in actionable_risk.iterrows():
        # ... (keep your existing Slack message construction logic)
        msg = f"🚨 *{row['risk_category']} Risk Alert* 🚨\nClient: {row['client_id']}"
        
        if webhook_url:
            requests.post(webhook_url, json={"text": msg}, timeout=5)
            
    print(f"[OK] Dispatched {len(actionable_risk)} alerts.")