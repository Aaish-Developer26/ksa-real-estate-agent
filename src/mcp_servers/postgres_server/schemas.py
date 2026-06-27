"""SQL DDL definitions for the Postgres/TimescaleDB schema.

Raw SQL only — no ORM. Statements are executed directly via asyncpg.
"""

from __future__ import annotations

CREATE_ANALYSIS_RUNS_TABLE: str = """
CREATE TABLE IF NOT EXISTS analysis_runs (
    run_id          TEXT PRIMARY KEY,
    status          TEXT NOT NULL DEFAULT 'running'
                    CHECK (status IN ('running', 'completed', 'failed')),
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    completed_at    TIMESTAMPTZ,
    total_listings  INTEGER DEFAULT 0,
    summary         TEXT
);
"""

CREATE_RAW_LISTINGS_TABLE: str = """
CREATE TABLE IF NOT EXISTS raw_listings (
    id                  SERIAL PRIMARY KEY,
    run_id              TEXT REFERENCES analysis_runs(run_id),
    listing_id          TEXT,
    source_url          TEXT,
    raw_title           TEXT,
    raw_price           TEXT,
    raw_area            TEXT,
    raw_location        TEXT,
    raw_property_type   TEXT,
    raw_description     TEXT,
    rera_number         TEXT,
    is_waqf             BOOLEAN DEFAULT FALSE,
    scraped_at          TIMESTAMPTZ,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (run_id, listing_id)
);
"""

CREATE_CLEANED_LISTINGS_TABLE: str = """
CREATE TABLE IF NOT EXISTS cleaned_listings (
    id                              SERIAL PRIMARY KEY,
    run_id                          TEXT REFERENCES analysis_runs(run_id),
    listing_id                      TEXT NOT NULL,
    source_url                      TEXT,
    title_en                        TEXT,
    price_sar                       NUMERIC(15, 2),
    area_sqm                        NUMERIC(10, 2),
    price_per_sqm                   NUMERIC(12, 2),
    district                        TEXT,
    property_type                   TEXT,
    rera_number                     TEXT,
    is_waqf                         BOOLEAN DEFAULT FALSE,
    is_foreign_ownership_restricted BOOLEAN DEFAULT FALSE,
    normalized_at                   TIMESTAMPTZ,
    created_at                      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (run_id, listing_id)
);
"""

CREATE_COMPLIANCE_FLAGS_TABLE: str = """
CREATE TABLE IF NOT EXISTS compliance_flags (
    id              SERIAL PRIMARY KEY,
    listing_id      TEXT NOT NULL,
    run_id          TEXT REFERENCES analysis_runs(run_id),
    flag_type       TEXT NOT NULL,
    severity        TEXT NOT NULL
                    CHECK (severity IN ('low', 'medium', 'high', 'critical')),
    description     TEXT,
    flagged_at      TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
"""

CREATE_PRICE_HISTORY_TABLE: str = """
CREATE TABLE IF NOT EXISTS price_history (
    id              SERIAL,
    listing_id      TEXT NOT NULL,
    district        TEXT,
    price_sar       NUMERIC(15, 2),
    price_per_sqm   NUMERIC(12, 2),
    recorded_at     TIMESTAMPTZ NOT NULL,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (id, recorded_at)
);
"""

CONVERT_PRICE_HISTORY_TO_HYPERTABLE: str = (
    "SELECT create_hypertable('price_history', 'recorded_at', "
    "if_not_exists => TRUE);"
)

CREATE_DISTRICT_INDEX: str = (
    "CREATE INDEX IF NOT EXISTS idx_cleaned_listings_district "
    "ON cleaned_listings(district);"
)

CREATE_RUN_ID_INDEX: str = (
    "CREATE INDEX IF NOT EXISTS idx_cleaned_listings_run_id "
    "ON cleaned_listings(run_id);"
)

ALL_SCHEMAS: list[str] = [
    CREATE_ANALYSIS_RUNS_TABLE,
    CREATE_RAW_LISTINGS_TABLE,
    CREATE_CLEANED_LISTINGS_TABLE,
    CREATE_COMPLIANCE_FLAGS_TABLE,
    CREATE_PRICE_HISTORY_TABLE,
    CONVERT_PRICE_HISTORY_TO_HYPERTABLE,
    CREATE_DISTRICT_INDEX,
    CREATE_RUN_ID_INDEX,
]
