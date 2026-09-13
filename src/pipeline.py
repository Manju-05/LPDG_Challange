"""End-to-end Part 1 pipeline orchestrator."""

from __future__ import annotations

import pathlib
import pandas as pd

from src.config import SCORED_WEEKS
from src.data_loader import (
    load_engineer_review,
    load_field_visits,
    load_gateway_master,
    load_meter_reads,
    load_telemetry,
)
from src.features import extract_features_for_week
from src.ranker import rank_gateways_for_week


def run_pipeline(data_dir: pathlib.Path, output_path: pathlib.Path) -> pd.DataFrame:
    """Execute the complete Part 1 ranking pipeline across all 8 scored weeks."""
    print(f"Loading datasets from {data_dir}...")
    telemetry = load_telemetry(data_dir)
    gateway_master = load_gateway_master(data_dir)
    meter_reads = load_meter_reads(data_dir)
    engineer_review = load_engineer_review(data_dir)

    print(f"Telemetry loaded: {len(telemetry)} rows across {telemetry['gateway_id'].nunique()} gateways.")

    weekly_results: list[pd.DataFrame] = []
    recent_visits: dict[str, int] = {}

    for week_idx, monday in enumerate(SCORED_WEEKS):
        print(f"Generating ranking for week {week_idx + 1}/8: {monday.isoformat()}...")
        features = extract_features_for_week(
            monday=monday,
            telemetry=telemetry,
            gateway_master=gateway_master,
            meter_reads=meter_reads,
            engineer_review=engineer_review,
        )

        ranked_df, selected_ids = rank_gateways_for_week(
            monday=monday,
            features=features,
            recent_visits=recent_visits,
            week_idx=week_idx,
        )

        weekly_results.append(ranked_df)

        # Update visit history
        for gid in selected_ids:
            recent_visits[gid] = week_idx

    final_predictions = pd.concat(weekly_results, ignore_index=True)

    # Ensure output parent directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)
    final_predictions.to_csv(output_path, index=False)
    print(f"Successfully generated {output_path} with {len(final_predictions)} rows.")

    return final_predictions
