# Where does EU research funding flow in North Rhine-Westphalia?

**Live demo: [nrw-funding-dashboard.streamlit.app](https://nrw-funding-dashboard.streamlit.app)**

An interactive dashboard tracing every EU research grant that reached an
organisation in North Rhine-Westphalia (NRW) under Horizon 2020 (2014–2020)
and Horizon Europe (2021–2027), built from the official CORDIS bulk datasets
of the EU Publications Office.

At the July 2026 data snapshot, the two framework programmes committed
**€3.54 billion** to **1,104 NRW organisations** across **4,969 projects** —
**17.8 %** of the €19.9 billion that went to Germany as a whole. Köln leads
the state (€1.05 bn, helped by DLR's legal seat there), followed by Bonn,
Aachen and Jülich; natural sciences and engineering together account for
over half of the field-attributed funding.

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

Both datasets are published by the EU Publications Office; reuse is permitted
under [Commission Decision 2011/833/EU](http://data.europa.eu/eli/dec/2011/833/oj)
with attribution. `src/fetch_cordis.py` records the retrieval timestamp and
the server's `Last-Modified`/`ETag` headers in `data/raw/PROVENANCE.json`, so
every figure traces to an exact snapshot of the source (currently
21 July 2026).

## Methodology

- **Unit of analysis.** One row is one *participation* — one organisation's
  role in one project. An organisation active in ten projects contributes ten
  rows. Figures aggregate `ecContribution`, the EU's committed financial
  contribution to that participant.
- **NRW identification.** Primary criterion is the Eurostat NUTS code:
  every code beginning with `DEA` lies in NRW. Rows without a NUTS code
  (<1 % of German rows) fall back to a city-name match against NRW
  municipalities; the method used is recorded per row. 167 German rows with
  neither a NUTS code nor a matchable city (<0.5 %) are excluded from NRW
  figures.
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
src/fetch_cordis.py     download raw dumps, write provenance record
src/build_dataset.py    filter, flag NRW, join projects + fields, write Parquet
app.py                  Streamlit dashboard
data/raw/               CORDIS zips + PROVENANCE.json (zips not versioned)
data/processed/         Parquet files + machine-generated build summary
```

## Roadmap

- **DFG funding (GEPRIS).** The DFG's project database has no
  machine-readable bulk access as of mid-2026; a planned second data source
  is the DFG's published funding tables, which would put national and EU
  funding side by side.
- Per-capita and per-researcher normalisation of city totals.
- Collaboration-network view of NRW organisations and their EU partners.
