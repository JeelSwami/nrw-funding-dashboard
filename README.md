# Where does EU research funding flow in North Rhine-Westphalia?

**Live demo: [nrw-funding-dashboard.streamlit.app](https://nrw-funding-dashboard.streamlit.app)**

An interactive dashboard tracing every EU research grant that reached an
organisation in North Rhine-Westphalia (NRW) under Horizon 2020 (2014–2020)
and Horizon Europe (2021–2027), built from the official CORDIS bulk datasets
of the EU Publications Office.

At the August 2026 data snapshot, the two framework programmes committed
**€3.71 billion** to **1,128 NRW organisations** across **5,097 projects** —
**18.6 %** of the €20.0 billion that went to Germany as a whole. Köln leads
the state (helped by DLR's legal seat there), followed by Bonn, Aachen and
Jülich; natural sciences and engineering together account for over half of
the field-attributed funding.

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

The CORDIS datasets are published by the EU Publications Office; reuse is
permitted under [Commission Decision 2011/833/EU](http://data.europa.eu/eli/dec/2011/833/oj)
with attribution. Eurostat data is reused under CC BY 4.0.
`src/fetch_cordis.py` records the retrieval timestamp and the server's
`Last-Modified`/`ETag` headers in `data/raw/PROVENANCE.json`, so every figure
traces to an exact snapshot of the source.

A GitHub Actions workflow ([data-refresh.yml](.github/workflows/data-refresh.yml))
re-runs the pipeline on the 3rd of every month and commits the rebuilt
dataset only when the sources actually changed; the push triggers an
automatic redeployment of the live app.

## Methodology

- **Unit of analysis.** One row is one *participation* — one organisation's
  role in one project. An organisation active in ten projects contributes ten
  rows. Figures aggregate `ecContribution`, the EU's committed financial
  contribution to that participant.
- **Land attribution.** Each row's Eurostat NUTS code is cross-validated
  against the postal code of the registered address, resolved through the
  [GeoNames postal register](https://download.geonames.org/export/zip/)
  (CC BY 4.0). When they agree the NUTS code stands; when they disagree the
  postal code wins — some CORDIS releases carry corrupted NUTS codes and
  geolocations (the August 2026 release stamped organisations from Köln,
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

### Limitations

- Contributions are commitments at grant signature, not final payments.
- Multi-site organisations are counted at the address registered for the
  participation — usually the legal seat. DLR's €600 m, for example, is
  credited to Köln although its institutes span Germany.
- Horizon Europe is a running programme; recent start years are incomplete
  by construction and grow with every CORDIS release.

## Repository layout

```
src/fetch_cordis.py       download raw dumps, write provenance record
src/fetch_population.py   fetch Länder populations from the Eurostat API
src/build_dataset.py      filter, flag NRW, join projects + fields, write Parquet
app.py                    Streamlit dashboard
data/raw/                 CORDIS zips + PROVENANCE.json (zips not versioned)
data/reference/           population figures with retrieval metadata
data/processed/           Parquet files + machine-generated build summary
```

## Roadmap

- **DFG funding (GEPRIS).** The DFG's project database has no
  machine-readable bulk access as of mid-2026; a planned second data source
  is the DFG's published funding tables, which would put national and EU
  funding side by side.
- Collaboration-network view of NRW organisations and their EU partners.
