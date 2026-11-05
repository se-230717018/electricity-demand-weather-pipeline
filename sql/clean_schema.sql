-- Cleaned layer for electricity-demand-weather-pipeline (Milestone M3)
--
-- Built by src/clean.py from the M2 tables, which it only ever reads.
-- Safe to run more than once (IF NOT EXISTS). Every table is STRICT.
-- Each cleaned table has the same grain, primary key and row count as the
-- M2 table it cleans. For every value cleaning can change there are three
-- columns: <col>_raw (exactly as loaded), <col> (cleaned) and <col>_flag (why
-- they differ). Cleaned values are never imputed: NULL when not trusted.

-- Mapping: one row = one decision that a weather location represents a region.
-- Loaded from data/mappings/region_location.csv (source IDs, not surrogate keys).
CREATE TABLE IF NOT EXISTS map_region_location (
    location_key  INTEGER PRIMARY KEY REFERENCES location (location_key),
    region_key    INTEGER NOT NULL REFERENCES region (region_key),
    city          TEXT    NOT NULL,
    decided_by    TEXT    NOT NULL,
    decided_at    TEXT    NOT NULL CHECK (decided_at GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'),
    note          TEXT    NOT NULL
) STRICT;

-- Mapping: one row = one decision about what an EIA series type means.
-- Loaded from data/mappings/series_type_role.csv.
CREATE TABLE IF NOT EXISTS map_series_type (
    type_key    INTEGER PRIMARY KEY REFERENCES series_type (type_key),
    role        TEXT    NOT NULL CHECK (role IN ('actual', 'forecast')),
    unit        TEXT    NOT NULL,
    decided_by  TEXT    NOT NULL,
    decided_at  TEXT    NOT NULL CHECK (decided_at GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'),
    note        TEXT    NOT NULL
) STRICT;

-- Cleaned demand: one row = one region, one series type, one UTC hour (same as demand).
CREATE TABLE IF NOT EXISTS demand_clean (
    region_key      INTEGER NOT NULL REFERENCES region (region_key),
    type_key        INTEGER NOT NULL REFERENCES series_type (type_key),
    period_utc      TEXT    NOT NULL,
    value_mwh_raw   REAL,
    value_mwh       REAL,
    value_mwh_flag  TEXT    NOT NULL CHECK (value_mwh_flag IN (
                        'ok', 'missing_not_reported', 'invalid_nonpositive', 'invalid_dropout',
                        'stuck_value', 'forecast_mismatch', 'unusual_high', 'unusual_low')),
    PRIMARY KEY (region_key, type_key, period_utc),
    FOREIGN KEY (region_key, type_key, period_utc) REFERENCES demand (region_key, type_key, period_utc),
    -- Flag before you fix, and fix what you flag: untrusted flags carry NULL,
    -- every other flag keeps the raw value unchanged.
    CHECK ((value_mwh_flag IN ('missing_not_reported', 'invalid_nonpositive', 'invalid_dropout', 'stuck_value')
            AND value_mwh IS NULL)
        OR (value_mwh_flag IN ('ok', 'forecast_mismatch', 'unusual_high', 'unusual_low')
            AND value_mwh IS value_mwh_raw))
) STRICT;

-- Cleaned weather: one row = one location, one UTC hour (same as weather).
CREATE TABLE IF NOT EXISTS weather_clean (
    location_key                INTEGER NOT NULL REFERENCES location (location_key),
    observed_at                 TEXT    NOT NULL,
    temperature_c_raw           REAL,
    temperature_c               REAL,
    temperature_c_flag          TEXT    NOT NULL CHECK (temperature_c_flag IN (
                                    'ok', 'missing_not_reported', 'invalid_out_of_range',
                                    'stuck_value', 'spike', 'unusual_high', 'unusual_low')),
    relative_humidity_pct_raw   REAL,
    relative_humidity_pct       REAL,
    relative_humidity_pct_flag  TEXT    NOT NULL CHECK (relative_humidity_pct_flag IN (
                                    'ok', 'missing_not_reported', 'invalid_out_of_range',
                                    'stuck_value', 'spike', 'unusual_high', 'unusual_low')),
    precipitation_mm_raw        REAL,
    precipitation_mm            REAL,
    precipitation_mm_flag       TEXT    NOT NULL CHECK (precipitation_mm_flag IN (
                                    'ok', 'missing_not_reported', 'invalid_out_of_range',
                                    'stuck_value', 'spike', 'unusual_high', 'unusual_low')),
    PRIMARY KEY (location_key, observed_at),
    FOREIGN KEY (location_key, observed_at) REFERENCES weather (location_key, observed_at),
    CHECK ((temperature_c_flag IN ('missing_not_reported', 'invalid_out_of_range', 'stuck_value', 'spike')
            AND temperature_c IS NULL)
        OR (temperature_c_flag IN ('ok', 'unusual_high', 'unusual_low') AND temperature_c IS temperature_c_raw)),
    CHECK ((relative_humidity_pct_flag IN ('missing_not_reported', 'invalid_out_of_range', 'stuck_value', 'spike')
            AND relative_humidity_pct IS NULL)
        OR (relative_humidity_pct_flag IN ('ok', 'unusual_high', 'unusual_low')
            AND relative_humidity_pct IS relative_humidity_pct_raw)),
    CHECK ((precipitation_mm_flag IN ('missing_not_reported', 'invalid_out_of_range', 'stuck_value', 'spike')
            AND precipitation_mm IS NULL)
        OR (precipitation_mm_flag IN ('ok', 'unusual_high', 'unusual_low') AND precipitation_mm IS precipitation_mm_raw))
) STRICT;

-- Views with entity names joined in, so M4 queries stay short.
CREATE VIEW IF NOT EXISTS demand_resolved AS
SELECT r.respondent, s.type_code, m.role, d.period_utc,
       d.value_mwh_raw, d.value_mwh, d.value_mwh_flag
FROM demand_clean d
JOIN region r      ON r.region_key = d.region_key
JOIN series_type s ON s.type_key = d.type_key
LEFT JOIN map_series_type m ON m.type_key = d.type_key;

CREATE VIEW IF NOT EXISTS weather_resolved AS
SELECT l.location_code, m.city, r.respondent, w.observed_at,
       w.temperature_c_raw, w.temperature_c, w.temperature_c_flag,
       w.relative_humidity_pct_raw, w.relative_humidity_pct, w.relative_humidity_pct_flag,
       w.precipitation_mm_raw, w.precipitation_mm, w.precipitation_mm_flag
FROM weather_clean w
JOIN location l ON l.location_key = w.location_key
LEFT JOIN map_region_location m ON m.location_key = w.location_key
LEFT JOIN region r ON r.region_key = m.region_key;
