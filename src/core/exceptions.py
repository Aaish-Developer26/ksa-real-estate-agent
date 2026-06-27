"""Custom exception hierarchy for the KSA Real Estate Investment Agent."""

from __future__ import annotations


class KSAAgentError(Exception):
    """Root exception for all application-specific errors.

    Args:
        message: Human-readable description of the error.
        context: Optional structured metadata describing the error
            (e.g. listing_id, source_url, field name).
    """

    def __init__(self, message: str, context: dict[str, str] | None = None) -> None:
        self.message = message
        self.context = context or {}
        super().__init__(message)

    def __str__(self) -> str:
        """Return the error message, appending context when present.

        Returns:
            The human-readable message, with structured context appended
            if any context metadata was provided.
        """
        if self.context:
            return f"{self.message} | context={self.context}"
        return self.message


class ConfigurationError(KSAAgentError):
    """Raised when required configuration or environment variables are missing or invalid."""


class DataLayerError(KSAAgentError):
    """Raised when a database connection or query operation fails."""


class MigrationError(DataLayerError):
    """Raised when a database schema migration fails."""


class IngestionError(KSAAgentError):
    """Raised when the Sourcing Agent fails to extract listing data."""


class ScrapingRateLimitError(IngestionError):
    """Raised when a data source rate-limits or throttles the Sourcing Agent."""


class NormalizationError(KSAAgentError):
    """Raised when the Cleaning Agent fails to normalize a raw listing."""


class SchemaValidationError(NormalizationError):
    """Raised when a cleaned listing fails Pydantic schema validation."""


class AnalysisError(KSAAgentError):
    """Raised when the Analyst Agent fails to complete quantitative analysis."""


class InsufficientDataError(AnalysisError):
    """Raised when there is not enough data to perform a statistically valid analysis."""


class ComplianceError(KSAAgentError):
    """Raised when the Risk & Compliance Agent fails to evaluate a listing."""


class RERAViolationError(ComplianceError):
    """Raised when a listing violates RERA regulatory requirements."""


class MCPServerError(KSAAgentError):
    """Raised when communication with an MCP server fails."""
