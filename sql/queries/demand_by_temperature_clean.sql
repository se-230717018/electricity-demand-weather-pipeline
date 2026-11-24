-- Analytical query on the cleaned layer (M3): how does electricity demand change with temperature?
--
-- Same question, grain and bands as demand_by_temperature.sql (M2), but read from
-- demand_clean and weather_clean, so the known M2 issue (hours of 0 or near-0 MWh)
-- is gone: untrusted values are NULL in the cleaned layer and are left out here.
--
-- Grain of the result: one row = one region x one 5 °C temperature band.
--
-- Inputs:
--   demand_clean  : one row = one region, one series type, one UTC hour.
--                   Only actual demand (role 'actual' in map_series_type) is used.
--   weather_clean : one row = one location, one UTC hour.
--   Each demand hour is joined to the weather of the location that represents
--   its region at the same UTC hour (period_utc = observed_at).
--
-- Kept: every value the cleaning step trusts (flags ok, unusual_high, unusual_low).
-- Left out: hours whose cleaned demand or temperature is NULL, so `hours` shows
-- how many trusted hours each average rests on.
-- Band: floor(temperature / 5) * 5; +100 keeps the number positive so integer
-- division floors correctly for sub-zero temperatures.

WITH joined AS (
    SELECT
        r.respondent,
        (CAST(w.temperature_c + 100 AS INTEGER) / 5) * 5 - 100 AS band_low_c,
        d.value_mwh
    FROM demand_clean    AS d
    JOIN region          AS r ON r.region_key = d.region_key
    JOIN location        AS l ON l.region_key = d.region_key
    JOIN weather_clean   AS w ON w.location_key = l.location_key
                             AND w.observed_at = d.period_utc
    WHERE d.type_key IN (SELECT type_key FROM map_series_type WHERE role = 'actual')
      AND d.value_mwh IS NOT NULL
      AND w.temperature_c IS NOT NULL
)
SELECT
    respondent,
    band_low_c,
    band_low_c + 5            AS band_high_c,
    COUNT(*)                  AS hours,
    ROUND(AVG(value_mwh), 0)  AS avg_demand_mwh,
    MIN(value_mwh)            AS min_demand_mwh,
    MAX(value_mwh)            AS max_demand_mwh
FROM joined
GROUP BY respondent, band_low_c
ORDER BY respondent, band_low_c;