"""FastAPI REST API Service for LPDG Gateway Prioritization (Part 2: Track B)."""

from __future__ import annotations

import datetime as dt
import pathlib
import threading
from typing import Any

from fastapi import FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import pandas as pd

from src import __version__
from src.config import SCORED_WEEKS
from src.data_loader import (
    load_engineer_review,
    load_gateway_master,
    load_meter_reads,
    load_telemetry,
    normalize_gateway_id,
)
from src.features import extract_features_for_week
from src.pipeline import run_pipeline
from src.ranker import RANKER_REGISTRY, get_ranker
from src.reason_generator import build_reason
from src.schemas import (
    ErrorResponse,
    FleetSummaryResponse,
    GatewayDetailResponse,
    GatewayHistoryEntry,
    GatewayHistoryResponse,
    GatewayRankingItem,
    HealthResponse,
    RunPipelineResponse,
    WeeklyRankingsResponse,
)

app = FastAPI(
    title="LPDG Gateway Fleet Health & Field Visit API",
    description=(
        "REST API service for automated field visit ranking, gateway diagnostics, "
        "and on-demand pipeline execution across LPDG's utility radio network."
    ),
    version=__version__,
    responses={
        400: {"model": ErrorResponse, "description": "Bad Request"},
        404: {"model": ErrorResponse, "description": "Not Found"},
        422: {"model": ErrorResponse, "description": "Unprocessable Entity"},
        500: {"model": ErrorResponse, "description": "Internal Server Error"},
    },
)

# CORS middleware for open accessibility
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Execution lock to safely handle concurrent /run calls
_RUN_LOCK = threading.Lock()
DEFAULT_DATA_DIR = pathlib.Path("data")
DEFAULT_OUT_CSV = pathlib.Path("predictions.csv")


def _discover_latest_monday_on_disk(data_dir: pathlib.Path) -> dt.date:
    """Dynamically discover the most recent Monday on disk with available telemetry."""
    try:
        telemetry = load_telemetry(data_dir)
        if not telemetry.empty and "ts" in telemetry.columns:
            max_ts = telemetry["ts"].max()
            if pd.notna(max_ts):
                max_date = max_ts.date()
                candidate_monday = max_date - dt.timedelta(days=max_date.weekday())
                # If fresh unseen partitions exist beyond standard challenge period (April 2026+), return newest Monday
                if candidate_monday > dt.date(2026, 3, 31):
                    return candidate_monday
    except Exception:
        pass
    return SCORED_WEEKS[-1]


def _get_target_monday(week_str: str | None, data_dir: pathlib.Path = DEFAULT_DATA_DIR) -> dt.date:
    """Parse and validate week date string against Monday temporal boundaries.
    
    Supports:
      - None or 'first': Defaults to the first evaluation week (2026-02-02)
      - 'latest': Dynamically discovers the newest available Monday from on-disk telemetry
      - ISO Monday dates: Any valid Monday (e.g. 2026-02-09 or unseen live-session dates like 2026-04-06)
    """
    if not week_str or week_str.strip().lower() in ("default", "first"):
        return SCORED_WEEKS[0]

    if week_str.strip().lower() == "latest":
        return _discover_latest_monday_on_disk(data_dir)

    try:
        parsed_date = dt.date.fromisoformat(week_str.strip())
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid date format '{week_str}'. Use ISO format YYYY-MM-DD (e.g. 2026-02-02).",
        )

    # In utility operations, dispatch decisions happen strictly on Monday boundaries
    if parsed_date.weekday() != 0:
        nearest_monday = parsed_date - dt.timedelta(days=parsed_date.weekday())
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Date '{week_str}' is a {parsed_date.strftime('%A')}. "
                f"Field dispatch prioritization strictly operates on Mondays (e.g. '{nearest_monday.isoformat()}')."
            ),
        )

    return parsed_date


def _validate_telemetry_history_bounds(monday: dt.date, telemetry: pd.DataFrame) -> None:
    """Ensure requested Monday does not precede the start of available telemetry observations."""
    if not telemetry.empty and "ts" in telemetry.columns:
        min_date = telemetry["ts"].min().date()
        if monday < min_date:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Requested evaluation date '{monday.isoformat()}' precedes available telemetry history. "
                    f"Telemetry observations on disk begin on '{min_date.isoformat()}'."
                ),
            )


@app.get("/health", response_model=HealthResponse, tags=["System Health"])
def get_health() -> HealthResponse:
    """Return system health status, active data path, and available algorithms."""
    return HealthResponse(
        status="healthy",
        version=__version__,
        data_dir=str(DEFAULT_DATA_DIR),
        data_dir_exists=DEFAULT_DATA_DIR.exists(),
        available_weeks=[w.isoformat() for w in SCORED_WEEKS],
        available_rankers=list(RANKER_REGISTRY.keys()),
    )


@app.get("/fleet/status", tags=["System Health"])
def get_fleet_quick_status():
    """Quick summary of active system configuration."""
    return {
        "status": "operational",
        "scored_weeks_count": len(SCORED_WEEKS),
        "default_ranker": "composite",
        "quota_per_week": 15
    }


@app.get("/fleet/summary", response_model=FleetSummaryResponse, tags=["Fleet Rankings"])
def get_fleet_summary(
    week: str | None = Query(
        None,
        description="Target Monday date (YYYY-MM-DD, 'latest', or leave empty for default 2026-02-02).",
    ),
) -> FleetSummaryResponse:
    """Retrieve high-level operational health statistics across the entire gateway fleet."""
    target_monday = _get_target_monday(week, DEFAULT_DATA_DIR)

    if not DEFAULT_DATA_DIR.exists():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Data directory '{DEFAULT_DATA_DIR}' not found on server.",
        )

    telemetry = load_telemetry(DEFAULT_DATA_DIR)
    _validate_telemetry_history_bounds(target_monday, telemetry)

    gateway_master = load_gateway_master(DEFAULT_DATA_DIR)
    meter_reads = load_meter_reads(DEFAULT_DATA_DIR)
    engineer_review = load_engineer_review(DEFAULT_DATA_DIR)

    features = extract_features_for_week(
        monday=target_monday,
        telemetry=telemetry,
        gateway_master=gateway_master,
        meter_reads=meter_reads,
        engineer_review=engineer_review,
    )

    total_monitored = len(features)
    spike_count = int((features["flagged_hours"] > 0).sum())
    silent_count = int((features["silent_hours"] > 24).sum())
    avg_fail_rate = round(float(features["meter_fail_rate"].mean()), 4)

    return FleetSummaryResponse(
        week_start=target_monday.isoformat(),
        total_gateways_monitored=total_monitored,
        gateways_with_3sigma_breaches=spike_count,
        silent_gateways_count=silent_count,
        avg_fleet_meter_fail_rate=avg_fail_rate,
        recommended_visits_count=min(15, total_monitored),
    )


@app.get("/rankings", response_model=WeeklyRankingsResponse, tags=["Fleet Rankings"])
def get_weekly_rankings(
    week: str | None = Query(
        None,
        description="Target Monday date (YYYY-MM-DD, 'latest', or leave empty for default 2026-02-02).",
    ),
    ranker: str = Query(
        "composite",
        description="Ranking strategy: 'composite' (multi-source + cooldown) or 'baseline' (3-sigma).",
    ),
) -> WeeklyRankingsResponse:
    """Retrieve the top 15 gateways prioritized for field dispatch in the requested week."""
    target_monday = _get_target_monday(week, DEFAULT_DATA_DIR)

    try:
        ranker_instance = get_ranker(ranker)
    except ValueError as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err))

    if not DEFAULT_DATA_DIR.exists():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Data directory '{DEFAULT_DATA_DIR}' not found on server.",
        )

    try:
        telemetry = load_telemetry(DEFAULT_DATA_DIR)
        _validate_telemetry_history_bounds(target_monday, telemetry)

        gateway_master = load_gateway_master(DEFAULT_DATA_DIR)
        meter_reads = load_meter_reads(DEFAULT_DATA_DIR)
        engineer_review = load_engineer_review(DEFAULT_DATA_DIR)

        week_idx = SCORED_WEEKS.index(target_monday) if target_monday in SCORED_WEEKS else max(0, (target_monday - SCORED_WEEKS[0]).days // 7)
        features = extract_features_for_week(
            monday=target_monday,
            telemetry=telemetry,
            gateway_master=gateway_master,
            meter_reads=meter_reads,
            engineer_review=engineer_review,
        )

        ranked_df, _ = ranker_instance.rank_week(
            monday=target_monday,
            features=features,
            recent_visits={},
            week_idx=week_idx,
        )

        items = [
            GatewayRankingItem(
                rank=int(r["rank"]),
                gateway_id=str(r["gateway_id"]),
                score=float(r["score"]),
                reason=str(r["reason"]),
            )
            for _, r in ranked_df.iterrows()
        ]

        return WeeklyRankingsResponse(
            week_start=target_monday.isoformat(),
            total_ranked=len(items),
            ranker_type=ranker_instance.name,
            rankings=items,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ranking computation failed: {exc}",
        )


@app.get("/gateways/{gateway_id}", response_model=GatewayDetailResponse, tags=["Gateway Diagnostics"])
def get_gateway_details(
    gateway_id: str,
    week: str | None = Query(
        None,
        description="Target Monday date (YYYY-MM-DD, 'latest', or leave empty for default 2026-02-02).",
    ),
    ranker: str = Query(
        "composite",
        description="Ranking strategy: 'composite' or 'baseline'.",
    ),
) -> GatewayDetailResponse:
    """Retrieve operational diagnostics and ranking status for a specific gateway."""
    norm_id = normalize_gateway_id(gateway_id)
    if not norm_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid gateway identifier format: '{gateway_id}'",
        )

    target_monday = _get_target_monday(week, DEFAULT_DATA_DIR)

    try:
        ranker_instance = get_ranker(ranker)
    except ValueError as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err))

    if not DEFAULT_DATA_DIR.exists():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Data directory '{DEFAULT_DATA_DIR}' not found on server.",
        )

    telemetry = load_telemetry(DEFAULT_DATA_DIR)
    _validate_telemetry_history_bounds(target_monday, telemetry)

    gateway_master = load_gateway_master(DEFAULT_DATA_DIR)
    meter_reads = load_meter_reads(DEFAULT_DATA_DIR)
    engineer_review = load_engineer_review(DEFAULT_DATA_DIR)

    week_idx = SCORED_WEEKS.index(target_monday) if target_monday in SCORED_WEEKS else max(0, (target_monday - SCORED_WEEKS[0]).days // 7)
    features = extract_features_for_week(
        monday=target_monday,
        telemetry=telemetry,
        gateway_master=gateway_master,
        meter_reads=meter_reads,
        engineer_review=engineer_review,
    )

    gw_row = features[features["gateway_id"] == norm_id]
    if gw_row.empty:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Gateway '{norm_id}' not found in network registry for week {target_monday.isoformat()}.",
        )

    ranked_df, _ = ranker_instance.rank_week(
        monday=target_monday,
        features=features,
        recent_visits={},
        week_idx=week_idx,
    )

    match = ranked_df[ranked_df["gateway_id"] == norm_id]
    row_data = gw_row.iloc[0]

    raw_metrics: dict[str, Any] = {
        "flagged_hours_3sigma": int(row_data.get("flagged_hours", 0)),
        "worst_metric": str(row_data.get("worst_metric", "")),
        "total_offline_hours": round(float(row_data.get("offline_hours", 0.0)), 2),
        "total_disconnects": int(row_data.get("total_disconnects", 0)),
        "total_reboots": int(row_data.get("total_reboots", 0)),
        "silent_hours": int(row_data.get("silent_hours", 0)),
        "meter_fail_rate": round(float(row_data.get("meter_fail_rate", 0.0)), 4),
        "expert_review_schlecht": bool(row_data.get("expert_schlecht", 0)),
    }

    if not match.empty:
        rank_val = int(match.iloc[0]["rank"])
        score_val = float(match.iloc[0]["score"])
        reason_val = str(match.iloc[0]["reason"])
        is_rec = True
    else:
        rank_val = None
        score_val = None
        reason_val = build_reason(row_data)
        is_rec = False

    return GatewayDetailResponse(
        gateway_id=norm_id,
        week_start=target_monday.isoformat(),
        rank=rank_val,
        score=score_val,
        reason=reason_val,
        is_recommended_visit=is_rec,
        metrics=raw_metrics,
    )


@app.get("/gateways/{gateway_id}/history", response_model=GatewayHistoryResponse, tags=["Gateway Diagnostics"])
def get_gateway_history(
    gateway_id: str,
    ranker: str = Query(
        "composite",
        description="Ranking strategy: 'composite' or 'baseline'.",
    ),
) -> GatewayHistoryResponse:
    """Retrieve multi-week historical performance and visit recommendations for a gateway."""
    norm_id = normalize_gateway_id(gateway_id)
    if not norm_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid gateway identifier format: '{gateway_id}'",
        )

    try:
        ranker_instance = get_ranker(ranker)
    except ValueError as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err))

    if not DEFAULT_DATA_DIR.exists():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Data directory '{DEFAULT_DATA_DIR}' not found on server.",
        )

    telemetry = load_telemetry(DEFAULT_DATA_DIR)
    gateway_master = load_gateway_master(DEFAULT_DATA_DIR)
    meter_reads = load_meter_reads(DEFAULT_DATA_DIR)
    engineer_review = load_engineer_review(DEFAULT_DATA_DIR)

    history_entries: list[GatewayHistoryEntry] = []
    recent_visits: dict[str, int] = {}

    for week_idx, monday in enumerate(SCORED_WEEKS):
        features = extract_features_for_week(
            monday=monday,
            telemetry=telemetry,
            gateway_master=gateway_master,
            meter_reads=meter_reads,
            engineer_review=engineer_review,
        )

        gw_row = features[features["gateway_id"] == norm_id]
        if gw_row.empty:
            continue

        ranked_df, selected_ids = ranker_instance.rank_week(
            monday=monday,
            features=features,
            recent_visits=recent_visits,
            week_idx=week_idx,
        )

        # Update visit tracking for cooldown
        for gid in selected_ids:
            recent_visits[gid] = week_idx

        row_data = gw_row.iloc[0]
        match = ranked_df[ranked_df["gateway_id"] == norm_id]

        if not match.empty:
            rank_val = int(match.iloc[0]["rank"])
            score_val = float(match.iloc[0]["score"])
            is_rec = True
        else:
            rank_val = None
            score_val = round(float(row_data.get("flagged_hours", 0)), 2)
            is_rec = False

        history_entries.append(
            GatewayHistoryEntry(
                week_start=monday.isoformat(),
                rank=rank_val,
                score=score_val,
                offline_hours=round(float(row_data.get("offline_hours", 0.0)), 2),
                silent_hours=int(row_data.get("silent_hours", 0)),
                meter_fail_rate=round(float(row_data.get("meter_fail_rate", 0.0)), 4),
                is_recommended_visit=is_rec,
            )
        )

    if not history_entries:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Gateway '{norm_id}' has no historical records in the fleet.",
        )

    return GatewayHistoryResponse(
        gateway_id=norm_id,
        weeks_evaluated=len(history_entries),
        history=history_entries,
    )


@app.post("/run", response_model=RunPipelineResponse, tags=["Pipeline Operations"])
def trigger_run_pipeline(
    ranker: str = Query(
        "composite",
        description="Ranking strategy to apply ('composite' or 'baseline').",
    ),
    out: str = Query(
        "predictions.csv",
        description="Destination filename for predictions output.",
    ),
) -> RunPipelineResponse:
    """Re-execute the prioritization pipeline over mounted data without restarting the server."""
    if not _RUN_LOCK.acquire(blocking=False):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A pipeline ranking run is currently in progress. Please retry shortly.",
        )

    try:
        ranker_instance = get_ranker(ranker)
        out_path = pathlib.Path(out)

        predictions_df = run_pipeline(
            data_dir=DEFAULT_DATA_DIR,
            output_path=out_path,
            ranker=ranker_instance,
        )

        return RunPipelineResponse(
            status="completed",
            rows_generated=len(predictions_df),
            weeks_processed=predictions_df["week_start"].nunique(),
            ranker_used=ranker_instance.name,
            output_path=str(out_path),
        )
    finally:
        _RUN_LOCK.release()
