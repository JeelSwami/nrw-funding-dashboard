"""EU research funding in North Rhine-Westphalia - interactive dashboard.

Data: CORDIS bulk datasets (Horizon 2020 and Horizon Europe), EU Publications
Office. Reuse permitted under Commission Decision 2011/833/EU with attribution.
Build the dataset first:  python src/fetch_cordis.py && python src/build_dataset.py
Run:                      streamlit run app.py
"""

import json
import math
from pathlib import Path

import networkx as nx
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

st.set_page_config(
    page_title="EU research funding flow in North Rhine-Westphalia",
    page_icon=":bar_chart:", layout="wide")


def _fingerprint(*paths):
    """Cache key tied to the data files, so a data update after a hot code
    reload can never serve a stale cached frame."""
    return tuple((p.name, p.stat().st_mtime_ns) for p in paths if p.exists())


@st.cache_data
def load(fingerprint):
    de = pd.read_parquet(DATA / "participations_de.parquet")
    fields = pd.read_parquet(DATA / "fields_nrw.parquet")
    collab = pd.read_parquet(DATA / "collab_edges.parquet")
    summary = json.loads((DATA / "summary.json").read_text())
    return de, fields, collab, summary


@st.cache_data
def load_population(fingerprint):
    return json.loads(
        (DATA.parent / "reference" / "population_nuts1.json").read_text())


@st.cache_data
def load_dfg(fingerprint):
    return json.loads(
        (DATA.parent / "reference" / "dfg_foerderatlas.json").read_text())


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


REPO_URL = "https://github.com/JeelSwami/nrw-funding-dashboard"
APP_URL = "https://nrw-funding-dashboard.streamlit.app"

de, fields, collab, summary = load(_fingerprint(
    DATA / "participations_de.parquet", DATA / "fields_nrw.parquet",
    DATA / "collab_edges.parquet", DATA / "summary.json"))
nrw_all = de[de["is_nrw"]]

st.title("EU research funding flow in North Rhine-Westphalia, Germany")
snapshot = summary["provenance"].get("HORIZON", {}).get("last_modified", "")

with st.sidebar:
    st.markdown("### About")
    st.markdown(
        "Built and maintained by **Jeel Swami**.\n\n"
        "This dashboard traces the EU's committed research funding to "
        "organisations in North Rhine-Westphalia under Horizon 2020 and "
        "Horizon Europe, from the official CORDIS bulk datasets. Methodology, "
        "sources and limitations are documented at the bottom of the page.\n\n"
        f"[Source code & data pipeline]({REPO_URL})"
    )
    st.caption(f"Data snapshot: {snapshot or 'see data/raw/PROVENANCE.json'}")
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

# --- Map --------------------------------------------------------------------
st.subheader("Where the money lands")
geo = nrw[nrw["lat"].notna() & nrw["lon"].notna()]
if len(geo):
    pts = (geo.groupby("organisationID")
           .agg(org_label=("org_label", "first"),
                city=("city_display", "first"),
                lat=("lat", "first"), lon=("lon", "first"),
                ec=("ecContribution", "sum"))
           .reset_index())
    pts = pts[pts["ec"] > 0]
    map_fig = go.Figure(go.Scattermap(
        lat=pts["lat"], lon=pts["lon"], mode="markers",
        marker=dict(size=pts["ec"], sizemode="area",
                    sizeref=2.0 * float(pts["ec"].max()) / (44 ** 2),
                    sizemin=4, color=BLUE, opacity=0.7),
        text=[f"{org_display(o)} · {c}<br>{eur(v)}"
              for o, c, v in zip(pts["org_label"], pts["city"], pts["ec"])],
        hovertemplate="%{text}<extra></extra>",
    ))
    map_fig.update_layout(
        map=dict(style="carto-positron",
                 center=dict(lat=51.35, lon=7.45), zoom=6.8),
        height=460, paper_bgcolor=SURFACE,
        margin=dict(l=8, r=8, t=8, b=8),
        font=dict(family=FONT, color=INK_2),
        hoverlabel=dict(bgcolor="#ffffff", font=dict(family=FONT, color=INK)),
    )
    st.plotly_chart(map_fig, config={"displayModeBar": False})
    n_missing = int(nrw["organisationID"].nunique() - pts["organisationID"].nunique())
    st.caption("Marker area is proportional to the EU contribution received "
               "at that registered address. "
               f"{len(pts):,} organisations shown; {n_missing:,} without "
               "usable coordinates in CORDIS are omitted here (they remain in "
               "all other figures).")

# --- Laender benchmark ------------------------------------------------------
st.subheader("How does NRW compare? EU funding per inhabitant, by Land")
LAENDER = {
    "DE1": "Baden-Württemberg", "DE2": "Bayern", "DE3": "Berlin",
    "DE4": "Brandenburg", "DE5": "Bremen", "DE6": "Hamburg", "DE7": "Hessen",
    "DE8": "Mecklenburg-Vorpommern", "DE9": "Niedersachsen",
    "DEA": "Nordrhein-Westfalen", "DEB": "Rheinland-Pfalz", "DEC": "Saarland",
    "DED": "Sachsen", "DEE": "Sachsen-Anhalt", "DEF": "Schleswig-Holstein",
    "DEG": "Thüringen",
}
popref = load_population(_fingerprint(
    DATA.parent / "reference" / "population_nuts1.json"))
# The `land` column is the pipeline's cross-validated attribution (NUTS
# checked against the registered address's postcode; see methodology).
bench = de_filtered[de_filtered["land"].isin(LAENDER)]
rows = (bench.groupby("land")["ecContribution"].sum().rename("total")
        .reset_index())
rows["name"] = rows["land"].map(LAENDER)
rows["pop"] = rows["land"].map(popref["population"])
rows["percap"] = rows["total"] / rows["pop"]
rows = rows.sort_values("percap")
bench_fig = go.Figure(go.Bar(
    x=rows["percap"], y=rows["name"], orientation="h",
    marker=dict(color=[BLUE if l == "DEA" else "#c3c2b7"
                       for l in rows["land"]]),
    cliponaxis=False, text=[f"€{v:,.0f}" for v in rows["percap"]],
    textposition="outside", textfont=dict(color=INK_2, size=12),
    customdata=[(eur(t), f"{p / 1e6:.1f} m")
                for t, p in zip(rows["total"], rows["pop"])],
    hovertemplate=("%{y}<br>€%{x:,.0f} per inhabitant<br>"
                   "total %{customdata[0]} · population %{customdata[1]}"
                   "<extra></extra>"),
))
bench_fig.update_xaxes(visible=False,
                       range=[0, float(rows["percap"].max()) * 1.18])
bench_fig.update_yaxes(showgrid=False)
bench_fig.update_layout(bargap=0.35)
bench_fig = style(bench_fig, 480)
bench_fig.update_layout(margin=dict(l=8, r=56, t=8, b=8))
st.plotly_chart(bench_fig, config={"displayModeBar": False})
pop_year = sorted(set(popref["reference_year"].values()))[-1]
st.caption(
    "EU contribution over the selected period divided by the Land's "
    f"population on 1 January {pop_year} (Eurostat, demo_r_d2jan). "
    "Nordrhein-Westfalen is highlighted. Small Länder that host large "
    "organisations' legal seats (e.g. Bremen) rank high because funding "
    "counts at the registered address. The city filter does not apply here.")

# --- DFG comparison ---------------------------------------------------------
st.subheader("DFG and EU funding side by side")
dfg = load_dfg(_fingerprint(DATA.parent / "reference" / "dfg_foerderatlas.json"))

# Same reporting window as the Foerderatlas: projects starting 2020-2022.
window = de[de["start_year"].between(2020, 2022)]
dfg_nrw = dfg["laender_meur"]["Nordrhein-Westfalen"]
dfg_share = dfg_nrw / sum(dfg["laender_meur"].values())
eu_de_window = window["ecContribution"].sum()
eu_share = (window.loc[window["is_nrw"], "ecContribution"].sum()
            / eu_de_window if eu_de_window else 0)
c_dfg1, c_dfg2, c_dfg3 = st.columns(3)
c_dfg1.metric("DFG awards to NRW, 2020–2022", f"€{dfg_nrw / 1e3:.2f} bn",
              help="DFG Förderatlas 2024, all NRW institutions.")
c_dfg2.metric("NRW share of DFG awards", f"{dfg_share:.1%}",
              help="Share of DFG awards 2020–2022 across the 16 Länder.")
c_dfg3.metric("NRW share of EU funding, same window", f"{eu_share:.1%}",
              help="Share of EU contributions to German participants in "
                   "projects starting 2020–2022.")

# University-level pairing. EU-side groups add the university hospital to
# its university, since the DFG figures include the medical faculties.
UNI_GROUPS = {
    "Aachen TH": ("RWTH Aachen",
                  ["rheinisch-westfalische technische hochschule",
                   "rwth aachen", "universitatsklinikum aachen"]),
    "Bonn U": ("Uni Bonn", ["friedrich-wilhelms-universitat bonn",
                            "universitatsklinikum bonn"]),
    "Köln U": ("Uni Köln", ["universitat zu koln"]),
    "Münster U": ("Uni Münster", ["universitat munster",
                                  "universitatsklinikum munster"]),
    "Bochum U": ("RU Bochum", ["ruhr-universitat bochum"]),
    "Duisburg-Essen U": ("Uni Duisburg-Essen",
                         ["duisburg-essen", "universitatsklinikum essen"]),
    "Düsseldorf U": ("Uni Düsseldorf", ["heinrich-heine",
                                        "universitatsklinikum dusseldorf"]),
    "Dortmund TU": ("TU Dortmund", ["technische universitat dortmund"]),
    "Bielefeld U": ("Uni Bielefeld", ["universitat bielefeld"]),
}


def _fold(s: str) -> str:
    import unicodedata
    s = unicodedata.normalize("NFKD", (s or "").lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    for a, b in (("ae", "a"), ("oe", "o"), ("ue", "u"), ("ss", "s")):
        s = s.replace(a, b)
    return s


nrw_window = window[window["is_nrw"]].copy()
folded = nrw_window["name"].map(_fold)
# Legally separate affiliated institutes ("... an der Universitaet X") are
# not part of the university in the DFG figures either.
not_affiliate = ~folded.str.contains(" an der ", regex=False)
rows_dfg = []
for dfg_name, (display, patterns) in UNI_GROUPS.items():
    mask = (folded.str.contains("|".join(_fold(p) for p in patterns),
                                regex=True) & not_affiliate)
    rows_dfg.append({
        "uni": display,
        "DFG": dfg["universities_meur"].get(dfg_name, 0.0),
        "EU": nrw_window.loc[mask, "ecContribution"].sum() / 1e6,
    })
cmp_df = pd.DataFrame(rows_dfg).sort_values("DFG")
dfg_fig = go.Figure()
dfg_fig.add_bar(y=cmp_df["uni"], x=cmp_df["DFG"], orientation="h",
                name="DFG awards 2020–2022", marker=dict(color="#1baf7a"),
                text=[f"€{v:,.0f} m" for v in cmp_df["DFG"]],
                textposition="outside", textfont=dict(size=11),
                cliponaxis=False,
                hovertemplate="%{y}<br>DFG: €%{x:,.1f} m<extra></extra>")
dfg_fig.add_bar(y=cmp_df["uni"], x=cmp_df["EU"], orientation="h",
                name="EU contribution, projects starting 2020–2022",
                marker=dict(color=BLUE),
                text=[f"€{v:,.0f} m" for v in cmp_df["EU"]],
                textposition="outside", textfont=dict(size=11),
                cliponaxis=False,
                hovertemplate="%{y}<br>EU: €%{x:,.1f} m<extra></extra>")
dfg_fig.update_layout(barmode="group", bargap=0.25,
                      legend=dict(orientation="h", y=1.08,
                                  font=dict(color=INK_2)))
dfg_fig.update_xaxes(visible=False,
                     range=[0, float(cmp_df["DFG"].max()) * 1.18])
dfg_fig.update_yaxes(showgrid=False)
dfg_fig = style(dfg_fig, 500)
dfg_fig.update_layout(margin=dict(l=8, r=64, t=8, b=8))
st.plotly_chart(dfg_fig, config={"displayModeBar": False})
st.caption(
    "NRW universities in the DFG Förderatlas top 40, matched to their EU "
    "funding over the same 2020–2022 window (university hospitals counted "
    "with their university on both sides). The Förderatlas appears every "
    "three years; the 2024 edition, the most recent, reports 2020–2022. "
    "DFG figures are awards "
    "(Bewilligungen); EU figures are committed contributions for projects "
    "starting in the window; the two are related but not identical concepts. "
    "© Deutsche Forschungsgemeinschaft, Förderatlas 2024. The filter row "
    "does not apply here.")
if show_tables:
    st.dataframe(cmp_df.sort_values("DFG", ascending=False)
                 .rename(columns={"uni": "University",
                                  "DFG": "DFG 2020–22 (€ m)",
                                  "EU": "EU 2020–22 (€ m)"})
                 .round(1), hide_index=True)

# --- Collaboration network --------------------------------------------------
st.subheader("Who does NRW collaborate with?")
top_nrw = (collab.drop_duplicates("nrw_org_id")
           .sort_values("nrw_org_ec", ascending=False))
disp_to_raw = {org_display(o): o for o in top_nrw["nrw_org"]}
focus = st.selectbox(
    "Focus", ["Overview: top NRW organisations"]
    + [org_display(o) for o in top_nrw["nrw_org"].head(25)],
    label_visibility="collapsed")
if focus.startswith("Overview"):
    hubs = set(top_nrw["nrw_org_id"].head(10))
    ev = (collab[collab["nrw_org_id"].isin(hubs)]
          .sort_values("joint_projects", ascending=False)
          .groupby("nrw_org_id").head(6))
else:
    ev = collab[collab["nrw_org"] == disp_to_raw[focus]]
    hubs = set(ev["nrw_org_id"])

G = nx.Graph()
for r in ev.itertuples():
    G.add_node(r.nrw_org_id, label=org_display(r.nrw_org), kind="nrw")
    if r.partner_id not in G or G.nodes[r.partner_id].get("kind") != "nrw":
        kind = ("nrw" if r.partner_is_nrw
                else "de" if r.partner_country == "DE" else "intl")
        G.add_node(r.partner_id, label=org_display(r.partner), kind=kind)
    G.add_edge(r.nrw_org_id, r.partner_id, weight=int(r.joint_projects))

# Layout on topology alone: raw joint-project weights (up to >100) would
# collapse the strongest partners into an unreadable core.
pos = nx.spring_layout(G, seed=42, k=2.0 / math.sqrt(max(len(G), 2)),
                       iterations=200, weight=None)
net = go.Figure()
for a, b, d in G.edges(data=True):
    net.add_trace(go.Scatter(
        x=[pos[a][0], pos[b][0]], y=[pos[a][1], pos[b][1]], mode="lines",
        line=dict(width=min(1 + math.log2(d["weight"]), 6), color=GRID),
        hoverinfo="skip", showlegend=False))
KIND_STYLE = {"nrw": (BLUE, "NRW"), "de": ("#c3c2b7", "Germany (other)"),
              "intl": (ORANGE, "International")}
strength = {n: sum(d["weight"] for _, _, d in G.edges(n, data=True))
            for n in G}
for kind, (color, name) in KIND_STYLE.items():
    nodes = [n for n in G if G.nodes[n]["kind"] == kind]
    if not nodes:
        continue
    net.add_trace(go.Scatter(
        x=[pos[n][0] for n in nodes], y=[pos[n][1] for n in nodes],
        mode="markers", name=name,
        marker=dict(color=color,
                    size=[min(9 + 1.6 * math.sqrt(strength[n]), 34)
                          for n in nodes],
                    line=dict(width=2, color=SURFACE)),
        text=[f"{G.nodes[n]['label']}<br>{strength[n]} joint projects"
              for n in nodes],
        hovertemplate="%{text}<extra></extra>"))
label_nodes = list(G) if len(G) <= 20 else list(hubs)
for n in label_nodes:
    net.add_annotation(x=pos[n][0], y=pos[n][1], text=G.nodes[n]["label"],
                       showarrow=False, yshift=14,
                       font=dict(family=FONT, size=11, color=INK_2))
net.update_xaxes(visible=False)
net.update_yaxes(visible=False)
net.update_layout(legend=dict(orientation="h", y=1.06,
                              font=dict(color=INK_2)))
st.plotly_chart(style(net, 560), config={"displayModeBar": False})
st.caption(
    "Organisations connected by joint project participation; line width "
    "scales with the number of shared projects. The overview shows the ten "
    "largest NRW recipients with their six strongest partners each; choose "
    "an organisation above to see its fifteen strongest partnerships. Based "
    "on all years and both programmes; the filter row does not apply.")
if show_tables:
    st.dataframe(ev[["nrw_org", "partner", "partner_country",
                     "joint_projects"]]
                 .rename(columns={"nrw_org": "NRW organisation",
                                  "partner": "Partner",
                                  "partner_country": "Country",
                                  "joint_projects": "Joint projects"}),
                 hide_index=True)

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

# --- Data & citation --------------------------------------------------------
st.subheader("Data & citation")
export = (nrw[["programme", "projectID", "acronym", "title", "name",
               "city_display", "activity_label", "role", "start_year",
               "ecContribution", "netEcContribution", "nutsCode", "land",
               "land_method"]]
          .rename(columns={"city_display": "city",
                           "activity_label": "organisation_type"}))
d1, d2 = st.columns([1, 2])
with d1:
    st.download_button(
        "Download filtered data (CSV)",
        data=export.to_csv(index=False).encode("utf-8"),
        file_name="nrw_eu_funding_filtered.csv", mime="text/csv",
        help="The NRW participations matching the current filters, "
             "one row per organisation per project.")
    st.caption(f"{len(export):,} rows under the current filters.")
with d2:
    snap_short = " ".join(snapshot.split()[1:4]) if snapshot else "latest"
    st.code(
        "Swami, J. (2026). EU research funding flow in\n"
        "North Rhine-Westphalia, Germany. Interactive dashboard.\n"
        f"Data: CORDIS, EU Publications Office (snapshot {snap_short}).\n"
        "https://doi.org/10.5281/zenodo.21841052\n"
        f"{APP_URL}", language=None)

# --- Methodology ------------------------------------------------------------
with st.expander("Methodology, sources and limitations"):
    s = summary
    st.markdown(f"""
**Sources.** [CORDIS - EU research projects under Horizon Europe (2021-2027)](https://data.europa.eu/data/datasets/cordis-eu-research-projects-under-horizon-europe-2021-2027)
and [under Horizon 2020 (2014-2020)](https://data.europa.eu/data/datasets/cordish2020projects),
published by the EU Publications Office. Reuse is permitted under
[Commission Decision 2011/833/EU](http://data.europa.eu/eli/dec/2011/833/oj)
with attribution. Retrieval details are recorded in `data/raw/PROVENANCE.json`.

**Unit of analysis.** One row is one *participation*: one organisation's role
in one project. Figures aggregate the EU's committed contribution
(`ecContribution`) per participation; grants signed but later reduced or
terminated are counted at their recorded value. Throughout the dashboard,
*bn* denotes the English billion, 10⁹ (German: Milliarde).

**Land attribution.** Each participation's Eurostat NUTS code is
cross-validated against the postal code of its registered address, resolved
through the [GeoNames postal register](https://download.geonames.org/export/zip/)
(CC BY 4.0). When both agree the NUTS code stands; when they disagree the
postal code wins, because it is part of the organisation's own registered
address. Some CORDIS releases carry corrupted NUTS codes (the August 2026
release stamped organisations from Köln, Jülich and München with the Berlin
code `DE300`). In this build, {s.get('land_nuts_plz_conflicts', 0):,} of
{s['german_participations']:,} German rows had such a conflict, of which
{s.get('nrw_recovered_from_nuts_conflicts', 0):,} resolved to NRW. Rows with
neither signal fall back to a city-name match
({s['nrw_matched_by_city_fallback']} rows);
{s.get('german_rows_without_land', 0)} German rows with no usable signal are
excluded. The same releases move geolocations, so map coordinates further
than ~0.7° from their postcode's centroid are replaced by that centroid
({s.get('coords_repaired', 0):,} rows). The per-Land comparison uses this
corrected attribution throughout.

**Field attribution.** EuroSciVoc classifies projects, not participations, and
projects carry several field tags. Funding per field splits each
participation's contribution equally across its project's distinct top-level
fields, so field totals sum to the overall total.

**DFG comparison.** DFG figures come from the published Förderatlas 2024
tables ([per university](https://foerderatlas.dfg.de/daten/dfg-bewilligungen-fuer-2020-bis-2022-nach-hochschulen-und-fachgebieten/),
[per Land](https://foerderatlas.dfg.de/daten/dfg-bewilligungen-fuer-2020-bis-2022-nach-bundeslaendern-und-wissenschaftsbereichen/);
© Deutsche Forschungsgemeinschaft), covering awards made 2020–2022; the
university table lists the 40 universities with the highest awards. EU
figures for the comparison are contributions committed to projects starting
2020–2022. On both sides a university group includes its university
hospital; legally separate affiliated institutes are excluded. Awards and
commitments are related but distinct measures, and the DFG funds
individuals and infrastructure in ways the EU does not; the comparison
shows orders of magnitude and shares, not a like-for-like ledger.

**Per-inhabitant comparison.** Population figures come from Eurostat,
dataset [demo_r_d2jan](https://ec.europa.eu/eurostat/databrowser/product/view/demo_r_d2jan)
(population on 1 January, NUTS-1), reused under CC BY 4.0; retrieval details
are stored in `data/reference/population_nuts1.json`. Funding is aggregated
over the selected period and divided by a single reference-year population,
so the ratio is a normalisation, not a time series.

**Limitations.** Contributions are commitments, not final payments; multi-site
organisations are attributed to the address registered for the participation;
Horizon Europe data grows with each CORDIS release, so recent years are
incomplete by construction ({snapshot or "see provenance file"}).
""")
