"""Listings data API endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status

from src.api.schemas import DistrictListingsResponse, ListingResponse
from src.core.logging_setup import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/listings", tags=["listings"])

VALID_DISTRICTS = {
    "Olaya",
    "Al_Malqa",
    "Al_Nakheel",
    "Al_Rawdah",
    "KAFD",
    "Al_Naseem",
    "Al_Shifa",
    "Al_Wurud",
}


@router.get(
    "/{district}",
    response_model=DistrictListingsResponse,
)
async def get_listings_by_district(
    district: str,
    limit: int = Query(default=50, ge=1, le=200),
) -> DistrictListingsResponse:
    """Retrieve cleaned listings for a specific Riyadh district.

    Queries the database for normalized listings, ordered by
    price_per_sqm ascending (best value first).

    Args:
        district: Canonical district name (e.g. Olaya, KAFD).
        limit: Maximum number of listings to return.

    Returns:
        DistrictListingsResponse with listings and avg price/sqm.

    Raises:
        HTTPException 400: If district name is not valid.
        HTTPException 404: If no listings found for district.
        HTTPException 500: If database query fails.
    """
    from src.mcp_servers.postgres_server.repository import ListingRepository

    if district not in VALID_DISTRICTS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid district '{district}'. "
            f"Valid options: {sorted(VALID_DISTRICTS)}",
        )

    try:
        repo = ListingRepository()
        raw_listings = await repo.get_listings_by_district(district=district, limit=limit)

        if not raw_listings:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No listings found for district: {district}",
            )

        listings = [
            ListingResponse(
                listing_id=listing.get("listing_id", ""),
                title_en=listing.get("title_en", ""),
                price_sar=float(listing.get("price_sar", 0)),
                area_sqm=float(listing.get("area_sqm", 0)),
                price_per_sqm=float(listing.get("price_per_sqm", 0)),
                district=listing.get("district", district),
                property_type=listing.get("property_type", "other"),
                rera_number=listing.get("rera_number"),
                is_waqf=bool(listing.get("is_waqf", False)),
            )
            for listing in raw_listings
        ]

        prices = [listing.price_per_sqm for listing in listings if listing.price_per_sqm > 0]
        avg_price = round(sum(prices) / len(prices), 2) if prices else None

        return DistrictListingsResponse(
            district=district,
            total=len(listings),
            listings=listings,
            avg_price_per_sqm=avg_price,
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.error(
            "Failed to fetch listings", exc_info=True, extra={"district": district}
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {exc}",
        ) from exc
