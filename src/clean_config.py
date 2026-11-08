"""Every threshold and constant used by the M3 cleaning step, in one place.

Each constant has a name and a comment, and every value is justified in
docs/cleaning_report.md, section 5. Edit only your own section; the values in
DEMAND and WEATHER are decided after profiling (team meeting, 5 Nov).
"""

from pathlib import Path

# ---------------------------------------------------------------------------
# GENERAL (Esma) - src/clean.py
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent
MAPPINGS_DIR = ROOT / "data" / "mappings"  # committed CSVs: name, category and identity decisions

# ---------------------------------------------------------------------------
# DEMAND (Tuba) - src/clean_demand.py
# ---------------------------------------------------------------------------
# Add constants for demand_clean below this line, each with a comment.

DROPOUT_FRACTION = 0.10   # value < 10 % of its region x series median -> invalid_dropout (NULL); profile 1.5: real lows >= 47 %, dropouts <= 0.4 %
STUCK_RUN_HOURS = 6       # same value in >= 6 consecutive hours -> stuck_value (NULL); profile 1.6: longest natural non-zero run is 3 h
DF_D_RATIO_MIN = 0.5      # DF / D below this -> forecast_mismatch on the DF row (value kept); profile 1.7
DF_D_RATIO_MAX = 2.0      # DF / D above this -> forecast_mismatch on the DF row (value kept); flags 1 hour in the profile
ROBUST_Z_UNUSUAL = 3.5    # |robust z| > 3.5 -> unusual_high / unusual_low (value kept); never mean +/- 3 SD
ROBUST_Z_SCALE = 0.6745   # robust z = 0.6745 * (x - median) / MAD (makes MAD comparable to a standard deviation)
WARN_NULL_SHARE = 0.01    # validate.py: WARN when > 1 % of a region's cleaned demand values are NULL

# ---------------------------------------------------------------------------
# WEATHER (İrem) - src/clean_weather.py
# ---------------------------------------------------------------------------
# Add constants for weather_clean below this line, each with a comment.


TEMP_MIN_C, TEMP_MAX_C = -60.0, 60.0          # outside -> invalid_out_of_range (NULL); profile: observed -18.3 .. 45.7 C, 0 outside
HUMIDITY_MIN_PCT, HUMIDITY_MAX_PCT = 0.0, 100.0  # relative humidity is a percentage by definition; profile: observed 3 .. 100, 0 outside
PRECIP_MIN_MM = 0.0                           # negative precipitation is impossible; profile: min 0.0, 0 below
WEATHER_STUCK_RUN_HOURS = 24                  # same value >= 24 consecutive hours -> stuck_value (NULL); profile: longest natural run 7 h (temperature, night) and 18 h (humidity at 100 % saturation)
TEMP_SPIKE_C_PER_HOUR = 12.0                  # |change| > 12 C in one hour -> spike (NULL); profile: p99 3.0-3.8 C, max 10.2 C (ERCO thunderstorm, 2 Aug 2022)
WEATHER_ROBUST_Z_UNUSUAL = 3.5                # |robust z| > 3.5 per location x variable -> unusual_high / unusual_low (value kept); not applied to precipitation (MAD = 0)