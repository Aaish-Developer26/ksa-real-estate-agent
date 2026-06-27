"""Deterministic quantitative analysis tools for district price statistics.

Pure deterministic Python using numpy/scipy. No LLM calls. No I/O.
"""

from __future__ import annotations

from typing import Any

import numpy as np
from scipy import stats


def compute_district_statistics(
    price_per_sqm_values: list[float],
) -> dict[str, float]:
    """Compute descriptive statistics for a district's price/sqm values.

    Args:
        price_per_sqm_values: List of price per sqm floats for a district.

    Returns:
        Dict with keys: mean, median, std_dev, min, max, q1, q3, iqr.
        Returns an empty dict if fewer than 2 values are provided.
    """
    if len(price_per_sqm_values) < 2:
        return {}
    values = np.array(price_per_sqm_values, dtype=float)
    q1, q3 = np.percentile(values, [25, 75])
    return {
        "mean": round(float(np.mean(values)), 2),
        "median": round(float(np.median(values)), 2),
        "std_dev": round(float(np.std(values)), 2),
        "min": round(float(np.min(values)), 2),
        "max": round(float(np.max(values)), 2),
        "q1": round(float(q1), 2),
        "q3": round(float(q3), 2),
        "iqr": round(float(q3 - q1), 2),
    }


def detect_price_outliers(
    price_per_sqm_values: list[float],
    listing_ids: list[str],
    z_score_threshold: float = 3.0,
) -> list[str]:
    """Identify listings with statistically anomalous price/sqm.

    Uses the Z-score method: a value is an outlier if |z| exceeds
    z_score_threshold.

    Args:
        price_per_sqm_values: Price/sqm for each listing.
        listing_ids: Corresponding listing ID for each value.
        z_score_threshold: Z-score cutoff (default 3.0 = 3σ rule).

    Returns:
        List of listing_ids where price/sqm is a statistical outlier.
        Returns an empty list if fewer than 3 values are provided
        (insufficient sample size for a meaningful z-score).
    """
    if len(price_per_sqm_values) < 3:
        return []
    z_scores = stats.zscore(price_per_sqm_values)
    return [
        listing_ids[i]
        for i, z_score in enumerate(z_scores)
        if abs(float(z_score)) > z_score_threshold
    ]


def compute_undervalue_discount(
    listing_price_per_sqm: float,
    district_avg_price_per_sqm: float,
) -> float:
    """Compute percentage discount versus the district average.

    Args:
        listing_price_per_sqm: Listing's price/sqm.
        district_avg_price_per_sqm: District benchmark price/sqm.

    Returns:
        Discount as a positive percentage (e.g., 22.5 means 22.5% below
        average). A negative value means the listing is above average
        (overvalued).
    """
    return round((1 - listing_price_per_sqm / district_avg_price_per_sqm) * 100, 2)


def rank_investment_opportunities(
    listings: list[dict[str, Any]],
    district_benchmarks: dict[str, float],
    min_discount_pct: float = 20.0,
) -> list[dict[str, Any]]:
    """Rank undervalued listings by investment opportunity score.

    Scoring formula: opportunity_score = discount_pct * log(area_sqm + 1)
    — larger discounted properties score higher.

    Args:
        listings: Cleaned listing dicts with price_per_sqm, district,
            area_sqm, and listing_id fields.
        district_benchmarks: District average price/sqm map.
        min_discount_pct: Minimum discount to qualify (default 20%).

    Returns:
        List of opportunity dicts sorted by opportunity_score descending.
        Empty list if no listings meet the threshold.
    """
    opportunities: list[dict[str, Any]] = []
    for listing in listings:
        district = listing.get("district")
        benchmark = district_benchmarks.get(district) if district else None
        price_per_sqm = listing.get("price_per_sqm")
        if not benchmark or price_per_sqm is None:
            continue

        discount_pct = compute_undervalue_discount(price_per_sqm, benchmark)
        if discount_pct < min_discount_pct:
            continue

        area_sqm = listing.get("area_sqm") or 0.0
        opportunity_score = round(discount_pct * float(np.log(area_sqm + 1)), 2)
        opportunities.append(
            {
                "listing_id": listing["listing_id"],
                "district": district,
                "discount_pct": discount_pct,
                "opportunity_score": opportunity_score,
                "price_per_sqm": price_per_sqm,
                "area_sqm": area_sqm,
            }
        )

    opportunities.sort(key=lambda item: item["opportunity_score"], reverse=True)
    return opportunities
