"""Defines the LangGraph master state as a hierarchy of Pydantic models."""

from __future__ import annotations

import operator
import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field


class RawListing(BaseModel):
    """An unvalidated listing as scraped from a data source.

    All fields are optional because source data is dirty, bilingual,
    and inconsistently formatted prior to cleaning.

    Attributes:
        listing_id: Source-provided unique identifier, if any.
        source_url: URL the listing was scraped from.
        raw_title: Listing title, may be Arabic or English.
        raw_price: Unparsed price string (e.g. "1,500,000 SAR" or "١٥٠٠٠٠٠").
        raw_area: Unparsed area string (e.g. "250 م²" or "250 sqm").
        raw_location: District or area name, any language.
        raw_property_type: Unnormalized property type string.
        raw_description: Free-text listing description.
        rera_number: RERA registration number, if disclosed.
        is_waqf: Whether the source flagged this property as Waqf.
        scraped_at: ISO 8601 timestamp of when the listing was scraped.
    """

    listing_id: str | None = None
    source_url: str | None = None
    raw_title: str | None = None
    raw_price: str | None = None
    raw_area: str | None = None
    raw_location: str | None = None
    raw_property_type: str | None = None
    raw_description: str | None = None
    rera_number: str | None = None
    is_waqf: bool = False
    scraped_at: str | None = None


class CleanedListing(BaseModel):
    """A listing that has passed normalization and strict schema validation.

    Attributes:
        listing_id: Unique listing identifier.
        source_url: URL the listing was scraped from.
        title_en: English-normalized listing title.
        price_sar: Listing price in Saudi Riyal.
        area_sqm: Listing area in square meters.
        price_per_sqm: Computed price per square meter (price_sar / area_sqm).
        district: Standardized district name.
        property_type: Normalized property type category.
        rera_number: RERA registration number, if disclosed.
        is_waqf: Whether the property is flagged as Waqf.
        is_foreign_ownership_restricted: Whether foreign ownership is restricted.
        normalized_at: ISO 8601 timestamp of when normalization occurred.
    """

    listing_id: str
    source_url: str = ""
    title_en: str = ""
    price_sar: float = 0.0
    area_sqm: float = 0.0
    price_per_sqm: float = 0.0
    district: str
    property_type: Literal[
        "villa", "apartment", "compound", "land", "commercial", "other"
    ]
    rera_number: str | None = None
    is_waqf: bool = False
    is_foreign_ownership_restricted: bool = False
    normalized_at: str = ""


class ComplianceFlag(BaseModel):
    """A regulatory or statistical compliance flag raised against a listing.

    Attributes:
        listing_id: The listing this flag applies to.
        flag_type: The category of compliance issue detected.
        severity: The severity level of the flag.
        description: Human-readable explanation of the flag.
        flagged_at: ISO 8601 timestamp of when the flag was raised.
    """

    listing_id: str
    flag_type: Literal[
        "missing_rera",
        "waqf_property",
        "foreign_ownership_restricted",
        "price_outlier",
        "area_outlier",
        "vat_applicable",
    ]
    severity: Literal["low", "medium", "high", "critical"]
    description: str
    flagged_at: str


class AgentState(BaseModel):
    """Root LangGraph state passed between all pipeline nodes.

    List fields annotated with ``operator.add`` accumulate across node
    invocations (append semantics); plain fields use last-write semantics.

    Attributes:
        run_id: Unique identifier for this pipeline run.
        created_at: ISO 8601 timestamp of when the run was created.
        current_phase: Name of the pipeline phase currently executing.
        errors: Accumulated structured error records from any node.
        raw_listings: Accumulated raw listings from the Sourcing Agent.
        cleaned_listings: Accumulated cleaned listings from the Cleaning Agent.
        district_benchmarks: District-level price/m² benchmarks from the Analyst Agent.
        undervalued_listing_ids: Listing IDs identified as undervalued.
        analysis_summary: Final narrative analysis summary.
        compliance_flags: Accumulated compliance flags from the Risk Agent.
        compliance_report: Final narrative compliance report.
        investment_report: Final investment-grade due diligence report.
    """

    run_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    current_phase: str = "initialized"
    errors: Annotated[list[dict[str, str]], operator.add] = Field(
        default_factory=list
    )

    raw_listings: Annotated[list[RawListing], operator.add] = Field(
        default_factory=list
    )

    cleaned_listings: Annotated[list[CleanedListing], operator.add] = Field(
        default_factory=list
    )

    district_benchmarks: dict[str, float] = Field(default_factory=dict)
    undervalued_listing_ids: list[str] = Field(default_factory=list)
    analysis_summary: str = ""

    compliance_flags: Annotated[list[ComplianceFlag], operator.add] = Field(
        default_factory=list
    )
    compliance_report: str = ""

    investment_report: str = ""
