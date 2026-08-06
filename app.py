"""EU research funding in North Rhine-Westphalia - interactive dashboard.

Data: CORDIS bulk datasets (Horizon 2020 and Horizon Europe), EU Publications
Office. Reuse permitted under Commission Decision 2011/833/EU with attribution.
Build the dataset first:  python src/fetch_cordis.py && python src/build_dataset.py
Run:                      streamlit run app.py
"""

import json
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

DATA = Path(__file__).parent / "data" / "processed"

# Palette: fixed hue per programme (identity), single blue for magnitude.
BLUE = "#2a78d6"
ORANGE = "#eb6834"
PROGRAMME_COLORS = {"Horizon Europe": BLUE, "Horizon 2020": ORANGE}
INK = "#0b0b0b"
INK_2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
SURFACE = "#fcfcfb"
FONT = 'system-ui, -apple-system, "Segoe UI", sans-serif'

st.set_page_config(page_title="EU research funding in NRW",
                   page_icon=":bar_chart:", layout="wide")


@st.cache_data
def load():
    de = pd.read_parquet(DATA / "participations_de.parquet")
    fields = pd.read_parquet(DATA / "fields_nrw.parquet")
    summary = json.loads((DATA / "summary.json").read_text())
    return de, fields, summary


def eur(x: float) -> str:
    if x >= 1e9:
        return f"€{x / 1e9:.2f} bn"
    if x >= 1e6:
        return f"€{x / 1e6:.1f} m"
    return f"€{x / 1e3:.0f} k"


def style(fig: go.Figure, height: int = 380) -> go.Figure:
    fig.update_layout(
        height=height, paper_bgcolor=SURFACE, plot_bgcolor=SURFACE,
        font=dict(family=FONT, color=INK_2, size=13),
        margin=dict(l=8, r=8, t=8, b=8), barcornerradius=4,
        hoverlabel=dict(bgcolor="#ffffff", font=dict(family=FONT, color=INK)),
    )
    fig.update_xaxes(gridcolor=GRID, gridwidth=1, zeroline=False,
                     linecolor="#c3c2b7", tickfont=dict(color=MUTED))
    fig.update_yaxes(gridcolor=GRID, gridwidth=1, zeroline=False,
                     linecolor="#c3c2b7", tickfont=dict(color=MUTED))
    return fig


def ranked_bar(series: pd.Series, height: int = 380) -> go.Figure:
    """Horizontal ranked bar, single hue, value labels at the data ends."""
    s = series.sort_values()
    fig = go.Figure(go.Bar(
        x=s.values, y=s.index.tolist(), orientation="h",
        marker=dict(color=BLUE), text=[eur(v) for v in s.values],
        textposition="outside", textfont=dict(color=INK_2, size=12),
        cliponaxis=False,
        hovertemplate="%{y}<br>%{customdata}<extra></extra>",
        customdata=[eur(v) for v in s.values],
    ))
    # Headroom plus cliponaxis=False so the label on the longest bar can
    # spill into the right margin instead of being cut off.
    fig.update_xaxes(visible=False, range=[0, float(s.max()) * 1.18])
    fig.update_yaxes(showgrid=False)
    fig.update_layout(bargap=0.35)
    styled = style(fig, height)
    styled.update_layout(margin=dict(l=8, r=56, t=8, b=8))
    return styled


GERMAN_STOPWORDS = {"ZU", "ZUR", "ZUM", "DER", "DIE", "DAS", "UND", "FUR",
                    "FUER", "VON", "AN", "IM"}
CASING_EXCEPTIONS = {"GMBH": "GmbH", "EV": "e.V.", "E.V.": "e.V."}


def _case_word(w: str) -> str:
    if w in CASING_EXCEPTIONS:
        return CASING_EXCEPTIONS[w]
    if w in GERMAN_STOPWORDS:
        return w.lower()
    # Acronym heuristic: short or vowel-free tokens (DLR, UKB, RWTH, FZJ).
    if len(w) <= 3 or not any(v in w for v in "AEIOUY"):
        return w
    return w.capitalize()


def org_display(label: str, max_len: int = 36) -> str:
    """Readable casing for registry names, keeping acronyms intact."""
    if not isinstance(label, str):
        return ""
    if len(label) > 8 and label.isupper():
        label = " ".join(
            "-".join(_case_word(p) for p in w.split("-"))
            for w in label.split())
    if len(label) > max_len:
        label = label[:max_len - 1].rstrip() + "…"
    return label


de, fields, summary = load()
nrw_all = de[de["is_nrw"]]

st.title("Where does EU research funding flow in North Rhine-Westphalia?")
snapshot = summary["provenance"].get("HORIZON", {}).get("last_modified", "")
st.caption(
    "Source: CORDIS bulk datasets (Horizon 2020 & Horizon Europe), "
    "EU Publications Office · reuse under Commission Decision 2011/833/EU · "
    f"data snapshot: {snapshot or 'see data/raw/PROVENANCE.json'}"
)

# --- Filter row -------------------------------------------------------------
years = nrw_all["start_year"].dropna().astype(int)
f1, f2, f3, f4 = st.columns([1.3, 1.3, 1.6, 1.2])
with f1:
    programmes = st.multiselect("Programme", list(PROGRAMME_COLORS),
                                default=list(PROGRAMME_COLORS))
with f2:
    year_range = st.slider("Project start year", int(years.min()),
                           int(years.max()),
                           (int(years.min()), int(years.max())))
with f3:
    activities = st.multiselect(
        "Organisation type", sorted(nrw_all["activity_label"].unique()),
        default=[])
with f4:
    city_options = (nrw_all.groupby("city_display")["ecContribution"].sum()
                    .sort_values(ascending=False).index.tolist())
    city = st.selectbox("City", ["All of NRW"] + city_options)

def apply_filters(df: pd.DataFrame, with_city: bool = True) -> pd.DataFrame:
    out = df[df["programme"].isin(programmes or list(PROGRAMME_COLORS))]
    out = out[out["start_year"].between(*year_range)]
    if activities:
        out = out[out["activity_label"].isin(activities)]
    if with_city and city != "All of NRW":
        out = out[out["city_display"] == city]
    return out

nrw = apply_filters(nrw_all)
de_filtered = apply_filters(de, with_city=False)
nrw_no_city = apply_filters(nrw_all, with_city=False)

# --- KPI row ----------------------------------------------------------------
k1, k2, k3, k4 = st.columns(4)
k1.metric("EU contribution", eur(nrw["ecContribution"].sum()),
          help="Sum of the EU's committed contribution (ecContribution) to "
               "the selected NRW participations.")
k2.metric("Projects", f"{nrw['projectID'].nunique():,}")
k3.metric("Organisations", f"{nrw['organisationID'].nunique():,}")
if city == "All of NRW":
    denom = de_filtered["ecContribution"].sum()
    share = nrw["ecContribution"].sum() / denom if denom else 0
    k4.metric("Share of German total", f"{share:.1%}",
              help="NRW's share of the EU contribution to all German "
                   "participations under the same programme, year and "
                   "organisation-type filters.")
else:
    denom = nrw_no_city["ecContribution"].sum()
    share = nrw["ecContribution"].sum() / denom if denom else 0
    k4.metric(f"Share of NRW total", f"{share:.1%}",
              help=f"{city}'s share of the EU contribution to all NRW "
                   "participations under the current filters.")

show_tables = st.toggle("Show chart data as tables", value=False)

# --- Funding over time ------------------------------------------------------
st.subheader("EU contribution by project start year")
by_year = (nrw.groupby(["start_year", "programme"])["ecContribution"].sum()
           .div(1e6).reset_index())
fig = go.Figure()
for prog in PROGRAMME_COLORS:  # fixed order and hue per programme
    sub = by_year[by_year["programme"] == prog]
    if len(sub):
        fig.add_bar(x=sub["start_year"], y=sub["ecContribution"], name=prog,
                    marker=dict(color=PROGRAMME_COLORS[prog]),
                    hovertemplate=(f"{prog}, %{{x:.0f}}<br>"
                                   "€%{y:.1f} m<extra></extra>"))
fig.update_layout(barmode="stack", bargap=0.3,
                  legend=dict(orientation="h", y=1.08, font=dict(color=INK_2)))
fig.update_yaxes(title_text="EU contribution (€ million)",
                 title_font=dict(color=MUTED))
fig.update_xaxes(showgrid=False, dtick=1)
st.plotly_chart(style(fig, 340), config={"displayModeBar": False})
if show_tables:
    st.dataframe(by_year.rename(columns={"ecContribution": "EUR million"}),
                 hide_index=True)

# --- Two-column: organisations and cities -----------------------------------
c1, c2 = st.columns(2)
with c1:
    st.subheader("Top recipient organisations")
    top_orgs = (nrw.groupby("org_label")["ecContribution"].sum()
                .sort_values(ascending=False).head(15))
    top_orgs.index = [org_display(i) for i in top_orgs.index]
    st.plotly_chart(ranked_bar(top_orgs, 460),
                    config={"displayModeBar": False})
    if show_tables:
        st.dataframe(top_orgs.rename("EUR").map(eur))
with c2:
    st.subheader("Funding by city")
    top_cities = (nrw_no_city.groupby("city_display")["ecContribution"].sum()
                  .sort_values(ascending=False).head(15))
    st.plotly_chart(ranked_bar(top_cities, 460),
                    config={"displayModeBar": False})
    if show_tables:
        st.dataframe(top_cities.rename("EUR").map(eur))

# --- Two-column: fields and organisation types ------------------------------
c3, c4 = st.columns(2)
with c3:
    st.subheader("Funding by field of science")
    f = fields[fields["programme"].isin(programmes or list(PROGRAMME_COLORS))]
    f = f[f["start_year"].between(*year_range)]
    if city != "All of NRW":
        f = f[f["city_display"] == city]
    by_field = (f.groupby("field_l1")["ec_frac"].sum()
                .sort_values(ascending=False).head(8))
    by_field.index = [i.capitalize() for i in by_field.index]
    st.plotly_chart(ranked_bar(by_field, 380),
                    config={"displayModeBar": False})
    st.caption("EuroSciVoc top-level fields. A project's funding is split "
               "equally across its fields, so totals are not double-counted. "
               "Organisation-type filter does not apply here.")
    if show_tables:
        st.dataframe(by_field.rename("EUR").map(eur))
with c4:
    st.subheader("Funding by organisation type")
    by_type = (nrw.groupby("activity_label")["ecContribution"].sum()
               .sort_values(ascending=False))
    st.plotly_chart(ranked_bar(by_type, 380),
                    config={"displayModeBar": False})
    if show_tables:
        st.dataframe(by_type.rename("EUR").map(eur))

# --- Project explorer -------------------------------------------------------
st.subheader("Project explorer")
query = st.text_input("Search projects (title, acronym or organisation)",
                      placeholder="e.g. quantum, battery, RWTH ...")
table = nrw.copy()
if query:
    q = query.strip().lower()
    mask = (table["title"].str.lower().str.contains(q, na=False)
            | table["acronym"].str.lower().str.contains(q, na=False)
            | table["name"].str.lower().str.contains(q, na=False)
            | table["org_label"].str.lower().str.contains(q, na=False))
    table = table[mask]
table = (table.sort_values("ecContribution", ascending=False)
         [["acronym", "title", "org_label", "city_display", "programme",
           "start_year", "role", "ecContribution", "projectID"]]
         .head(500))
table["cordis"] = "https://cordis.europa.eu/project/id/" + table["projectID"]
st.dataframe(
    table.rename(columns={
        "acronym": "Acronym", "title": "Title", "org_label": "Organisation",
        "city_display": "City", "programme": "Programme",
        "start_year": "Start", "role": "Role",
        "ecContribution": "EU contribution (€)", "cordis": "CORDIS",
    }).drop(columns=["projectID"]),
    hide_index=True, height=420,
    column_config={
        "EU contribution (€)": st.column_config.NumberColumn(format="localized"),
        "Start": st.column_config.NumberColumn(format="%d"),
        "CORDIS": st.column_config.LinkColumn(display_text="open"),
    },
)
st.caption(f"{len(table):,} participations shown (largest first, capped at "
           "500). Each row is one organisation's participation in one project.")

# --- Methodology ------------------------------------------------------------
with st.expander("Methodology, sources and limitations"):
    s = summary
    st.markdown(f"""
**Sources.** [CORDIS - EU research projects under Horizon Europe (2021-2027)](https://data.europa.eu/data/datasets/cordis-eu-research-projects-under-horizon-europe-2021-2027)
and [under Horizon 2020 (2014-2020)](https://data.europa.eu/data/datasets/cordish2020projects),
published by the EU Publications Office. Reuse is permitted under
[Commission Decision 2011/833/EU](http://data.europa.eu/eli/dec/2011/833/oj)
with attribution. Retrieval details are recorded in `data/raw/PROVENANCE.json`.

**Unit of analysis.** One row is one *participation* - one organisation's role
in one project. Figures aggregate the EU's committed contribution
(`ecContribution`) per participation; grants signed but later reduced or
terminated are counted at their recorded value.

**NRW identification.** Primary criterion: Eurostat NUTS code beginning with
`DEA` (North Rhine-Westphalia). Fallback for rows without a NUTS code:
city-name match against NRW municipalities
({s['nrw_matched_by_city_fallback']} of {s['nrw_participations']:,} NRW rows).
{s['german_rows_missing_nuts_unmatched']} German rows
(<0.5 %) had neither a NUTS code nor a matchable city and are excluded from
NRW figures.

**Field attribution.** EuroSciVoc classifies projects, not participations, and
projects carry several field tags. Funding per field splits each
participation's contribution equally across its project's distinct top-level
fields, so field totals sum to the overall total.

**Limitations.** Contributions are commitments, not final payments; multi-site
organisations are attributed to the address registered for the participation;
Horizon Europe data grows with each CORDIS release, so recent years are
incomplete by construction ({snapshot or "see provenance file"}).
""")
