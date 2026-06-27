"""FastAPI request and response Pydantic v2 models."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class AnalysisRequest(BaseModel):
    """Request body for POST /analyze endpoint."""

    districts: list[str] = Field(
        default=[
            "Olaya",
            "Al_Malqa",
            "Al_Nakheel",
            "Al_Rawdah",
            "KAFD",
            "Al_Naseem",
        ],
        description="List of Riyadh districts to analyze",
        min_length=1,
    )
    max_listings_per_district: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Maximum listings to fetch per district",
    )
    use_mock_data: bool = Field(
        default=True,
        description="Use mock dataset instead of live search",
    )


class AnalysisResponse(BaseModel):
    """Response for POST /analyze — returns immediately with run_id."""

    run_id: str = Field(description="Unique pipeline run identifier")
    status: Literal["queued"] = "queued"
    status_url: str = Field(description="Poll this URL for results")
    message: str = "Analysis pipeline queued successfully"


class RunStatusResponse(BaseModel):
    """Response for GET /analyze/{run_id}."""

    run_id: str
    status: Literal["queued", "running", "complete", "failed"]
    current_phase: str
    created_at: str
    completed_at: str | None = None
    investment_report: str | None = None
    error: str | None = None


class HealthResponse(BaseModel):
    """Response for GET /health."""

    status: Literal["healthy", "degraded", "unhealthy"]
    database: str
    redis: str
    version: str = "0.1.0"


class ListingResponse(BaseModel):
    """Single listing record for GET /listings/{district}."""

    listing_id: str
    title_en: str
    price_sar: float
    area_sqm: float
    price_per_sqm: float
    district: str
    property_type: str
    rera_number: str | None
    is_waqf: bool


class DistrictListingsResponse(BaseModel):
    """Response for GET /listings/{district}."""

    district: str
    total: int
    listings: list[ListingResponse]
    avg_price_per_sqm: float | None = None
