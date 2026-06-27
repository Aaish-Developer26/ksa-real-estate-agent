"""Defines shared pytest fixtures for the test suite."""

from __future__ import annotations

import pytest

from src.core.state import AgentState, CleanedListing, RawListing


@pytest.fixture
def sample_raw_listing() -> RawListing:
    """Return a fully populated raw listing for an Olaya villa.

    Returns:
        A ``RawListing`` instance with realistic Olaya villa data.
    """
    return RawListing(
        listing_id="RYD-0001",
        source_url="https://aqar.sa/listing/ryd-0001",
        raw_title="Luxury villa for sale in Olaya",
        raw_price="4,500,000 SAR",
        raw_area="300 م²",
        raw_location="Olaya",
        raw_property_type="Villa",
        raw_description="Luxury villa located in Olaya, Riyadh.",
        rera_number="RERA-123456",
        is_waqf=False,
        scraped_at="2026-06-01T12:00:00+00:00",
    )


@pytest.fixture
def sample_cleaned_listing() -> CleanedListing:
    """Return a fully populated cleaned listing.

    Returns:
        A ``CleanedListing`` instance with all fields populated.
    """
    return CleanedListing(
        listing_id="RYD-0001",
        source_url="https://aqar.sa/listing/ryd-0001",
        title_en="Luxury villa for sale in Olaya",
        price_sar=4_500_000.0,
        area_sqm=300.0,
        price_per_sqm=15_000.0,
        district="Olaya",
        property_type="villa",
        rera_number="RERA-123456",
        is_waqf=False,
        is_foreign_ownership_restricted=False,
        normalized_at="2026-06-01T12:00:00+00:00",
    )


@pytest.fixture
def sample_agent_state(sample_raw_listing: RawListing) -> AgentState:
    """Return an agent state pre-populated with three raw listings.

    Args:
        sample_raw_listing: The base raw listing fixture, reused three times.

    Returns:
        An ``AgentState`` instance with ``run_id="test-run-001"`` and three
        raw listings.
    """
    return AgentState(
        run_id="test-run-001",
        raw_listings=[sample_raw_listing, sample_raw_listing, sample_raw_listing],
    )
