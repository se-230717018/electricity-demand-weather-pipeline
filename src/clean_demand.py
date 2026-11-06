"""Build demand_clean from the M2 demand table (M3).

Reads M2 tables with SELECT only. Does not open, commit or roll back the
connection: clean.py owns the transaction.
"""


def clean_demand(con):
    return {"table": "demand_clean", "rows": 0, "raw_rows": 0, "flags": {}}