"""
app.py
------
Streamlit AMR Surveillance Dashboard.
Connects to DuckDB and visualises AMR data across 6 ESKAPE pathogens.

Run with:
    streamlit run dashboard/app.py

Author: Menzisk
"""

import streamlit as st
import duckdb
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os

# ── Page config ──────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="AMR Surveillance Dashboard",
    page_icon="🦠",
    layout="wide",
)

# ── Database connection ───────────────────────────────────────────────────────

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "amr_surveillance.duckdb")

if not os.path.exists(DB_PATH):
    from setup_db import build_database
    build_database(DB_PATH)
    st.rerun()

@st.cache_resource
def get_connection():
    return duckdb.connect(DB_PATH, read_only=True)

con = get_connection()

# ── Header ───────────────────────────────────────────────────────────────────

st.title("🦠 AMR Surveillance Dashboard")
st.markdown(
    "Multi-pathogen antimicrobial resistance surveillance across **6 ESKAPE pathogens** "
    "using laboratory-confirmed AST data from [BV-BRC](https://www.bv-brc.org). "
    "Computational predictions excluded — lab records only."
)
st.divider()

# ── Sidebar filters ───────────────────────────────────────────────────────────

st.sidebar.header("Filters")

organisms = con.execute("""
    SELECT DISTINCT organism FROM amr_records ORDER BY organism
""").df()["organism"].tolist()

selected_organisms = st.sidebar.multiselect(
    "Pathogen",
    options=organisms,
    default=organisms,
)

year_min, year_max = con.execute("""
    SELECT MIN(year_inserted), MAX(year_inserted)
    FROM amr_records
    WHERE year_inserted BETWEEN 2000 AND 2026
""").fetchone()

selected_years = st.sidebar.slider(
    "Year range",
    min_value=int(year_min),
    max_value=int(year_max),
    value=(int(year_min), int(year_max)),
)

st.sidebar.markdown("---")
st.sidebar.markdown(
    "**Data source:** [BV-BRC](https://www.bv-brc.org) · Laboratory Method records only  \n"
    "**Built by:** Menzisk  \n"
    "**Stack:** Python · DuckDB · Streamlit · Plotly"
)

# ── Filter guard ──────────────────────────────────────────────────────────────

if not selected_organisms:
    st.warning("Select at least one pathogen from the sidebar.")
    st.stop()

org_filter  = str(tuple(selected_organisms)) if len(selected_organisms) > 1 else f"('{selected_organisms[0]}')"
year_filter = f"year_inserted BETWEEN {selected_years[0]} AND {selected_years[1]}"

# ── Metric cards ──────────────────────────────────────────────────────────────

m1, m2, m3, m4 = st.columns(4)

total = con.execute(f"""
    SELECT COUNT(*) FROM amr_records
    WHERE organism IN {org_filter}
    AND {year_filter}
""").fetchone()[0]

isolates = con.execute(f"""
    SELECT COUNT(DISTINCT genome_id) FROM amr_records
    WHERE organism IN {org_filter}
    AND {year_filter}
""").fetchone()[0]

antibiotics = con.execute(f"""
    SELECT COUNT(DISTINCT antibiotic) FROM amr_records
    WHERE organism IN {org_filter}
    AND {year_filter}
""").fetchone()[0]

years_covered = con.execute(f"""
    SELECT COUNT(DISTINCT year_inserted) FROM amr_records
    WHERE organism IN {org_filter}
    AND {year_filter}
    AND year_inserted IS NOT NULL
""").fetchone()[0]

m1.metric("Total records", f"{total:,}")
m2.metric("Unique isolates", f"{isolates:,}")
m3.metric("Antibiotics tracked", f"{antibiotics:,}")
m4.metric("Years covered", f"{years_covered}")

st.divider()

# ── Row 1: Records by organism + Surveillance over time ───────────────────────

col1, col2 = st.columns(2)

with col1:
    st.subheader("Records by organism")
    df_org = con.execute(f"""
        SELECT organism, COUNT(*) AS records
        FROM amr_records
        WHERE organism IN {org_filter}
        AND {year_filter}
        GROUP BY organism
        ORDER BY records DESC
    """).df()

    fig1 = px.bar(
        df_org,
        x="records",
        y="organism",
        orientation="h",
        color="records",
        color_continuous_scale="Blues",
        labels={"records": "Records", "organism": ""},
    )
    fig1.update_layout(
        showlegend=False,
        coloraxis_showscale=False,
        margin=dict(l=0, r=0, t=0, b=0),
        height=300,
    )
    st.plotly_chart(fig1, use_container_width=True)

with col2:
    st.subheader("Surveillance records over time")
    df_time = con.execute(f"""
        SELECT year_inserted, organism, COUNT(*) AS records
        FROM amr_records
        WHERE organism IN {org_filter}
        AND {year_filter}
        AND year_inserted IS NOT NULL
        GROUP BY year_inserted, organism
        ORDER BY year_inserted
    """).df()

    fig2 = px.line(
        df_time,
        x="year_inserted",
        y="records",
        color="organism",
        labels={"year_inserted": "Year", "records": "Records", "organism": "Organism"},
        markers=True,
    )
    fig2.update_layout(
        margin=dict(l=0, r=0, t=0, b=0),
        height=300,
        legend=dict(font=dict(size=10)),
    )
    st.plotly_chart(fig2, use_container_width=True)

st.divider()

# ── Row 2: MIC heatmap ────────────────────────────────────────────────────────

st.subheader("Median MIC by organism and antibiotic")
st.caption("Key clinical antibiotic-pathogen pairs · higher MIC = less susceptible")

df_mic = con.execute(f"""
    SELECT
        organism,
        antibiotic,
        ROUND(MEDIAN(measurement_value), 2) AS median_mic,
        COUNT(*) AS n
    FROM amr_records
    WHERE organism IN {org_filter}
    AND {year_filter}
    AND measurement_value IS NOT NULL
    AND (
        (organism = 'Acinetobacter baumannii'  AND antibiotic IN ('imipenem','meropenem','colistin','ciprofloxacin','amikacin','gentamicin'))
     OR (organism = 'Klebsiella pneumoniae'    AND antibiotic IN ('meropenem','imipenem','colistin','ciprofloxacin','amikacin','gentamicin'))
     OR (organism = 'Pseudomonas aeruginosa'   AND antibiotic IN ('meropenem','imipenem','ciprofloxacin','colistin','tobramycin','amikacin'))
     OR (organism = 'Staphylococcus aureus'    AND antibiotic IN ('oxacillin','vancomycin','linezolid','daptomycin','gentamicin','ciprofloxacin'))
     OR (organism = 'Enterococcus faecium'     AND antibiotic IN ('vancomycin','linezolid','daptomycin','ampicillin','gentamicin','teicoplanin'))
     OR (organism = 'Enterobacter cloacae'     AND antibiotic IN ('meropenem','imipenem','ciprofloxacin','ceftriaxone','gentamicin','amikacin'))
    )
    GROUP BY organism, antibiotic
    HAVING COUNT(*) >= 10
""").df()

if not df_mic.empty:
    pivot = df_mic.pivot(index="organism", columns="antibiotic", values="median_mic")
    fig3 = px.imshow(
        pivot,
        color_continuous_scale="RdYlGn_r",
        labels={"color": "Median MIC (mg/L)"},
        aspect="auto",
    )
    fig3.update_layout(
        margin=dict(l=0, r=0, t=0, b=0),
        height=350,
        xaxis_title="",
        yaxis_title="",
    )
    st.plotly_chart(fig3, use_container_width=True)
else:
    st.info("No MIC data available for the selected filters.")

st.divider()

# ── Row 3: Top antibiotics per organism ───────────────────────────────────────

st.subheader("Top antibiotics tested per organism")

selected_org_detail = st.selectbox(
    "Select organism",
    options=selected_organisms,
    index=0,
)

df_abx = con.execute(f"""
    SELECT antibiotic, COUNT(*) AS times_tested
    FROM amr_records
    WHERE organism = '{selected_org_detail}'
    AND {year_filter}
    GROUP BY antibiotic
    ORDER BY times_tested DESC
    LIMIT 15
""").df()

fig4 = px.bar(
    df_abx,
    x="antibiotic",
    y="times_tested",
    color="times_tested",
    color_continuous_scale="Purples",
    labels={"times_tested": "Times tested", "antibiotic": "Antibiotic"},
)
fig4.update_layout(
    showlegend=False,
    coloraxis_showscale=False,
    margin=dict(l=0, r=0, t=0, b=0),
    height=320,
    xaxis_tickangle=-35,
)
st.plotly_chart(fig4, use_container_width=True)

st.divider()

# ── Footer ────────────────────────────────────────────────────────────────────

st.caption(
    "Data: BV-BRC (Bacterial and Viral Bioinformatics Resource Center) · "
    "Laboratory Method records only · Computational predictions excluded · "
    "130,076 records across 6 ESKAPE pathogens"
)
