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

BASE_URL = "https://www.bv-brc.org/api/genome_amr/"
LIMIT    = 25000
HEADERS  = {
    "accept": "application/json",
    "content-type": "application/rqlquery+x-www-form-urlencoded",
}

# ── 3. Output directory ─────────────────────────────────────────────────────

RAW_DIR = "data/raw"
os.makedirs(RAW_DIR, exist_ok=True)

# ── 4. Download function with cursor-based pagination ───────────────────────

def download_amr_data(pathogen: dict) -> dict:
    """
    Downloads ALL AMR records for a single pathogen from BV-BRC
    using cursor-based pagination to exceed the 25,000 record limit.

    BV-BRC returns an X-Cursor-Mark header with each response.
    We pass that cursor back in the next request to get the next page.
    Pagination ends when the cursor token stops changing.

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

    all_records  = []
    cursor       = "*"          # BV-BRC cursor pagination starts with *
    page         = 1
    previous_cursor = None

    while True:
        print(f"  page {page:>3} | cursor: {cursor[:30]}...")

        # Build RQL query with cursor
        params = (
            f"eq(taxon_id,{taxon_id})"
            f"&limit({LIMIT})"
            f"&cursor({cursor})"
            f"&sort(+genome_id)"    # cursor pagination requires a sort field
        )

        try:
            response = requests.get(
                BASE_URL,
                params=params,
                headers=HEADERS,
                timeout=120
            )
            response.raise_for_status()

        except requests.exceptions.Timeout:
            print(f"  ERROR: timeout on page {page} for {name}")
            break

        except requests.exceptions.RequestException as e:
            print(f"  ERROR: {e}")
            break

        # Parse records
        data = response.json()
        if isinstance(data, list):
            records = data
        elif isinstance(data, dict) and "data" in data:
            records = data["data"]
        else:
            records = []

        if not records:
            print(f"  no records returned on page {page} — stopping")
            break

        all_records.extend(records)
        print(f"  page {page:>3} | fetched {len(records):,} | total so far: {len(all_records):,}")

        # Get the next cursor from response headers
        next_cursor = response.headers.get("X-Cursor-Mark", cursor)

        # If cursor hasn't changed, we've reached the last page
        if next_cursor == previous_cursor or next_cursor == cursor:
            print(f"  cursor unchanged — all pages fetched")
            break

        previous_cursor = cursor
        cursor          = next_cursor
        page           += 1
        time.sleep(0.5)    # polite pause between pages

    # Save all records to a single JSON file
    total = len(all_records)
    print(f"  total records: {total:,}")

    date_str = datetime.today().strftime("%Y%m%d")
    filename = f"{short_name}_amr_{date_str}.json"
    filepath = os.path.join(RAW_DIR, filename)

    with open(filepath, "w") as f:
        json.dump(all_records, f, indent=2)

    print(f"  saved: {filepath}")

    return {
        "name":    name,
        "records": total,
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
