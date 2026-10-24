-- Analytical query: how does electricity demand change with temperature?
--
-- Grain of the result: one row = one region x one 5 °C temperature band.
--
-- Inputs:
--   demand  : one row = one region, one series type, one UTC hour.
--             Only actual demand (type_code 'D') is used, not the forecast.
--   weather : one row = one location, one UTC hour.
--   Each demand hour is joined to the weather of the location that represents
--   its region at the same UTC hour (demand.period_utc = weather.observed_at).
--
-- Hours where demand or temperature is NULL (not reported / not yet archived)
-- are left out, so `hours` shows how many hours each average rests on.
-- Band: floor(temperature / 5) * 5; +100 keeps the number positive so integer
-- division floors correctly for sub-zero temperatures.

WITH joined AS (
    SELECT
        r.respondent,
        (CAST(w.temperature_c + 100 AS INTEGER) / 5) * 5 - 100 AS band_low_c,
        d.value_mwh
    FROM demand AS d
    JOIN series_type AS t ON t.type_key = d.type_key AND t.type_code = 'D'
    JOIN region      AS r ON r.region_key = d.region_key
    JOIN location    AS l ON l.region_key = d.region_key
    JOIN weather     AS w ON w.location_key = l.location_key
                         AND w.observed_at = d.period_utc
    WHERE d.value_mwh IS NOT NULL
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