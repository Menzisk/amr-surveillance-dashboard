"""
03_analytics_queries.py
-----------------------
SQL analytics queries for the AMR surveillance dashboard.

Data note: BV-BRC Laboratory Method records contain raw MIC values,
not interpreted R/S/I phenotype calls. All analysis is therefore
MIC-based and coverage-based rather than resistance-rate-based.

Queries:
    Q1  — Record counts by organism
    Q2  — Top antibiotics tested per organism
    Q3  — MIC value distributions (top organism-antibiotic pairs)
    Q4  — Surveillance coverage over time by organism
    Q5  — Top 10 most tested organism-antibiotic combinations
    Q6  — Laboratory typing method breakdown
    Q7  — Median MIC by organism and antibiotic (key clinical pairs)

Author: Menzisk
"""

import duckdb
import pandas as pd
import os

DB_PATH       = "data/amr_surveillance.duckdb"
PROCESSED_DIR = "data/processed"
os.makedirs(PROCESSED_DIR, exist_ok=True)

con = duckdb.connect(DB_PATH)

def run_query(title, sql):
    print(f"\n{'='*60}")
    print(f"{title}")
    print('='*60)
    df = con.execute(sql).df()
    print(df.to_string(index=False))
    return df

# ── Q1: Record counts by organism ────────────────────────────────────────────
df1 = run_query("Q1: Records by organism", """
    SELECT
        organism,
        COUNT(*)                        AS total_records,
        COUNT(DISTINCT antibiotic)      AS antibiotics_tested,
        COUNT(DISTINCT genome_id)       AS unique_isolates
    FROM amr_records
    GROUP BY organism
    ORDER BY total_records DESC
""")
df1.to_csv(f"{PROCESSED_DIR}/q1_records_by_organism.tsv", sep="\t", index=False)

# ── Q2: Top antibiotics per organism ─────────────────────────────────────────
# New concept: we loop over organisms and run the same query per organism.
# In SQL this is done with a WHERE clause filter.
df2_all = []
for organism in df1["organism"].tolist():
    df_org = con.execute("""
        SELECT
            ? AS organism,
            antibiotic,
            COUNT(*) AS times_tested
        FROM amr_records
        WHERE organism = ?
        GROUP BY antibiotic
        ORDER BY times_tested DESC
        LIMIT 10
    """, [organism, organism]).df()
    df2_all.append(df_org)

df2 = pd.concat(df2_all, ignore_index=True)
print(f"\n{'='*60}\nQ2: Top antibiotics per organism\n{'='*60}")
print(df2.to_string(index=False))
df2.to_csv(f"{PROCESSED_DIR}/q2_top_antibiotics_per_organism.tsv", sep="\t", index=False)

# ── Q3: Top organism-antibiotic combinations ──────────────────────────────────
# New concept: concatenating two columns with || to make a label.
# HAVING filters aggregated results — like WHERE but after GROUP BY.
df3 = run_query("Q3: Top 15 organism-antibiotic combinations by test volume", """
    SELECT
        organism,
        antibiotic,
        COUNT(*)                                    AS times_tested,
        COUNT(CASE WHEN measurement_value IS NOT NULL
                   THEN 1 END)                      AS has_mic_value,
        ROUND(AVG(measurement_value), 2)            AS mean_mic,
        ROUND(MEDIAN(measurement_value), 2)         AS median_mic
    FROM amr_records
    WHERE measurement_value IS NOT NULL
    GROUP BY organism, antibiotic
    HAVING COUNT(*) >= 50
    ORDER BY times_tested DESC
    LIMIT 15
""")
df3.to_csv(f"{PROCESSED_DIR}/q3_organism_antibiotic_mic_summary.tsv", sep="\t", index=False)

# ── Q4: Surveillance coverage over time ──────────────────────────────────────
# New concept: filtering a range with BETWEEN.
# This query shows how many records were added each year per organism —
# a proxy for how surveillance intensity has changed over time.
df4 = run_query("Q4: Records by year and organism", """
    SELECT
        year_inserted,
        organism,
        COUNT(*) AS records
    FROM amr_records
    WHERE year_inserted BETWEEN 2010 AND 2026
    GROUP BY year_inserted, organism
    ORDER BY year_inserted, records DESC
""")
df4.to_csv(f"{PROCESSED_DIR}/q4_records_by_year_organism.tsv", sep="\t", index=False)

# ── Q5: Laboratory typing method breakdown ────────────────────────────────────
# Which AST methods are used? Broth dilution, agar dilution, E-test?
# Important for methodological context in surveillance.
df5 = run_query("Q5: Laboratory typing methods", """
    SELECT
        laboratory_typing_method,
        COUNT(*)                        AS n,
        COUNT(DISTINCT organism)        AS organisms_covered
    FROM amr_records
    WHERE laboratory_typing_method IS NOT NULL
    GROUP BY laboratory_typing_method
    ORDER BY n DESC
""")
df5.to_csv(f"{PROCESSED_DIR}/q5_typing_methods.tsv", sep="\t", index=False)

# ── Q6: Key clinical MIC summary ─────────────────────────────────────────────
# For the most clinically critical antibiotic-organism pairs,
# what does the MIC distribution look like?
# These pairs are selected based on WHO critical priority pathogens
# and their first-line or last-resort antibiotics.
df6 = run_query("Q6: Key clinical pairs — MIC summary", """
    SELECT
        organism,
        antibiotic,
        COUNT(*)                        AS n,
        ROUND(MIN(measurement_value),2) AS mic_min,
        ROUND(MEDIAN(measurement_value),2) AS mic_median,
        ROUND(MAX(measurement_value),2) AS mic_max,
        ROUND(AVG(measurement_value),2) AS mic_mean
    FROM amr_records
    WHERE measurement_value IS NOT NULL
      AND (
          (organism = 'Acinetobacter baumannii'  AND antibiotic IN ('imipenem','meropenem','colistin','ciprofloxacin'))
       OR (organism = 'Klebsiella pneumoniae'    AND antibiotic IN ('meropenem','imipenem','colistin','tigecycline'))
       OR (organism = 'Pseudomonas aeruginosa'   AND antibiotic IN ('meropenem','imipenem','ciprofloxacin','colistin'))
       OR (organism = 'Staphylococcus aureus'    AND antibiotic IN ('oxacillin','vancomycin','linezolid','daptomycin'))
       OR (organism = 'Enterococcus faecium'     AND antibiotic IN ('vancomycin','linezolid','daptomycin','ampicillin'))
       OR (organism = 'Enterobacter cloacae'     AND antibiotic IN ('meropenem','imipenem','ciprofloxacin','ceftriaxone'))
      )
    GROUP BY organism, antibiotic
    HAVING COUNT(*) >= 10
    ORDER BY organism, antibiotic
""")
df6.to_csv(f"{PROCESSED_DIR}/q6_key_clinical_pairs_mic.tsv", sep="\t", index=False)

con.close()
print(f"\n{'='*60}")
print("All queries complete.")
print(f"TSVs saved to {PROCESSED_DIR}/")
