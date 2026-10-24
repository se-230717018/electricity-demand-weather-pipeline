"""Load Open-Meteo raw files into the location, weather and quarantine tables (M2)."""


def load_weather(con, files):
    """files: [(Path, retrieved_at), ...] sorted oldest -> newest.

    Returns a summary dict. Does not open, commit or roll back the connection:
    load.py owns the transaction.
    """
    return {"files": 0, "values_cleaned": 0, "quarantined": 0}