"""Build the analysis dataset from the raw CORDIS dumps.

Reads the official CORDIS zip archives in data/raw/ (see fetch_cordis.py),
filters to organisations in Germany, flags North Rhine-Westphalia (NRW), joins
project metadata and EuroSciVoc science fields, and writes compact Parquet
files plus a machine-generated summary of the build to data/processed/.

Methodology (also documented in README.md):

* Unit of analysis: one row = one *participation* (one organisation's role in
  one project). An organisation appearing in ten projects contributes ten rows.
* Land attribution: the NUTS code is cross-validated against the postal code
  of the registered address, resolved through the GeoNames postal register
  (see fetch_plz.py). When both agree, the NUTS code stands; when they
  disagree — some CORDIS releases stamp organisations from Cologne, Juelich,
  Munich and elsewhere as Berlin/DE300 — the postal code wins, because it is
  part of the organisation's own registered address. Rows with neither
  signal fall back to a city-name match against NRW municipalities. The
  method is recorded per row ("nuts", "plz", "city").
* Coordinates: CORDIS geolocations are replaced by the postcode centroid
  when they sit further than ~0.7 degrees from it (the same releases that
  corrupt NUTS codes also move geolocations), and filled from the centroid
  when missing.
* Funding metric: `ecContribution` — the EU's committed financial contribution
  to that participant. `netEcContribution` is retained as a column.
* Science fields: EuroSciVoc tags exist per project, not per participation,
  and a project usually carries several tags. Funding attributed to a field is
  therefore computed *fractionally*: each participation's contribution is
  split equally across the project's distinct top-level fields, so field
  totals sum to the overall total instead of double-counting.

Usage:
    python src/build_dataset.py
"""

from __future__ import annotations

import json
import sys
import unicodedata
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "processed"

ARCHIVES = {
    "Horizon Europe": "cordis-HORIZONprojects-csv.zip",
    "Horizon 2020": "cordis-h2020projects-csv.zip",
}

ORG_COLS = [
    "projectID", "organisationID", "name", "shortName", "SME", "activityType",
    "postCode", "city", "country", "nutsCode", "geolocation", "role",
    "ecContribution", "netEcContribution",
]
PROJECT_COLS = [
    "id", "acronym", "status", "title", "startDate", "endDate",
    "ecMaxContribution", "fundingScheme",
]

ACTIVITY_LABELS = {
    "HES": "Higher education",
    "REC": "Research organisation",
    "PRC": "Private company",
    "PUB": "Public body",
    "OTH": "Other",
}

# Canonical display names for cities that appear in CORDIS in ASCII-folded or
# variant spellings. Keys are normalised forms (see normalise_city).
CITY_DISPLAY = {
    "koln": "Köln", "cologne": "Köln", "dusseldorf": "Düsseldorf",
    "munster": "Münster", "julich": "Jülich", "monchengladbach":
    "Mönchengladbach", "hurth": "Hürth", "lubeck": "Lübeck",
    "sankt augustin": "Sankt Augustin", "st. augustin": "Sankt Augustin",
}

# NRW municipalities used only as a fallback for rows with no NUTS code.
NRW_CITIES = {
    "aachen", "bielefeld", "bochum", "bonn", "bottrop", "detmold", "dortmund",
    "duisburg", "dusseldorf", "essen", "euskirchen", "gelsenkirchen",
    "gummersbach", "gutersloh", "hagen", "hamm", "herford", "herne", "hurth",
    "iserlohn", "julich", "kamp-lintfort", "kleve", "koln", "cologne",
    "krefeld", "lemgo", "leverkusen", "lippstadt", "meschede", "minden",
    "moers", "monchengladbach", "mulheim an der ruhr", "munster", "neuss",
    "oberhausen", "paderborn", "recklinghausen", "remscheid", "rheinbach",
    "sankt augustin", "st. augustin", "siegen", "soest", "solingen",
    "steinfurt", "troisdorf", "witten", "wuppertal",
}

LAND_CODES = {f"DE{c}" for c in "123456789ABCDEFG"}


def normalise_city(raw: object) -> str:
    """Lower-case, strip accents, and fold German digraphs for matching."""
    if not isinstance(raw, str):
        raw = ""
    s = unicodedata.normalize("NFKD", raw.strip().lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    for digraph, plain in (("ae", "a"), ("oe", "o"), ("ue", "u"), ("ss", "s")):
        s = s.replace(digraph, plain)
    return s


# Keys must live in the same normalised space the lookup uses (e.g. the
# double-s fold maps "dusseldorf" to "duseldorf").
CITY_DISPLAY_NORM = {normalise_city(k): v for k, v in CITY_DISPLAY.items()}


def display_city(raw: object) -> str:
    if not isinstance(raw, str):
        raw = ""
    return CITY_DISPLAY_NORM.get(normalise_city(raw), raw.strip().title())


def load_plz_register() -> dict:
    path = RAW.parent / "reference" / "plz_land.json"
    if not path.exists():
        sys.exit(f"missing {path} - run: python src/fetch_plz.py")
    return json.loads(path.read_text())["plz"]


def load_programme(label: str, archive: Path,
                   plz_map: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    with zipfile.ZipFile(archive) as zf:
        with zf.open("organization.csv") as fh:
            orgs = pd.read_csv(fh, sep=";", usecols=ORG_COLS, dtype=str,
                               encoding="utf-8-sig")
        with zf.open("project.csv") as fh:
            projects = pd.read_csv(fh, sep=";", usecols=PROJECT_COLS, dtype=str,
                                   encoding="utf-8-sig")
        with zf.open("euroSciVoc.csv") as fh:
            fields = pd.read_csv(fh, sep=";", dtype=str, encoding="utf-8-sig")

    orgs = orgs[orgs["country"] == "DE"].copy()
    orgs["programme"] = label
    for col in ("ecContribution", "netEcContribution"):
        orgs[col] = pd.to_numeric(orgs[col], errors="coerce").fillna(0.0)

    nuts = orgs["nutsCode"].fillna("").str.strip()
    land_nuts = nuts.str[:3].where(nuts.str[:3].isin(LAND_CODES), "")
    plz = (orgs["postCode"].fillna("").str.extract(r"(\d{5})", expand=False)
           .fillna(""))
    plz_rec = plz.map(lambda p: plz_map.get(p) or {})
    land_plz = plz_rec.map(lambda r: r.get("land") or "")
    city_nrw = orgs["city"].map(normalise_city).isin(
        {normalise_city(c) for c in NRW_CITIES})

    land = land_nuts.copy()
    method = pd.Series("", index=orgs.index)
    method[land_nuts != ""] = "nuts"
    # The postal code is part of the registered address and survives the
    # NUTS/geocoding regressions seen in some CORDIS releases, so it wins
    # any disagreement and covers rows without a NUTS code.
    use_plz = (land_plz != "") & (land_plz != land_nuts)
    land[use_plz] = land_plz[use_plz]
    method[use_plz] = "plz"
    only_city = (land == "") & city_nrw
    land[only_city] = "DEA"
    method[only_city] = "city"

    orgs["land"] = land
    orgs["land_method"] = method
    orgs["is_nrw"] = land == "DEA"
    orgs["nrw_method"] = method.where(orgs["is_nrw"], "")
    orgs["nuts_plz_conflict"] = ((land_nuts != "") & (land_plz != "")
                                 & (land_nuts != land_plz))

    # Repair coordinates against the postcode centroid.
    ll = (orgs["geolocation"].fillna("").str.strip("() ")
          .str.split(",", expand=True).reindex(columns=[0, 1]))
    glat = pd.to_numeric(ll[0], errors="coerce")
    glon = pd.to_numeric(ll[1], errors="coerce")
    plat = pd.to_numeric(plz_rec.map(lambda r: r.get("lat")), errors="coerce")
    plon = pd.to_numeric(plz_rec.map(lambda r: r.get("lon")), errors="coerce")
    off = (glat - plat).abs() + (glon - plon).abs()
    bad = plat.notna() & (glat.isna() | (off > 0.7))
    orgs["lat"] = glat.where(~bad, plat)
    orgs["lon"] = glon.where(~bad, plon)
    orgs["coords_repaired"] = bad & glat.notna()

    projects = projects.rename(columns={"id": "projectID"})
    merged = orgs.merge(projects, on="projectID", how="left", validate="m:1")
    merged["start_year"] = pd.to_datetime(
        merged["startDate"], errors="coerce").dt.year
    merged["activity_label"] = (merged["activityType"].map(ACTIVITY_LABELS)
                                .fillna("Other"))
    merged["org_label"] = (merged["shortName"].fillna("").str.strip()
                           .where(lambda s: s != "", merged["name"]))
    merged["city_display"] = merged["city"].map(display_city)

    # Distinct top-level EuroSciVoc field per project, e.g. "natural sciences".
    fields["field_l1"] = (fields["euroSciVocPath"].fillna("")
                          .str.strip("/").str.split("/").str[0].str.strip())
    fields = (fields[fields["field_l1"] != ""][["projectID", "field_l1"]]
              .drop_duplicates())
    return merged, fields


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    plz_map = load_plz_register()
    frames, field_frames = [], []
    for label, filename in ARCHIVES.items():
        archive = RAW / filename
        if not archive.exists():
            sys.exit(f"missing {archive} - run: python src/fetch_cordis.py")
        merged, fields = load_programme(label, archive, plz_map)
        frames.append(merged)
        field_frames.append(fields)
        print(f"[ok] {label}: {len(merged)} German participations, "
              f"{merged['is_nrw'].sum()} in NRW")

    de = pd.concat(frames, ignore_index=True)
    fields = pd.concat(field_frames, ignore_index=True).drop_duplicates()

    # Fractional field attribution: split each participation's contribution
    # equally across its project's distinct top-level fields.
    n_fields = fields.groupby("projectID").size().rename("n_fields")
    nrw = de[de["is_nrw"]].copy()
    nrw_fields = (nrw.merge(fields, on="projectID", how="inner")
                     .merge(n_fields, on="projectID"))
    nrw_fields["ec_frac"] = (nrw_fields["ecContribution"]
                             / nrw_fields["n_fields"])

    de.to_parquet(OUT / "participations_de.parquet", index=False)
    (nrw_fields[["programme", "projectID", "organisationID", "org_label",
                 "city_display", "field_l1", "ec_frac", "start_year"]]
     .to_parquet(OUT / "fields_nrw.parquet", index=False))

    provenance = {}
    prov_path = RAW / "PROVENANCE.json"
    if prov_path.exists():
        provenance = json.loads(prov_path.read_text())

    summary = {
        "built_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "provenance": provenance,
        "german_participations": int(len(de)),
        "nrw_participations": int(de["is_nrw"].sum()),
        "nrw_matched_by_city_fallback": int((de["nrw_method"] == "city").sum()),
        "land_nuts_plz_conflicts": int(de["nuts_plz_conflict"].sum()),
        "nrw_recovered_from_nuts_conflicts": int(
            (de["nuts_plz_conflict"] & de["is_nrw"]).sum()),
        "nrw_recovered_ec_eur": float(
            de.loc[de["nuts_plz_conflict"] & de["is_nrw"],
                   "ecContribution"].sum()),
        "coords_repaired": int(de["coords_repaired"].sum()),
        "german_rows_without_land": int((de["land"] == "").sum()),
        "nrw_projects": int(de.loc[de["is_nrw"], "projectID"].nunique()),
        "nrw_organisations": int(
            de.loc[de["is_nrw"], "organisationID"].nunique()),
        "nrw_ec_contribution_eur": float(
            de.loc[de["is_nrw"], "ecContribution"].sum()),
        "german_ec_contribution_eur": float(de["ecContribution"].sum()),
        "by_programme": {
            label: {
                "nrw_participations": int(sub["is_nrw"].sum()),
                "nrw_ec_contribution_eur": float(
                    sub.loc[sub["is_nrw"], "ecContribution"].sum()),
            }
            for label, sub in de.groupby("programme")
        },
    }
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(f"[ok] wrote {OUT / 'participations_de.parquet'}")
    print(f"[ok] wrote {OUT / 'fields_nrw.parquet'}")
    print(f"[ok] wrote {OUT / 'summary.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
