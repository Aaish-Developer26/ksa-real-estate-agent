"""Deterministic compliance and regulatory checking tools.

Pure deterministic Python. No LLM calls. No I/O. All inputs are
primitive Python types.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

FOREIGN_OWNERSHIP_APPROVED_ZONES: set[str] = {"KAFD", "Diplomatic_Quarter", "DQ"}

COMMERCIAL_PROPERTY_TYPES: set[str] = {"commercial"}


def _now_iso() -> str:
    """Return the current UTC timestamp as an ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()


def check_rera_compliance(
    listing_id: str,
    rera_number: str | None,
) -> dict[str, Any] | None:
    """Check RERA registration compliance.

    Args:
        listing_id: The listing being checked.
        rera_number: The listing's RERA registration number, if any.

    Returns:
        A compliance flag dict if rera_number is missing, else None.
    """
    if rera_number:
        return None
    return {
        "listing_id": listing_id,
        "flag_type": "missing_rera",
        "severity": "high",
        "description": "Listing is missing a RERA registration number.",
        "flagged_at": _now_iso(),
    }


def check_waqf_status(
    listing_id: str,
    is_waqf: bool,
) -> dict[str, Any] | None:
    """Return a critical compliance flag if the listing is a Waqf property.

    Waqf properties are Islamic endowments and are legally non-transferable.

    Args:
        listing_id: The listing being checked.
        is_waqf: Whether the listing is flagged as Waqf.

    Returns:
        A critical compliance flag dict if is_waqf is True, else None.
    """
    if not is_waqf:
        return None
    return {
        "listing_id": listing_id,
        "flag_type": "waqf_property",
        "severity": "critical",
        "description": (
            "Listing is a Waqf (Islamic endowment) property and cannot be "
            "legally sold or transferred."
        ),
        "flagged_at": _now_iso(),
    }


def check_foreign_ownership(
    listing_id: str,
    district: str | None,
    is_foreign_ownership_restricted: bool,
) -> dict[str, Any] | None:
    """Flag listings in zones restricted to foreign buyers.

    Args:
        listing_id: The listing being checked.
        district: Standardized district name.
        is_foreign_ownership_restricted: Whether this listing's class is
            restricted for foreign ownership.

    Returns:
        A high severity compliance flag dict if the district is not in
        FOREIGN_OWNERSHIP_APPROVED_ZONES and restriction applies, else None.
    """
    if not is_foreign_ownership_restricted:
        return None
    if district in FOREIGN_OWNERSHIP_APPROVED_ZONES:
        return None
    return {
        "listing_id": listing_id,
        "flag_type": "foreign_ownership_restricted",
        "severity": "high",
        "description": (
            f"District '{district}' is not an approved zone for foreign "
            "ownership."
        ),
        "flagged_at": _now_iso(),
    }


def check_vat_applicability(
    listing_id: str,
    property_type: str,
) -> dict[str, Any] | None:
    """Flag commercial listings for 15% VAT applicability.

    Args:
        listing_id: The listing being checked.
        property_type: Normalized property type.

    Returns:
        A low severity informational flag for commercial properties,
        else None.
    """
    if property_type not in COMMERCIAL_PROPERTY_TYPES:
        return None
    return {
        "listing_id": listing_id,
        "flag_type": "vat_applicable",
        "severity": "low",
        "description": "Commercial property is subject to 15% VAT.",
        "flagged_at": _now_iso(),
    }


def run_all_compliance_checks(
    listing_id: str,
    rera_number: str | None,
    is_waqf: bool,
    district: str | None,
    property_type: str,
    is_foreign_ownership_restricted: bool,
) -> list[dict[str, Any]]:
    """Run all compliance checks for a single listing.

    Args:
        listing_id: The listing being checked.
        rera_number: The listing's RERA registration number, if any.
        is_waqf: Whether the listing is flagged as Waqf.
        district: Standardized district name.
        property_type: Normalized property type.
        is_foreign_ownership_restricted: Whether this listing's class is
            restricted for foreign ownership.

    Returns:
        List of compliance flag dicts (may be empty if listing is clean).
    """
    checks = [
        check_rera_compliance(listing_id, rera_number),
        check_waqf_status(listing_id, is_waqf),
        check_foreign_ownership(listing_id, district, is_foreign_ownership_restricted),
        check_vat_applicability(listing_id, property_type),
    ]
    return [flag for flag in checks if flag is not None]
