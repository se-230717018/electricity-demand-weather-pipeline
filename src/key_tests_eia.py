"""Key tests on the raw EIA files: do our chosen keys hold?

Reads data/raw/eia only (no API). Checks one ingestion run (the newest).
"""
import json
import sys
from pathlib import Path

import pandas as pd

RAW = Path(__file__).resolve().parent.parent / "data" / "raw" / "eia"
KEY = ["respondent", "type", "period"]


def main():
    files = sorted(RAW.glob("*.json"))
    if not files:
        sys.exit("no EIA files in data/raw/eia")

    latest = max(p.name.split("_")[0] for p in files)
    run = [p for p in files if p.name.startswith(latest)]

    frames = []
    for p in run:
        data = json.loads(p.read_text(encoding="utf-8"))["response"]["data"]
        frames.append(pd.DataFrame(data))
    df = pd.concat(frames, ignore_index=True)

    print(f"run {latest}: {len(run)} files, {len(df)} records")
    print("records with a missing key field:", int(df[KEY].isna().any(axis=1).sum()))
    print("duplicate (respondent, type, period):", int(df.duplicated(subset=KEY).sum()))
    print("respondents with more than one respondent-name:",
          int((df.groupby("respondent")["respondent-name"].nunique() > 1).sum()))
    print("types with more than one type-name:",
          int((df.groupby("type")["type-name"].nunique() > 1).sum()))

    numeric = pd.to_numeric(df["value"], errors="coerce")
    print("empty or non-numeric value:", int(numeric.isna().sum()))
    print("non-numeric values by respondent and type:")
    print(df[numeric.isna()].groupby(["respondent", "type"]).size().to_string())


if __name__ == "__main__":
    main()