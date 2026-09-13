"""Operational reason generator for field operations teams."""

from __future__ import annotations

import pandas as pd

from src.config import MAX_REASON_CHARS


def build_reason(row: pd.Series) -> str:
    """Generate a clear, evidence-based reason for dispatching a field engineer.

    Must be <= 300 characters, non-empty, and written from an operational perspective.
    """
    reasons: list[str] = []

    flagged_hours = int(row.get("flagged_hours", 0))
    worst_metric = str(row.get("worst_metric", "")).strip()
    offline_hours = float(row.get("offline_hours", 0.0))
    disconnects = int(row.get("total_disconnects", 0))
    reboots = int(row.get("total_reboots", 0))
    silent_hours = int(row.get("silent_hours", 0))
    meter_fail_rate = float(row.get("meter_fail_rate", 0.0))
    expert_schlecht = int(row.get("expert_schlecht", 0))

    if flagged_hours > 0:
        metric_desc = worst_metric if worst_metric else "telemetry"
        reasons.append(f"{flagged_hours}h >3-sigma breach on {metric_desc}")

    if offline_hours >= 1.0:
        reasons.append(f"{offline_hours:.1f}h total offline")

    if reboots >= 5:
        reasons.append(f"{reboots} reboots")

    if disconnects >= 10:
        reasons.append(f"{disconnects} disconnects")

    if silent_hours >= 24:
        reasons.append(f"{silent_hours}h telemetry silence")

    if meter_fail_rate >= 0.15:
        reasons.append(f"meter fail rate {meter_fail_rate * 100:.1f}%")

    if expert_schlecht == 1:
        reasons.append("engineer review flagged Schlecht")

    if not reasons:
        # Fallback if selected as baseline/quietest
        if offline_hours > 0:
            reasons.append(f"{offline_hours:.1f}h offline")
        else:
            reasons.append("Routine proactive inspection based on network health baseline")

    full_reason = "; ".join(reasons)
    if len(full_reason) > MAX_REASON_CHARS:
        full_reason = full_reason[: MAX_REASON_CHARS - 3] + "..."

    return full_reason or "Proactive inspection based on baseline risk score."
