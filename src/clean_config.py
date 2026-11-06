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