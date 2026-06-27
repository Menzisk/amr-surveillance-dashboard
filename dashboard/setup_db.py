"""
setup_db.py
-----------
Called by app.py on first run if the database doesn't exist.
Downloads a lightweight subset of BV-BRC data and builds the DuckDB database.

For the full 1.3M record pipeline, run scripts/01_download_bvbrc.py
and scripts/02_load_duckdb.py locally.

Author: Menzisk
"""

import requests
import json
import duckdb
import pandas as pd
import os
import streamlit as st

BASE_URL = "https://www.bv-brc.org/api/genome_amr/"
HEADERS  = {
    "accept": "application/json",
    "content-type": "application/rqlquery+x-www-form-urlencoded",
}

ESKAPE_PATHOGENS = [
    {"name": "Enterococcus faecium",    "taxon_id": 1352, "short_name": "E_faecium"},
    {"name": "Staphylococcus aureus",   "taxon_id": 1280, "short_name": "S_aureus"},
    {"name": "Klebsiella pneumoniae",   "taxon_id": 573,  "short_name": "K_pneumoniae"},
    {"name": "Acinetobacter baumannii", "taxon_id": 470,  "short_name": "A_baumannii"},
    {"name": "Pseudomonas aeruginosa",  "taxon_id": 287,  "short_name": "P_aeruginosa"},
    {"name": "Enterobacter cloacae",    "taxon_id": 550,  "short_name": "E_cloacae"},
]

TAXON_LABELS = {
    1352: "Enterococcus faecium",
    1280: "Staphylococcus aureus",
     573: "Klebsiella pneumoniae",
     470: "Acinetobacter baumannii",
     287: "Pseudomonas aeruginosa",
     550: "Enterobacter cloacae",
}

FIELD_MAP = {
    "record_id":                "id",
    "genome_id":                "genome_id",
    "genome_name":              "genome_name",
    "taxon_id":                 "taxon_id",
    "antibiotic":               "antibiotic",
    "measurement":              "measurement",
    "measurement_sign":         "measurement_sign",
    "measurement_value":        "measurement_value",
    "measurement_unit":         "measurement_unit",
    "laboratory_typing_method": "laboratory_typing_method",
    "evidence":                 "evidence",
    "pmid":                     "pmid",
    "date_inserted":            "date_inserted",
}

def extract_year(date_str):
    try:
        return int(str(date_str)[:4])
    except:
        return None

def flatten_pmid(pmid_val):
    if isinstance(pmid_val, list):
        return ";".join(str(p) for p in pmid_val)
    elif pmid_val:
        return str(pmid_val)
    return None

def fetch_pathogen(pathogen, limit=5000, progress_text=""):
    """Fetch up to `limit` lab records for one pathogen."""
    taxon_id = pathogen["taxon_id"]
    all_records = []
    cursor = "*"
    previous_cursor = None

    while len(all_records) < limit:
        params = (
            f"eq(taxon_id,{taxon_id})"
            f"&limit(25000)"
            f"&cursor({cursor})"
            f"&sort(+genome_id)"
        )
        try:
            response = requests.get(BASE_URL, params=params, headers=HEADERS, timeout=60)
            response.raise_for_status()
        except Exception as e:
            break

        data = response.json()
        records = data if isinstance(data, list) else data.get("data", [])
        if not records:
            break

        lab = [r for r in records if r.get("evidence") == "Laboratory Method"]
        all_records.extend(lab)

        next_cursor = response.headers.get("X-Cursor-Mark", cursor)
        if next_cursor == previous_cursor or next_cursor == cursor:
            break
        previous_cursor = cursor
        cursor = next_cursor

        if len(all_records) >= limit:
            break

    return all_records[:limit]

def parse_records(raw_records):
    parsed = []
    for r in raw_records:
        if r.get("evidence") != "Laboratory Method":
            continue
        row = {our: r.get(bvbrc) for our, bvbrc in FIELD_MAP.items()}
        row["organism"]      = TAXON_LABELS.get(r.get("taxon_id"), "Unknown")
        row["year_inserted"] = extract_year(r.get("date_inserted"))
        row["pmid"]          = flatten_pmid(r.get("pmid"))
        try:
            row["measurement_value"] = float(row["measurement_value"]) if row["measurement_value"] is not None else None
        except:
            row["measurement_value"] = None
        try:
            row["taxon_id"] = int(row["taxon_id"]) if row["taxon_id"] is not None else None
        except:
            row["taxon_id"] = None
        parsed.append(row)
    return parsed

def build_database(db_path):
    """Download a representative subset and build the DuckDB database."""
    st.info("Building database from BV-BRC — this runs once and takes ~2 minutes...")
    progress = st.progress(0)
    all_rows = []

    for i, pathogen in enumerate(ESKAPE_PATHOGENS):
        progress.progress((i) / len(ESKAPE_PATHOGENS), text=f"Fetching {pathogen['name']}...")
        raw     = fetch_pathogen(pathogen, limit=5000)
        parsed  = parse_records(raw)
        all_rows.extend(parsed)

    progress.progress(1.0, text="Loading into database...")

    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    df  = pd.DataFrame(all_rows)
    con = duckdb.connect(db_path)
    con.execute("DROP TABLE IF EXISTS amr_records")
    con.execute("CREATE TABLE amr_records AS SELECT * FROM df")
    count = con.execute("SELECT COUNT(*) FROM amr_records").fetchone()[0]
    con.close()

    st.success(f"Database ready — {count:,} records loaded.")
    return count
