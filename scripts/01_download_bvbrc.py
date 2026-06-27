"""
01_download_bvbrc.py
--------------------
Downloads AMR phenotype records for all six ESKAPE pathogens
from the BV-BRC (Bacterial and Viral Bioinformatics Resource Center) API.

Raw JSON responses are saved to data/raw/ these files are never modified.
All cleaning and transformation happens in downstream scripts.

BV-BRC AMR API endpoint:
    https://www.bv-brc.org/api/amr/
    Documentation: https://www.bv-brc.org/api/doc/

Author: Menzisk
"""

import requests
import json
import os
import time
from datetime import datetime

# ── 1. ESKAPE pathogen definitions ─────────────────────────────────────────
#
# Each pathogen is identified by its NCBI taxon_id.
# BV-BRC uses taxon_id as the primary filter for organism-level queries.
# We also store a short_name for labelling output files cleanly.
#
# Taxon IDs sourced from NCBI Taxonomy:
#   https://www.ncbi.nlm.nih.gov/taxonomy

ESKAPE_PATHOGENS = [
    {"name": "Enterococcus faecium",    "taxon_id": 1352,   "short_name": "E_faecium"},
    {"name": "Staphylococcus aureus",   "taxon_id": 1280,   "short_name": "S_aureus"},
    {"name": "Klebsiella pneumoniae",   "taxon_id": 573,    "short_name": "K_pneumoniae"},
    {"name": "Acinetobacter baumannii", "taxon_id": 470,    "short_name": "A_baumannii"},
    {"name": "Pseudomonas aeruginosa",  "taxon_id": 287,    "short_name": "P_aeruginosa"},
    {"name": "Enterobacter cloacae",    "taxon_id": 550,    "short_name": "E_cloacae"},
]

# ── 2. API configuration ────────────────────────────────────────────────────
#
# BV-BRC exposes a public REST API. No authentication required for AMR data.
#
# Key parameters:
#   eq(taxon_id,<ID>)  — filter by organism
#   limit(<N>)         — max records per request (BV-BRC cap is 25000)
#   http_accept        — we request JSON for reliable parsing

BASE_URL = "https://www.bv-brc.org/api/genome_amr/"
LIMIT    = 25000
HEADERS  = {
    "accept": "application/json",
    "content-type": "application/rqlquery+x-www-form-urlencoded",
}

# ── 3. Output directory ─────────────────────────────────────────────────────

RAW_DIR = "data/raw"
os.makedirs(RAW_DIR, exist_ok=True)

# ── 4. Download function ────────────────────────────────────────────────────

def download_amr_data(pathogen: dict) -> dict:
    """
    Downloads AMR records for a single pathogen from BV-BRC.

    Parameters
    ----------
    pathogen : dict
        A dictionary with keys: name, taxon_id, short_name

    Returns
    -------
    dict
        Summary of what was downloaded: pathogen name, record count, file path
    """
    name       = pathogen["name"]
    taxon_id   = pathogen["taxon_id"]
    short_name = pathogen["short_name"]

    print(f"\n[{name}]")
    print(f"  taxon_id : {taxon_id}")
    print(f"  querying : {BASE_URL}")

    # Build the RQL query string
    # RQL = Resource Query Language: BV-BRC's filter syntax
    # eq(field,value) means "where field equals value"
    params = f"eq(taxon_id,{taxon_id})&limit({LIMIT})"

    try:
        response = requests.get(
            BASE_URL,
            params=params,
            headers=HEADERS,
            timeout=120       # seconds, large datasets can be slow
        )
        response.raise_for_status()   # raises an error for 4xx/5xx responses

    except requests.exceptions.Timeout:
        print(f"  ERROR: request timed out for {name}")
        return {"name": name, "records": 0, "file": None, "status": "timeout"}

    except requests.exceptions.RequestException as e:
        print(f"  ERROR: {e}")
        return {"name": name, "records": 0, "file": None, "status": "error"}

    # Parse response
    data = response.json()

    # BV-BRC returns either a list directly or a dict with a data key
    if isinstance(data, list):
        records = data
    elif isinstance(data, dict) and "data" in data:
        records = data["data"]
    else:
        records = []

    record_count = len(records)
    print(f"  records  : {record_count:,}")

    # Save raw JSON
    # Filename includes date so repeated runs don't overwrite each other
    date_str  = datetime.today().strftime("%Y%m%d")
    filename  = f"{short_name}_amr_{date_str}.json"
    filepath  = os.path.join(RAW_DIR, filename)

    with open(filepath, "w") as f:
        json.dump(records, f, indent=2)

    print(f"  saved    : {filepath}")

    return {
        "name":    name,
        "records": record_count,
        "file":    filepath,
        "status":  "ok"
    }

# ── 5. Main execution ───────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("AMR Surveillance Dashboard — BV-BRC Data Ingestion")
    print(f"Started : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    results = []

    for pathogen in ESKAPE_PATHOGENS:
        result = download_amr_data(pathogen)
        results.append(result)
        time.sleep(1)    # polite pause between requests — don't hammer the API

    # ── Summary report ──────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("DOWNLOAD SUMMARY")
    print("=" * 60)

    total_records = 0
    for r in results:
        status_symbol = "✓" if r["status"] == "ok" else "✗"
        print(f"  {status_symbol}  {r['name']:<30} {r['records']:>7,} records")
        total_records += r["records"]

    print("-" * 60)
    print(f"     {'TOTAL':<30} {total_records:>7,} records")
    print("=" * 60)
    print(f"\nCompleted : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Raw files saved to: {os.path.abspath(RAW_DIR)}/")

if __name__ == "__main__":
    main()
