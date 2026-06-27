# AMR Surveillance Dashboard

A multi-pathogen antimicrobial resistance (AMR) surveillance pipeline covering the six ESKAPE pathogens, the leading causes of hospital-acquired infections globally.

Built to demonstrate production-style data engineering and public health analytics: automated data ingestion from BV-BRC, a structured DuckDB surveillance database, and an interactive Streamlit dashboard with global coverage and African contextualisation.

---

## ESKAPE pathogens covered

| Pathogen | Abbreviation | Clinical significance |
|---|---|---|
| *Enterococcus faecium* | Efm | Vancomycin-resistant enterococci (VRE) |
| *Staphylococcus aureus* | Sa | MRSA; leading cause of bloodstream infections |
| *Klebsiella pneumoniae* | Kpn | Carbapenem-resistant; WHO critical priority |
| *Acinetobacter baumannii* | Ab | Pan-drug resistant; nosocomial outbreaks |
| *Pseudomonas aeruginosa* | Pa | Intrinsic multidrug resistance |
| *Enterobacter* spp. | Ent | Extended-spectrum beta-lactamase producers |

---

## Tech stack

- **Data source:** BV-BRC (Bacterial and Viral Bioinformatics Resource Center) API
- **Database:** DuckDB — embedded analytical SQL database
- **Dashboard:** Streamlit + Plotly
- **Language:** Python 3.11

---

## Project structure
amr-surveillance-dashboard/

├── data/

│   ├── raw/          # BV-BRC API downloads (JSON) - not tracked by git

│   └── processed/    # Cleaned TSVs ready for DuckDB — not tracked by git

├── scripts/          # Data ingestion and processing pipeline

├── notebooks/        # Exploratory analysis and SQL development

├── dashboard/        # Streamlit app

├── tests/            # Validation scripts

├── environment.yml   # Conda environment specification

└── README.md

---

## Quickstart

```bash
# 1. Clone the repo
git clone https://github.com/Menzisk/amr-surveillance-dashboard.git
cd amr-surveillance-dashboard

# 2. Create and activate conda environment
conda env create -f environment.yml
conda activate amr-surveillance

# 3. Run data ingestion
python scripts/01_download_bvbrc.py

# 4. Launch dashboard
streamlit run dashboard/app.py
```

---

## Geographic focus

Pipeline covers global BV-BRC submissions. South Africa and the broader African region are highlighted as a contextual lens, relevant to public health surveillance priorities at institutions such as NICD.

---

## Status

Active development: follow the commit history to see the build in progress.


---

## Live dashboard

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://amr-surveillance-menzisk.streamlit.app)

> Replace the URL above with your actual Streamlit Cloud deployment URL.

---

## Live dashboard

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://amr-surveillance-menzisk.streamlit.app)
