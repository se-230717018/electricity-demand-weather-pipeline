-- Schema for electricity-demand-weather-pipeline (Milestone M2)
--
-- Safe to run more than once: every table uses CREATE TABLE IF NOT EXISTS.
-- Every table is STRICT, so a column only accepts values of its declared type.
-- Timestamps are TEXT in ISO 8601 UTC: events as YYYY-MM-DDTHH:MMZ,
-- retrieval times as YYYY-MM-DDTHH:MM:SSZ (taken from the raw file name).
-- Every table keeps retrieved_at + source_file: which landed file the row came from.

-- Entity: one row = one balancing authority (grid region), e.g. NYIS.
CREATE TABLE IF NOT EXISTS region (
    region_key       INTEGER PRIMARY KEY,
    respondent       TEXT    NOT NULL UNIQUE,
    respondent_name  TEXT,
    retrieved_at     TEXT    NOT NULL,
    source_file      TEXT    NOT NULL
) STRICT;

-- Entity: one row = one EIA series type, D (demand) or DF (day-ahead forecast).
CREATE TABLE IF NOT EXISTS series_type (
    type_key      INTEGER PRIMARY KEY,
    type_code     TEXT    NOT NULL UNIQUE,
    type_name     TEXT,
    retrieved_at  TEXT    NOT NULL,
    source_file   TEXT    NOT NULL
) STRICT;

-- Entity: one row = one weather point representing a region (e.g. New York for NYIS).
CREATE TABLE IF NOT EXISTS location (
    location_key   INTEGER PRIMARY KEY,
    location_code  TEXT    NOT NULL UNIQUE,
    region_key     INTEGER NOT NULL REFERENCES region (region_key),
    latitude       REAL,
    longitude      REAL,
    elevation_m    REAL,
    retrieved_at   TEXT    NOT NULL,
    source_file    TEXT    NOT NULL
) STRICT;

-- Event: one row = one region, one series type, one UTC hour.
CREATE TABLE IF NOT EXISTS demand (
    region_key    INTEGER NOT NULL REFERENCES region (region_key),
    type_key      INTEGER NOT NULL REFERENCES series_type (type_key),
    period_utc    TEXT    NOT NULL
                  CHECK (period_utc GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]Z'),
    value_mwh     REAL,
    retrieved_at  TEXT    NOT NULL,
    source_file   TEXT    NOT NULL,
    PRIMARY KEY (region_key, type_key, period_utc)
) STRICT;

-- Event: one row = one location, one UTC hour.
CREATE TABLE IF NOT EXISTS weather (
    location_key           INTEGER NOT NULL REFERENCES location (location_key),
    observed_at            TEXT    NOT NULL
                           CHECK (observed_at GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]Z'),
    temperature_c          REAL,
    relative_humidity_pct  REAL,
    precipitation_mm       REAL,
    retrieved_at           TEXT    NOT NULL,
    source_file            TEXT    NOT NULL,
    PRIMARY KEY (location_key, observed_at)
) STRICT;

-- Quarantine: one row = one record we could not load yet, and why.
-- UNIQUE keeps a second run from quarantining the same record twice.
CREATE TABLE IF NOT EXISTS quarantine (
    quarantine_id  INTEGER PRIMARY KEY,
    source         TEXT    NOT NULL CHECK (source IN ('eia', 'open_meteo')),
    source_file    TEXT    NOT NULL,
    record_ref     TEXT    NOT NULL,
    reason         TEXT    NOT NULL,
    raw_record     TEXT    NOT NULL,
    retrieved_at   TEXT    NOT NULL,
    UNIQUE (source, source_file, record_ref)
) STRICT;
