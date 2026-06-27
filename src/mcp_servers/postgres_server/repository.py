"""Repository pattern implementation for all listing database operations."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from src.core.database import get_pool
from src.core.exceptions import DataLayerError
from src.core.logging_setup import get_logger
from src.mcp_servers.postgres_server.schemas import ALL_SCHEMAS

logger = get_logger(__name__)


def _parse_timestamp(value: Any) -> datetime | None:
    """Convert ISO timestamp string to datetime object for asyncpg.

    asyncpg requires datetime objects for TIMESTAMPTZ columns — it
    does not auto-convert strings. Returns None if value is None,
    empty, or unparseable.

    Args:
        value: ISO timestamp string or None.

    Returns:
        datetime object with timezone info, or None.
    """
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value))
    except (ValueError, TypeError):
        return None


class ListingRepository:
    """Provides async data access operations for the listing pipeline."""

    async def create_tables(self) -> None:
        """Execute all DDL statements from ``schemas.py`` in a single transaction.

        Raises:
            DataLayerError: If any DDL statement fails. The whole
                transaction is rolled back.
        """
        pool = get_pool()
        try:
            async with pool.acquire() as conn, conn.transaction():
                for statement in ALL_SCHEMAS:
                    await conn.execute(statement)
        except Exception as exc:
            logger.error("Failed to initialize database schema", exc_info=True)
            raise DataLayerError(
                "Failed to initialize database schema", context={"error": str(exc)}
            ) from exc
        logger.info("Database schema initialized")

    async def create_analysis_run(self, run_id: str) -> dict[str, str]:
        """Insert a new analysis run record.

        Args:
            run_id: Unique identifier for the pipeline run.

        Returns:
            A dict with the run_id and its creation timestamp.

        Raises:
            DataLayerError: If the insert fails.
        """
        pool = get_pool()
        try:
            row = await pool.fetchrow(
                "INSERT INTO analysis_runs (run_id) VALUES ($1) "
                "RETURNING run_id, created_at",
                run_id,
            )
        except Exception as exc:
            logger.error(
                "Failed to create analysis run", exc_info=True, extra={"run_id": run_id}
            )
            raise DataLayerError(
                "Failed to create analysis run",
                context={"run_id": run_id, "error": str(exc)},
            ) from exc
        logger.debug("Created analysis run", extra={"run_id": run_id})
        return {"run_id": row["run_id"], "created_at": row["created_at"].isoformat()}

    async def update_analysis_run(
        self,
        run_id: str,
        status: str,
        summary: str = "",
        total_listings: int = 0,
    ) -> bool:
        """Update an analysis run's status, summary, and listing count.

        Args:
            run_id: The run to update.
            status: New status value ("running", "completed", "failed").
            summary: Optional narrative summary of the run.
            total_listings: Total listings processed by the run.

        Returns:
            True if a row was updated, False if run_id was not found.

        Raises:
            DataLayerError: If the update query fails.
        """
        pool = get_pool()
        try:
            result = await pool.execute(
                "UPDATE analysis_runs SET status = $2, summary = $3, "
                "total_listings = $4, completed_at = NOW() WHERE run_id = $1",
                run_id,
                status,
                summary,
                total_listings,
            )
        except Exception as exc:
            logger.error(
                "Failed to update analysis run", exc_info=True, extra={"run_id": run_id}
            )
            raise DataLayerError(
                "Failed to update analysis run",
                context={"run_id": run_id, "error": str(exc)},
            ) from exc
        updated = bool(result.endswith(" 1"))
        logger.debug("Updated analysis run", extra={"run_id": run_id, "updated": updated})
        return updated

    async def insert_raw_listings(
        self, listings: list[dict[str, Any]], run_id: str
    ) -> int:
        """Bulk insert raw scraped listings, skipping duplicates.

        Args:
            listings: Raw listing dicts matching the RawListing schema.
            run_id: The pipeline run these listings belong to.

        Returns:
            Count of rows actually inserted (excludes conflicts skipped).

        Raises:
            DataLayerError: If the bulk insert fails.
        """
        pool = get_pool()
        try:
            async with pool.acquire() as conn, conn.transaction():
                before = await conn.fetchval(
                    "SELECT COUNT(*) FROM raw_listings WHERE run_id = $1", run_id
                )
                await conn.executemany(
                    """
                    INSERT INTO raw_listings (
                        run_id, listing_id, source_url, raw_title, raw_price,
                        raw_area, raw_location, raw_property_type,
                        raw_description, rera_number, is_waqf, scraped_at
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
                    ON CONFLICT (run_id, listing_id) DO NOTHING
                    """,
                    [
                        (
                            run_id,
                            listing.get("listing_id"),
                            listing.get("source_url"),
                            listing.get("raw_title"),
                            listing.get("raw_price"),
                            listing.get("raw_area"),
                            listing.get("raw_location"),
                            listing.get("raw_property_type"),
                            listing.get("raw_description"),
                            listing.get("rera_number"),
                            listing.get("is_waqf", False),
                            _parse_timestamp(listing.get("scraped_at")),
                        )
                        for listing in listings
                    ],
                )
                after = await conn.fetchval(
                    "SELECT COUNT(*) FROM raw_listings WHERE run_id = $1", run_id
                )
        except Exception as exc:
            logger.error(
                "Failed to insert raw listings", exc_info=True, extra={"run_id": run_id}
            )
            raise DataLayerError(
                "Failed to insert raw listings",
                context={"run_id": run_id, "error": str(exc)},
            ) from exc
        inserted = int(after) - int(before)
        logger.debug("Inserted raw listings", extra={"run_id": run_id, "count": inserted})
        return inserted

    async def insert_cleaned_listings(
        self, listings: list[dict[str, Any]], run_id: str
    ) -> int:
        """Bulk insert cleaned, normalized listings, skipping duplicates.

        Args:
            listings: Cleaned listing dicts matching the CleanedListing schema.
            run_id: The pipeline run these listings belong to.

        Returns:
            Count of rows actually inserted (excludes conflicts skipped).

        Raises:
            DataLayerError: If the bulk insert fails.
        """
        pool = get_pool()
        try:
            async with pool.acquire() as conn, conn.transaction():
                before = await conn.fetchval(
                    "SELECT COUNT(*) FROM cleaned_listings WHERE run_id = $1", run_id
                )
                await conn.executemany(
                    """
                    INSERT INTO cleaned_listings (
                        run_id, listing_id, source_url, title_en, price_sar,
                        area_sqm, price_per_sqm, district, property_type,
                        rera_number, is_waqf, is_foreign_ownership_restricted,
                        normalized_at
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
                    ON CONFLICT (run_id, listing_id) DO NOTHING
                    """,
                    [
                        (
                            run_id,
                            listing["listing_id"],
                            listing.get("source_url"),
                            listing.get("title_en"),
                            listing.get("price_sar"),
                            listing.get("area_sqm"),
                            listing.get("price_per_sqm"),
                            listing.get("district"),
                            listing.get("property_type"),
                            listing.get("rera_number"),
                            listing.get("is_waqf", False),
                            listing.get("is_foreign_ownership_restricted", False),
                            _parse_timestamp(listing.get("normalized_at")),
                        )
                        for listing in listings
                    ],
                )
                after = await conn.fetchval(
                    "SELECT COUNT(*) FROM cleaned_listings WHERE run_id = $1", run_id
                )
        except Exception as exc:
            logger.error(
                "Failed to insert cleaned listings",
                exc_info=True,
                extra={"run_id": run_id},
            )
            raise DataLayerError(
                "Failed to insert cleaned listings",
                context={"run_id": run_id, "error": str(exc)},
            ) from exc
        inserted = int(after) - int(before)
        logger.debug(
            "Inserted cleaned listings", extra={"run_id": run_id, "count": inserted}
        )
        return inserted

    async def insert_compliance_flags(
        self, flags: list[dict[str, Any]], run_id: str
    ) -> int:
        """Bulk insert compliance flags for listings.

        Args:
            flags: Compliance flag dicts matching the ComplianceFlag schema.
            run_id: The pipeline run these flags belong to.

        Returns:
            Count of rows inserted.

        Raises:
            DataLayerError: If the bulk insert fails.
        """
        pool = get_pool()
        try:
            await pool.executemany(
                """
                INSERT INTO compliance_flags (
                    listing_id, run_id, flag_type, severity, description, flagged_at
                ) VALUES ($1, $2, $3, $4, $5, $6)
                """,
                [
                    (
                        flag["listing_id"],
                        run_id,
                        flag["flag_type"],
                        flag["severity"],
                        flag.get("description"),
                        _parse_timestamp(flag.get("flagged_at")),
                    )
                    for flag in flags
                ],
            )
        except Exception as exc:
            logger.error(
                "Failed to insert compliance flags",
                exc_info=True,
                extra={"run_id": run_id},
            )
            raise DataLayerError(
                "Failed to insert compliance flags",
                context={"run_id": run_id, "error": str(exc)},
            ) from exc
        logger.debug(
            "Inserted compliance flags", extra={"run_id": run_id, "count": len(flags)}
        )
        return len(flags)

    async def get_listings_by_district(
        self, district: str, limit: int = 50
    ) -> list[dict[str, Any]]:
        """Fetch cleaned listings for a given district, cheapest first.

        Args:
            district: Standardized district name to filter by.
            limit: Maximum number of listings to return.

        Returns:
            A list of listing dicts ordered by price_per_sqm ascending.

        Raises:
            DataLayerError: If the query fails.
        """
        pool = get_pool()
        try:
            rows = await pool.fetch(
                "SELECT * FROM cleaned_listings WHERE district = $1 "
                "ORDER BY price_per_sqm ASC LIMIT $2",
                district,
                limit,
            )
        except Exception as exc:
            logger.error(
                "Failed to fetch listings by district",
                exc_info=True,
                extra={"district": district},
            )
            raise DataLayerError(
                "Failed to fetch listings by district",
                context={"district": district, "error": str(exc)},
            ) from exc
        logger.debug(
            "Fetched listings by district",
            extra={"district": district, "count": len(rows)},
        )
        return [dict(row) for row in rows]

    async def get_price_benchmarks(self, districts: list[str]) -> dict[str, float]:
        """Calculate the average price per square meter for each district.

        Args:
            districts: District names to compute benchmarks for.

        Returns:
            A dict mapping district name to average price_per_sqm. Empty
            dict if no matching data was found.

        Raises:
            DataLayerError: If the query fails.
        """
        pool = get_pool()
        try:
            rows = await pool.fetch(
                "SELECT district, AVG(price_per_sqm) AS avg_price_per_sqm "
                "FROM cleaned_listings WHERE district = ANY($1) GROUP BY district",
                districts,
            )
        except Exception as exc:
            logger.error(
                "Failed to compute price benchmarks",
                exc_info=True,
                extra={"districts": districts},
            )
            raise DataLayerError(
                "Failed to compute price benchmarks",
                context={"districts": ",".join(districts), "error": str(exc)},
            ) from exc
        benchmarks = {
            row["district"]: float(row["avg_price_per_sqm"]) for row in rows
        }
        logger.debug("Computed price benchmarks", extra={"count": len(benchmarks)})
        return benchmarks

    async def load_mock_data(self, filepath: str, run_id: str) -> dict[str, int]:
        """Load mock listing data from a JSON file into raw_listings.

        Args:
            filepath: Path to the mock listings JSON file.
            run_id: The pipeline run to associate loaded listings with.

        Returns:
            A dict with ``{"loaded": N, "skipped": M}`` counts.

        Raises:
            DataLayerError: If the file does not exist or loading fails.
        """
        path = Path(filepath)
        if not path.exists():
            raise DataLayerError(
                "Mock data file not found", context={"filepath": filepath}
            )

        def _read_json() -> dict[str, Any]:
            with path.open(encoding="utf-8") as handle:
                loaded: dict[str, Any] = json.load(handle)
                return loaded

        try:
            data = await asyncio.to_thread(_read_json)
        except Exception as exc:
            logger.error("Failed to read mock data file", exc_info=True)
            raise DataLayerError(
                "Failed to read mock data file",
                context={"filepath": filepath, "error": str(exc)},
            ) from exc

        listings = data["listings"]
        loaded = await self.insert_raw_listings(listings, run_id)
        skipped = len(listings) - loaded
        logger.info(
            "Loaded mock data", extra={"loaded": loaded, "skipped": skipped}
        )
        return {"loaded": loaded, "skipped": skipped}

    async def insert_price_history(
        self,
        listing_id: str,
        district: str,
        price_sar: float,
        price_per_sqm: float,
        recorded_at: str,
    ) -> None:
        """Insert a single price history record for hypertable storage.

        Args:
            listing_id: The listing this price point belongs to.
            district: Standardized district name.
            price_sar: Listing price in Saudi Riyal.
            price_per_sqm: Price per square meter.
            recorded_at: ISO 8601 timestamp string, cast to TIMESTAMPTZ.

        Raises:
            DataLayerError: If the insert fails.
        """
        pool = get_pool()
        try:
            await pool.execute(
                "INSERT INTO price_history "
                "(listing_id, district, price_sar, price_per_sqm, recorded_at) "
                "VALUES ($1, $2, $3, $4, $5::timestamptz)",
                listing_id,
                district,
                price_sar,
                price_per_sqm,
                _parse_timestamp(recorded_at),
            )
        except Exception as exc:
            logger.error(
                "Failed to insert price history",
                exc_info=True,
                extra={"listing_id": listing_id},
            )
            raise DataLayerError(
                "Failed to insert price history",
                context={"listing_id": listing_id, "error": str(exc)},
            ) from exc
        logger.debug("Inserted price history", extra={"listing_id": listing_id})
