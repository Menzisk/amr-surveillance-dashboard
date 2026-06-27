"""
03_analytics_queries.py
-----------------------
SQL analytics queries for the AMR surveillance dashboard.

Each query answers a specific epidemiological question.
Results are printed and saved to data/processed/ as TSVs
ready for the Streamlit dashboard.

Author: Menzisk
"""

import duckdb
import pandas as pd
import os

DB_PATH       = "data/amr_surveillance.duckdb"
PROCESSED_DIR = "data/processed"
os.makedirs(PROCESSED_DIR, exist_ok=True)

con = duckdb.connect(DB_PATH)

# ── QUERY 1: Record counts by organism ──────────────────────────────────────
#
# The simplest surveillance question: how many isolates do we have per species?
# COUNT(*) counts every row. GROUP BY collapses rows with the same organism
# into one summary row. ORDER BY DESC puts the largest first.

print("=" * 60)
print("QUERY 1: Records by organism")
print("=" * 60)

q1 = """
    SELECT
        organism,
        COUNT(*) AS total_records
    FROM amr_records
    GROUP BY organism
    ORDER BY total_records DESC
"""

df1 = con.execute(q1).df()
print(df1.to_string(index=False))
df1.to_csv(f"{PROCESSED_DIR}/q1_records_by_organism.tsv", sep="\t", index=False)

# ── QUERY 2: Top antibiotics tested per organism ─────────────────────────────
#
# Which antibiotics are most commonly tested for each pathogen?
# This tells us where the surveillance focus lies clinically.
#
# New concept: we filter WHERE organism = specific value,
# then count and rank antibiotics within that organism.

print("\n" + "=" * 60)
print("QUERY 2: Top 10 antibiotics tested for A. baumannii")
print("=" * 60)

q2 = """
    SELECT
        antibiotic,
        COUNT(*) AS times_tested
    FROM amr_records
    WHERE organism = 'Acinetobacter baumannii'
    GROUP BY antibiotic
    ORDER BY times_tested DESC
    LIMIT 10
"""

df2 = con.execute(q2).df()
print(df2.to_string(index=False))

# ── QUERY 3: Resistance rates by organism ────────────────────────────────────
#
# The core surveillance metric: what proportion of isolates are resistant?
#
# New concepts:
#   CASE WHEN ... THEN ... END  — conditional logic inside SQL
#   AVG()  — average of a 0/1 flag = proportion
#   ROUND() — round to decimal places
#   HAVING — filter on aggregated results (like WHERE but after GROUP BY)
#
# We flag each record as 1 (Resistant) or 0 (not Resistant),
# then AVG() those flags to get the resistance rate.
#
# We only look at records where measurement is a qualitative R/S/I call
# (i.e. measurement_sign IS NULL and measurement is not a raw MIC number)

print("\n" + "=" * 60)
print("QUERY 3: Resistance rates by organism")
print("=" * 60)

q3 = """
    SELECT
        organism,
        COUNT(*)                                                AS total_tested,
        SUM(CASE WHEN measurement_sign = 'Resistant'
                 THEN 1 ELSE 0 END)                            AS resistant_count,
        ROUND(
            100.0 * SUM(CASE WHEN measurement_sign = 'Resistant'
                             THEN 1 ELSE 0 END) / COUNT(*), 1
        )                                                       AS resistance_rate_pct
    FROM amr_records
    GROUP BY organism
    HAVING COUNT(*) >= 100
    ORDER BY resistance_rate_pct DESC
"""

df3 = con.execute(q3).df()
print(df3.to_string(index=False))
df3.to_csv(f"{PROCESSED_DIR}/q3_resistance_by_organism.tsv", sep="\t", index=False)

# ── QUERY 4: Distinct measurement_sign values ────────────────────────────────
#
# Before we do more resistance analysis, let's see what values
# measurement_sign actually contains — the raw data may surprise us.

print("\n" + "=" * 60)
print("QUERY 4: What values does measurement_sign contain?")
print("=" * 60)

q4 = """
    SELECT
        measurement_sign,
        COUNT(*) AS n
    FROM amr_records
    GROUP BY measurement_sign
    ORDER BY n DESC
"""

df4 = con.execute(q4).df()
print(df4.to_string(index=False))

# ── QUERY 5: Records by year ─────────────────────────────────────────────────
#
# Temporal trend — when were these isolates collected/inserted?
# Useful for showing how surveillance coverage has grown over time.

print("\n" + "=" * 60)
print("QUERY 5: Records inserted by year")
print("=" * 60)

q5 = """
    SELECT
        year_inserted,
        COUNT(*) AS records
    FROM amr_records
    WHERE year_inserted IS NOT NULL
      AND year_inserted BETWEEN 2000 AND 2026
    GROUP BY year_inserted
    ORDER BY year_inserted
"""

df5 = con.execute(q5).df()
print(df5.to_string(index=False))
df5.to_csv(f"{PROCESSED_DIR}/q5_records_by_year.tsv", sep="\t", index=False)

con.close()
print("\nAll queries complete. TSVs saved to data/processed/")
