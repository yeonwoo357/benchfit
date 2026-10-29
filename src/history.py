import json
import os
from datetime import datetime, timezone

LOG_PATH = os.path.join(os.path.dirname(__file__), "..", "evaluation_log.json")


def load_history():
    if not os.path.exists(LOG_PATH):
        return []
    with open(LOG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def log_run(industry, stage, business_model, channel, campaign_type, metric_count):
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "industry": industry,
        "stage": stage,
        "business_model": business_model,
        "channel": channel,
        "campaign_type": campaign_type,
        "metric_count": metric_count,
    }
    history = load_history()
    history.append(entry)
    with open(LOG_PATH, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)
