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


# ---------------------------------------------------------------------------
# WEATHER (İrem) - src/clean_weather.py
# ---------------------------------------------------------------------------
# Add constants for weather_clean below this line, each with a comment.