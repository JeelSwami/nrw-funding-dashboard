# EU research funding flow in North Rhine-Westphalia, Germany

**English** · [Deutsch](README.de.md)

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.21841052.svg)](https://doi.org/10.5281/zenodo.21841052)

**Live demo: [nrw-funding-dashboard.streamlit.app](https://nrw-funding-dashboard.streamlit.app)**

An interactive dashboard tracing every EU research grant that reached an
organisation in North Rhine-Westphalia (NRW) under Horizon 2020 (2014–2020)
and Horizon Europe (2021–2027), built from the official CORDIS bulk datasets
of the EU Publications Office.

At the August 2026 data snapshot, the two framework programmes committed
**€3.71 billion** to **1,128 NRW organisations** across **5,097 projects**,
which is **18.6 %** of the €19.9 billion that went to Germany as a whole.
Köln leads
the state (helped by DLR's legal seat there), followed by Bonn, Aachen and
Jülich; natural sciences and engineering together account for over half of
the field-attributed funding.

![Dashboard overview: filters, key figures and funding by start year](docs/screenshot-overview.png)

![DFG and EU funding side by side for NRW universities](docs/screenshot-dfg.png)

![Collaboration network of the largest NRW recipients and their European partners](docs/screenshot-network.png)

## Quickstart

```
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python src/fetch_cordis.py      # ~92 MB from cordis.europa.eu
python src/build_dataset.py
streamlit run app.py
```

The dashboard offers programme, year, organisation-type and city filters, a
searchable project explorer linked to CORDIS project pages, and an optional
table view for every chart.

## Data and licensing

| Source | Coverage | Link |
|---|---|---|
| CORDIS – EU research projects under Horizon Europe | 2021–2027 | [data.europa.eu](https://data.europa.eu/data/datasets/cordis-eu-research-projects-under-horizon-europe-2021-2027) |
| CORDIS – EU research projects under Horizon 2020 | 2014–2020 | [data.europa.eu](https://data.europa.eu/data/datasets/cordish2020projects) |
| Eurostat – population on 1 January by NUTS region (demo_r_d2jan) | Länder populations | [ec.europa.eu/eurostat](https://ec.europa.eu/eurostat/databrowser/product/view/demo_r_d2jan) |
| DFG Förderatlas 2024 – awards by university and by Land | DFG awards 2020–2022 | [foerderatlas.dfg.de](https://foerderatlas.dfg.de/daten/) |
| GeoNames – postal code register (DE) | postcode-to-Land mapping, centroids | [geonames.org](https://download.geonames.org/export/zip/) |

The CORDIS datasets are published by the EU Publications Office; reuse is
permitted under [Commission Decision 2011/833/EU](http://data.europa.eu/eli/dec/2011/833/oj)
with attribution. Eurostat and GeoNames data are reused under CC BY 4.0.
The DFG figures are taken from the published Förderatlas 2024 tables of the
Deutsche Forschungsgemeinschaft and are reproduced with attribution.
The map background uses CARTO basemaps with OpenStreetMap data, attributed
on the map itself. The code and original content of this repository are
licensed under [CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/):
you may use, share and adapt them for non-commercial purposes, including
study and teaching, provided you credit Jeel Swami and link to this
repository. Commercial use requires written permission. The data remains
subject to the terms of its respective providers. Releases are archived on
Zenodo and citable via
[doi.org/10.5281/zenodo.21841052](https://doi.org/10.5281/zenodo.21841052).
`src/fetch_cordis.py` records the retrieval timestamp and the server's
`Last-Modified`/`ETag` headers in `data/raw/PROVENANCE.json`, so every figure
traces to an exact snapshot of the source.

A GitHub Actions workflow ([data-refresh.yml](.github/workflows/data-refresh.yml))
re-runs the pipeline on the 3rd of every month and commits the rebuilt
dataset only when the sources actually changed; the push triggers an
automatic redeployment of the live app.

## Methodology

- **Unit of analysis.** One row is one *participation*: one organisation's
  role in one project. An organisation active in ten projects contributes ten
  rows. Figures aggregate `ecContribution`, the EU's committed financial
  contribution to that participant.
- **Land attribution.** Each row's Eurostat NUTS code is cross-validated
  against the postal code of the registered address, resolved through the
  [GeoNames postal register](https://download.geonames.org/export/zip/)
  (CC BY 4.0). When they agree the NUTS code stands; when they disagree the
  postal code wins, because some CORDIS releases carry corrupted NUTS codes
  and geolocations (the August 2026 release stamped organisations from Köln,
  Jülich and München as Berlin). Coordinates further than ~0.7° from the
  postcode centroid are likewise replaced by that centroid. Rows with
  neither signal fall back to a city-name match; the method used is
  recorded per row, and rows with no usable signal (<1 %) are excluded.
  A validation step (`src/validate_build.py`) additionally blocks any
  automated refresh whose totals move implausibly against the previous
  release.
- **Fields of science.** EuroSciVoc tags classify projects, not
  participations, and a project usually carries several tags. Field totals
  therefore split each participation's contribution equally across its
  project's distinct top-level fields, so they sum to the overall total
  instead of double-counting.
- **DFG comparison.** DFG figures come from the published Förderatlas 2024
  tables (© Deutsche Forschungsgemeinschaft) covering awards 2020–2022; the
  EU side counts contributions committed to projects starting in the same
  window. University hospitals are counted with their university on both
  sides; legally separate affiliated institutes are excluded. Awards and
  commitments are related but distinct measures.

### Limitations

- Contributions are commitments at grant signature, not final payments.
- Multi-site organisations are counted at the address registered for the
  participation, usually the legal seat. DLR's roughly €660 m, for example,
  are credited to Köln although its institutes span Germany.
- Horizon Europe is a running programme; recent start years are incomplete
  by construction and grow with every CORDIS release.

## Repository layout

```
src/fetch_cordis.py       download raw dumps, write provenance record
src/fetch_population.py   fetch Länder populations from the Eurostat API
src/fetch_plz.py          postcode→Land register from GeoNames
src/fetch_dfg.py          DFG Förderatlas 2024 tables (Datawrapper)
src/build_dataset.py      filter, attribute, join; write Parquet
src/validate_build.py     plausibility gate for automated refreshes
app.py                    Streamlit dashboard
.github/workflows/        monthly data refresh
data/raw/                 CORDIS zips + PROVENANCE.json (zips not versioned)
data/reference/           reference data with retrieval metadata
data/processed/           Parquet files + machine-generated build summary
```

## Roadmap

- **Project-level DFG data.** The dashboard compares DFG and EU funding
  using the published Förderatlas 2024 tables; project-level DFG analysis
  waits on GEPRIS offering machine-readable bulk access.
