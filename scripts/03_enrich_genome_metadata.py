"""
03_enrich_genome_metadata.py
-----------------------------
Fetches genome-level metadata (country, host, collection date)
from the BV-BRC /api/genome/ endpoint for all genome_ids
present in our amr_records table.

Strategy: batch requests of 200 genome_ids at a time to stay
within URL length limits while minimising API call count.

Adds a new DuckDB table: genome_metadata
Enriched view: amr_enriched (amr_records JOIN genome_metadata)

Author: Menzisk
"""

import requests
import duckdb
import pandas as pd
import time
import os
from datetime import datetime

DB_PATH  = "data/amr_surveillance.duckdb"
BASE_URL = "https://www.bv-brc.org/api/genome/"
HEADERS  = {"accept": "application/json"}
BATCH    = 200   # genome IDs per request

GENOME_FIELDS = [
    "genome_id",
    "isolation_country",
    "host_name",
    "host_group",
    "host_common_name",
    "collection_date",
    "genome_quality",
    "genome_status",
    "sequencing_status",
]

# ── Get all unique genome_ids from our database ───────────────────────────────

print("=" * 60)
print("BV-BRC Genome Metadata Enrichment")
print(f"Started : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("=" * 60)

con = duckdb.connect(DB_PATH)

genome_ids = con.execute("""
    SELECT DISTINCT genome_id FROM amr_records
    WHERE genome_id IS NOT NULL
""").df()["genome_id"].tolist()

print(f"\nUnique genome IDs to enrich: {len(genome_ids):,}")
print(f"Batch size                 : {BATCH}")
print(f"Estimated API calls        : {len(genome_ids) // BATCH + 1}")

# ── Batch fetch ───────────────────────────────────────────────────────────────

def fetch_batch(ids: list) -> list:
    """Fetch genome metadata for a batch of genome_ids."""
    ids_str    = ",".join(ids)
    fields_str = ",".join(GENOME_FIELDS)
    params     = f"in(genome_id,({ids_str}))&select({fields_str})&limit({len(ids)+10})"

    try:
        r = requests.get(BASE_URL, params=params, headers=HEADERS, timeout=60)
        r.raise_for_status()
        data = r.json()
        return data if isinstance(data, list) else data.get("data", [])
    except Exception as e:
        print(f"  WARNING: batch failed — {e}")
        return []

all_metadata = []
batches      = [genome_ids[i:i+BATCH] for i in range(0, len(genome_ids), BATCH)]
total        = len(batches)

for i, batch in enumerate(batches):
    results = fetch_batch(batch)
    all_metadata.extend(results)

    if (i + 1) % 10 == 0 or (i + 1) == total:
        print(f"  Batch {i+1:>4}/{total} | metadata records so far: {len(all_metadata):,}")

    time.sleep(0.3)   # polite pause

print(f"\nTotal genome metadata records fetched: {len(all_metadata):,}")

# ── Load into DuckDB ──────────────────────────────────────────────────────────

df_meta = pd.DataFrame(all_metadata)

# Ensure all expected columns exist even if API returned partial data
for col in GENOME_FIELDS:
    if col not in df_meta.columns:
        df_meta[col] = None

df_meta = df_meta[GENOME_FIELDS]

print(f"\nMetadata DataFrame shape: {df_meta.shape}")
print(f"\nCountry coverage:")
country_counts = df_meta["isolation_country"].value_counts()
print(f"  Records with country    : {df_meta['isolation_country'].notna().sum():,}")
print(f"  Unique countries        : {df_meta['isolation_country'].nunique():,}")
print(f"\nTop 10 countries:")
print(country_counts.head(10).to_string())

# Save to DuckDB
con.execute("DROP TABLE IF EXISTS genome_metadata")
con.execute("CREATE TABLE genome_metadata AS SELECT * FROM df_meta")

# ── Create enriched JOIN view ─────────────────────────────────────────────────
#
# A VIEW is a saved SQL query — not a table, but a named query
# you can SELECT from as if it were a table.
# Every time you query amr_enriched, DuckDB runs the JOIN live.

con.execute("DROP VIEW IF EXISTS amr_enriched")
con.execute("""
    CREATE VIEW amr_enriched AS
    SELECT
        a.record_id,
        a.genome_id,
        a.organism,
        a.antibiotic,
        a.measurement,
        a.measurement_sign,
        a.measurement_value,
        a.measurement_unit,
        a.laboratory_typing_method,
        a.year_inserted,
        g.isolation_country,
        g.host_name,
        g.host_group,
        g.collection_date,
        g.genome_quality
    FROM amr_records a
    LEFT JOIN genome_metadata g
        ON a.genome_id = g.genome_id
""")

# Verify
total_enriched = con.execute("SELECT COUNT(*) FROM amr_enriched").fetchone()[0]
with_country   = con.execute("""
    SELECT COUNT(*) FROM amr_enriched
    WHERE isolation_country IS NOT NULL
""").fetchone()[0]

print(f"\nEnriched view rows     : {total_enriched:,}")
print(f"Rows with country data : {with_country:,} ({100*with_country/total_enriched:.1f}%)")

print(f"\nTop 15 countries in enriched dataset:")
result = con.execute("""
    SELECT isolation_country, COUNT(*) as n
    FROM amr_enriched
    WHERE isolation_country IS NOT NULL
    GROUP BY isolation_country
    ORDER BY n DESC
    LIMIT 15
""").fetchall()
for row in result:
    print(f"  {row[0]:<30} {row[1]:>8,}")

con.close()
print(f"\nCompleted : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print(f"Tables added: genome_metadata, view: amr_enriched")
