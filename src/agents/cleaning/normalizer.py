"""Provides Arabic/English text and unit normalization utilities.

Pure deterministic Python. Zero LLM calls. Zero I/O. All functions are
synchronous and fully unit-testable.
"""

from __future__ import annotations

import re

_ARABIC_INDIC_TRANSLATION = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
_SQFT_TO_SQM = 0.092903
_CURRENCY_WORDS_PATTERN = re.compile(r"(?i)\bSAR\b|\bSR\b|ريال|ر\.س")
_MULTIPLIER_PATTERN = re.compile(r"([\d.]+)\s*([MmKk])\b")
_SQFT_PATTERN = re.compile(r"(?i)sq\s*\.?\s*ft|sqft|قدم")
_NUMERIC_PATTERN = re.compile(r"[\d.]+")
_RERA_PATTERN = re.compile(r"\b\d{10}\b")


def parse_price_sar(raw_price: str | None) -> float | None:
    """Parse a raw price string into a SAR float value.

    Handles comma-separated values, Arabic-Indic numerals, M/K
    multiplier suffixes, and common SAR currency markers.

    Args:
        raw_price: Raw price string from listing source.

    Returns:
        Float SAR value, or None if unparseable.
    """
    if not raw_price:
        return None

    text = raw_price.translate(_ARABIC_INDIC_TRANSLATION)

    multiplier_match = _MULTIPLIER_PATTERN.search(text)
    if multiplier_match:
        try:
            number = float(multiplier_match.group(1))
        except ValueError:
            return None
        multiplier = 1_000_000.0 if multiplier_match.group(2).upper() == "M" else 1_000.0
        return round(number * multiplier, 2)

    text = _CURRENCY_WORDS_PATTERN.sub("", text)
    text = text.replace(",", "").strip()

    numeric_match = _NUMERIC_PATTERN.search(text)
    if not numeric_match:
        return None
    try:
        return float(numeric_match.group())
    except ValueError:
        return None


def parse_area_sqm(raw_area: str | None) -> float | None:
    """Parse a raw area string into a square-meter float value.

    Detects square-foot units and converts to square meters.

    Args:
        raw_area: Raw area string from listing source.

    Returns:
        Float square-meter value, or None if unparseable.
    """
    if not raw_area:
        return None

    text = raw_area.translate(_ARABIC_INDIC_TRANSLATION)
    is_sqft = bool(_SQFT_PATTERN.search(text))

    numeric_match = _NUMERIC_PATTERN.search(text)
    if not numeric_match:
        return None
    try:
        value = float(numeric_match.group())
    except ValueError:
        return None

    if is_sqft:
        return round(value * _SQFT_TO_SQM, 2)
    return value


def compute_price_per_sqm(
    price_sar: float | None,
    area_sqm: float | None,
) -> float | None:
    """Compute price per square meter.

    Args:
        price_sar: Total price in SAR.
        area_sqm: Area in square meters.

    Returns:
        Price per sqm rounded to 2 decimal places, or None if either
        input is None or area_sqm is zero.
    """
    if price_sar is None or area_sqm is None or area_sqm == 0:
        return None
    return round(price_sar / area_sqm, 2)


def extract_rera_number(raw_text: str | None) -> str | None:
    """Extract a 10-digit Saudi RERA registration number from free text.

    Args:
        raw_text: Any raw text field (title, description, etc.).

    Returns:
        The first 10-digit sequence found, or None if not present.
    """
    if not raw_text:
        return None
    match = _RERA_PATTERN.search(raw_text)
    return match.group() if match else None


DISTRICT_MAP: dict[str, str] = {
    "العليا": "Olaya",
    "عليا": "Olaya",
    "olaya": "Olaya",
    "الملقا": "Al_Malqa",
    "ملقا": "Al_Malqa",
    "al malqa": "Al_Malqa",
    "al-malqa": "Al_Malqa",
    "النخيل": "Al_Nakheel",
    "نخيل": "Al_Nakheel",
    "al nakheel": "Al_Nakheel",
    "الروضة": "Al_Rawdah",
    "روضة": "Al_Rawdah",
    "al rawdah": "Al_Rawdah",
    "كافد": "KAFD",
    "kafd": "KAFD",
    "king abdullah financial": "KAFD",
    "النسيم": "Al_Naseem",
    "نسيم": "Al_Naseem",
    "al naseem": "Al_Naseem",
    "الشفا": "Al_Shifa",
    "شفا": "Al_Shifa",
    "al shifa": "Al_Shifa",
    "الوروود": "Al_Wurud",
    "الورود": "Al_Wurud",
    "al wurud": "Al_Wurud",
}


def normalize_district(raw_location: str | None) -> str | None:
    """Map a raw location string to its canonical district name.

    Performs a case-insensitive exact lookup first, then falls back to
    a substring match against DISTRICT_MAP keys.

    Args:
        raw_location: Raw location string from listing.

    Returns:
        Canonical district name, or None if no match found.
    """
    if not raw_location:
        return None
    text = raw_location.lower().strip()
    if text in DISTRICT_MAP:
        return DISTRICT_MAP[text]
    for key, value in DISTRICT_MAP.items():
        if key in text:
            return value
    return None


PROPERTY_TYPE_MAP: dict[str, str] = {
    "شقة": "apartment",
    "apartment": "apartment",
    "flat": "apartment",
    "فيلا": "villa",
    "villa": "villa",
    "فلة": "villa",
    "أرض": "land",
    "land": "land",
    "ارض": "land",
    "مجمع": "compound",
    "compound": "compound",
    "تجاري": "commercial",
    "commercial": "commercial",
}


def normalize_property_type(raw_type: str | None) -> str:
    """Map a raw property type string to its canonical Literal value.

    Args:
        raw_type: Raw property type string from listing.

    Returns:
        One of "villa", "apartment", "compound", "land", "commercial",
        or "other" if no match is found.
    """
    if not raw_type:
        return "other"
    text = raw_type.lower().strip()
    if text in PROPERTY_TYPE_MAP:
        return PROPERTY_TYPE_MAP[text]
    for key, value in PROPERTY_TYPE_MAP.items():
        if key in text:
            return value
    return "other"
