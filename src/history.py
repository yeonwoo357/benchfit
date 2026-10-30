import json
import os
import re
from datetime import datetime, timezone

LOG_PATH = os.path.join(os.path.dirname(__file__), "..", "evaluation_log.json")


def load_history():
    if not os.path.exists(LOG_PATH):
        return []
    with open(LOG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def log_run(industry, stage, business_model, channel, campaign_type, audience_type, funnel_stage, metrics):
    """metrics: list of {"metric": name, "actual": value_str} from this run's quant result,
    stored so a later run in the same context can be compared against the marketer's own
    past performance, not just an industry average."""
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "industry": industry,
        "stage": stage,
        "business_model": business_model,
        "channel": channel,
        "campaign_type": campaign_type,
        "audience_type": audience_type,
        "funnel_stage": funnel_stage,
        "metric_count": len(metrics),
        "metrics": metrics,
    }
    history = load_history()
    history.append(entry)
    with open(LOG_PATH, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)
    return entry


def find_previous_run(history, industry, channel, campaign_type):
    """Most recent prior run with the same industry/channel/campaign type. Matching is
    deliberately loose (not on audience type or funnel stage) so a trend comparison is
    still offered even if the marketer narrows those on a later run."""
    matches = [
        h
        for h in history
        if h.get("metrics")
        and h.get("industry", "").strip().lower() == industry.strip().lower()
        and h.get("channel") == channel
        and h.get("campaign_type", "").strip().lower() == campaign_type.strip().lower()
    ]
    if not matches:
        return None
    return max(matches, key=lambda h: h["timestamp"])


def _extract_number(value):
    match = re.search(r"-?\d+\.?\d*", str(value).replace(",", ""))
    return float(match.group()) if match else None


def compute_trend(current_value, previous_value):
    """Returns {"previous": str, "pct_change": float} when both values are numeric and
    comparable, else None (non-numeric metric values, missing data, or divide-by-zero)."""
    cur = _extract_number(current_value)
    prev = _extract_number(previous_value)
    if cur is None or prev is None or prev == 0:
        return None
    return {"previous": previous_value, "pct_change": (cur - prev) / abs(prev) * 100}
