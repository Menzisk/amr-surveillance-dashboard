"""
02_load_duckdb.py
-----------------
Loads raw BV-BRC JSON files into a DuckDB surveillance database.

Filters to Laboratory Method records only — excluding computational
predictions — to ensure the dashboard reflects real clinical AST data.

Schema produced:
    amr_records — one row per isolate-antibiotic measurement

Author: Menzisk
"""

import json
import glob
import os
import duckdb
import pandas as pd
from datetime import datetime

# ── Configuration ────────────────────────────────────────────────────────────

RAW_DIR  = "data/raw"
DB_PATH  = "data/amr_surveillance.duckdb"

# Fields we extract from each raw record
# Left side = our clean column name, Right side = BV-BRC field name
FIELD_MAP = {
    "record_id":               "id",
    "genome_id":               "genome_id",
    "genome_name":             "genome_name",
    "taxon_id":                "taxon_id",
    "antibiotic":              "antibiotic",
    "measurement_sign":        "measurement_sign",
    "measurement_value":       "measurement_value",
    "measurement_unit":        "measurement_unit",
    "laboratory_typing_method":"laboratory_typing_method",
    "evidence":                "evidence",
    "pmid":                    "pmid",
    "date_inserted":           "date_inserted",
}

# ESKAPE pathogen label map — taxon_id → short name
TAXON_LABELS = {
    1352: "Enterococcus faecium",
    1280: "Staphylococcus aureus",
     573: "Klebsiella pneumoniae",
     470: "Acinetobacter baumannii",
     287: "Pseudomonas aeruginosa",
     550: "Enterobacter cloacae",
}

# ── Helper functions ─────────────────────────────────────────────────────────

def extract_year(date_str: str) -> int | None:
    """Extract year from ISO date string e.g. '2020-02-05T23:12:49.253Z'"""
    try:
        return int(date_str[:4])
    except (TypeError, ValueError):
        return None

def flatten_pmid(pmid_val) -> str | None:
    """
    pmid field comes as a list e.g. [31479500] — flatten to a string.
    Some records may have multiple PMIDs.
    """
    if isinstance(pmid_val, list):
        return ";".join(str(p) for p in pmid_val)
    elif pmid_val:
        return str(pmid_val)
    return None

def load_json_file(filepath: str) -> list[dict]:
    """Load a raw JSON file and return its records."""
    with open(filepath) as f:
        return json.load(f)

def parse_records(raw_records: list[dict]) -> list[dict]:
    """
    Filter to Laboratory Method records and extract relevant fields.

    Why we exclude Computational Method:
        BV-BRC uses an XGBoost model to predict MIC values for genomes
        that lack phenotype data. These predictions are useful for
        research but should not be treated as clinical observations
        in a surveillance context.
    """
    parsed = []

    for r in raw_records:
        # Filter: keep only real lab measurements
        if r.get("evidence") != "Laboratory Method":
            continue

        row = {}

        # Extract fields using our field map
        for our_name, bvbrc_name in FIELD_MAP.items():
            row[our_name] = r.get(bvbrc_name)

        # Derived fields
        row["organism"]     = TAXON_LABELS.get(r.get("taxon_id"), "Unknown")
        row["year_inserted"] = extract_year(r.get("date_inserted"))
        row["pmid"]         = flatten_pmid(r.get("pmid"))

        # Ensure numeric types
        try:
            row["measurement_value"] = float(row["measurement_value"]) if row["measurement_value"] is not None else None
        except (ValueError, TypeError):
            row["measurement_value"] = None

        try:
            row["taxon_id"] = int(row["taxon_id"]) if row["taxon_id"] is not None else None
        except (ValueError, TypeError):
            row["taxon_id"] = None

        parsed.append(row)

    return parsed

# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("AMR Surveillance Dashboard — DuckDB Loader")
    print(f"Started : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # Find all raw JSON files
    files = sorted(glob.glob(os.path.join(RAW_DIR, "*_amr_*.json")))
    if not files:
        print(f"ERROR: No JSON files found in {RAW_DIR}/")
        return

    print(f"\nFound {len(files)} raw files:")
    for f in files:
        print(f"  {f}")

    # Parse all files into one list
    all_rows = []
    for filepath in files:
        raw = load_json_file(filepath)
        parsed = parse_records(raw)
        print(f"\n  {os.path.basename(filepath)}")
        print(f"    raw records : {len(raw):>8,}")
        print(f"    lab records : {len(parsed):>8,}")
        all_rows.extend(parsed)

    print(f"\nTotal lab records across all pathogens: {len(all_rows):,}")

    # Convert to DataFrame
    df = pd.DataFrame(all_rows)

    print(f"\nDataFrame shape : {df.shape}")
    print(f"Columns         : {list(df.columns)}")
    print(f"\nNull counts:")
    print(df.isnull().sum().to_string())

    # ── Load into DuckDB ─────────────────────────────────────────────────────
    #
    # DuckDB can read a pandas DataFrame directly — no CSV intermediate needed.
    # We create (or replace) a table called amr_records.
    # CREATE OR REPLACE means re-running this script is safe — it overwrites.

    print(f"\nConnecting to DuckDB: {DB_PATH}")
    con = duckdb.connect(DB_PATH)

    con.execute("DROP TABLE IF EXISTS amr_records")
    con.execute("""
        CREATE TABLE amr_records AS
        SELECT * FROM df
    """)

    # Verify
    count = con.execute("SELECT COUNT(*) FROM amr_records").fetchone()[0]
    print(f"Records loaded into DuckDB: {count:,}")

    # Quick sanity check by organism
    print("\nRecord counts by organism:")
    result = con.execute("""
        SELECT organism, COUNT(*) as n
        FROM amr_records
        GROUP BY organism
        ORDER BY n DESC
    """).fetchall()

    for row in result:
        print(f"  {row[0]:<30} {row[1]:>8,}")

    con.close()
    print(f"\nDatabase saved to: {os.path.abspath(DB_PATH)}")
    print(f"Completed : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    main()
