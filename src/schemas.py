"""Pydantic request and response schemas for LPDG REST API."""

from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field


class GatewayRankingItem(BaseModel):
    """Model representing a single ranked gateway recommendation."""

    rank: int = Field(..., description="Rank within the week (1 to 15)", ge=1, le=15)
    gateway_id: str = Field(..., description="12-character uppercase gateway identifier")
    score: float = Field(..., description="Calculated operational risk score")
    reason: str = Field(..., description="Evidence-based dispatch justification (<= 300 chars)", max_length=300)


class WeeklyRankingsResponse(BaseModel):
    """Response payload for weekly top-15 gateway ranking."""

    week_start: str = Field(..., description="Reporting Monday date (YYYY-MM-DD)")
    total_ranked: int = Field(..., description="Number of ranked gateways returned")
    ranker_type: str = Field(..., description="Name of the active ranking algorithm")
    rankings: list[GatewayRankingItem] = Field(..., description="Ordered list of recommended gateway visits")


class GatewayDetailResponse(BaseModel):
    """Detailed operational breakdown for a specific gateway."""

    gateway_id: str = Field(..., description="12-character uppercase gateway identifier")
    week_start: str = Field(..., description="Target week date (YYYY-MM-DD)")
    rank: int | None = Field(None, description="Rank if in top 15, otherwise null")
    score: float | None = Field(None, description="Calculated risk score")
    reason: str | None = Field(None, description="Generated dispatch reason")
    is_recommended_visit: bool = Field(..., description="True if selected in top 15 visit quota")
    metrics: dict[str, Any] = Field(default_factory=dict, description="Raw operational feature indicators")


class GatewayHistoryEntry(BaseModel):
    """Weekly snapshot entry for gateway history."""

    week_start: str = Field(..., description="Reporting Monday date (YYYY-MM-DD)")
    rank: int | None = Field(None, description="Rank if in top 15, otherwise null")
    score: float = Field(..., description="Calculated risk score")
    offline_hours: float = Field(..., description="Cumulative offline duration in hours")
    silent_hours: int = Field(..., description="Missing telemetry hours")
    meter_fail_rate: float = Field(..., description="Meter reading failure rate")
    is_recommended_visit: bool = Field(..., description="Whether a visit was recommended this week")


class GatewayHistoryResponse(BaseModel):
    """Historical multi-week trend for a specific gateway."""

    gateway_id: str = Field(..., description="12-character uppercase gateway identifier")
    weeks_evaluated: int = Field(..., description="Total number of evaluation weeks analyzed")
    history: list[GatewayHistoryEntry] = Field(..., description="Chronological weekly operational snapshots")


class FleetSummaryResponse(BaseModel):
    """High-level operational health summary across the entire gateway fleet."""

    week_start: str = Field(..., description="Reporting Monday date (YYYY-MM-DD)")
    total_gateways_monitored: int = Field(..., description="Total active gateways in fleet")
    gateways_with_3sigma_breaches: int = Field(..., description="Number of gateways exhibiting 3-sigma spikes")
    silent_gateways_count: int = Field(..., description="Number of gateways with >24h telemetry silence")
    avg_fleet_meter_fail_rate: float = Field(..., description="Average fleet-wide meter read failure rate")
    recommended_visits_count: int = Field(..., description="Total gateways prioritized for field dispatch (max 15)")


class RunPipelineResponse(BaseModel):
    """Response payload for re-running the prioritization pipeline."""

    status: str = Field(..., description="Execution status")
    rows_generated: int = Field(..., description="Total prediction rows produced")
    weeks_processed: int = Field(..., description="Number of scored weeks evaluated")
    ranker_used: str = Field(..., description="Ranking algorithm applied")
    output_path: str = Field(..., description="Location of the generated predictions CSV")


class HealthResponse(BaseModel):
    """Health and liveness status of the prioritization service."""

    status: str = Field("healthy", description="Service health state")
    version: str = Field(..., description="Application version")
    data_dir: str = Field(..., description="Active mounted data directory")
    data_dir_exists: bool = Field(..., description="Whether the data directory is present on disk")
    available_weeks: list[str] = Field(..., description="List of supported scored week dates")
    available_rankers: list[str] = Field(..., description="List of registered ranking algorithms")


class ErrorResponse(BaseModel):
    """Standardized error payload."""

    error: str = Field(..., description="Error classification")
    message: str = Field(..., description="Human-readable error explanation")
    status_code: int = Field(..., description="HTTP status code")
