"""Fetch DFG Foerderatlas 2024 tables (awards 2020-2022).

The DFG publishes its Foerderatlas tables as interactive Datawrapper embeds
on https://foerderatlas.dfg.de/daten/ . Each embed exposes its underlying
data at a versioned CSV endpoint; this script resolves the current version
from the chart's embed.js and stores the parsed figures with provenance.

Tables used (DFG Foerderatlas 2024, reporting period 2020-2022):
  - 1EMUJ: DFG-Bewilligungen nach Hochschulen und Fachgebieten (top-40
    universities, EUR million by subject area)
  - DhzmE: DFG-Bewilligungen nach Bundeslaendern und Wissenschaftsbereichen

Attribution: (c) Deutsche Forschungsgemeinschaft, Foerderatlas 2024.

Usage:
    python src/fetch_dfg.py
"""

from __future__ import annotations

import csv
import io
import json
import re
import ssl
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

try:  # macOS framework builds of Python ship without root certificates
    import certifi
    SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    SSL_CONTEXT = ssl.create_default_context()

OUT = Path(__file__).resolve().parent.parent / "data" / "reference"

CHARTS = {
    "universities": {
        "id": "1EMUJ",
        "page": ("https://foerderatlas.dfg.de/daten/dfg-bewilligungen-fuer-"
                 "2020-bis-2022-nach-hochschulen-und-fachgebieten/"),
    },
    "laender": {
        "id": "DhzmE",
        "page": ("https://foerderatlas.dfg.de/daten/dfg-bewilligungen-fuer-"
                 "2020-bis-2022-nach-bundeslaendern-und-"
                 "wissenschaftsbereichen/"),
    },
}


def get(url: str) -> str:
    req = urllib.request.Request(
        url, headers={"User-Agent": "Mozilla/5.0 (data pipeline; "
                                    "github.com/JeelSwami/nrw-funding-dashboard)"})
    with urllib.request.urlopen(req, context=SSL_CONTEXT) as resp:
        return resp.read().decode("utf-8")


def german_float(raw: str) -> float | None:
    s = (raw or "").strip().replace(" ", "")
    if not s:
        return None
    s = s.replace(".", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def fetch_chart(chart_id: str) -> tuple[int, list[list[str]]]:
    embed = get(f"https://datawrapper.dwcdn.net/{chart_id}/embed.js")
    m = re.search(rf"dwcdn\.net/{chart_id}/(\d+)/", embed)
    if not m:
        sys.exit(f"could not resolve current version for chart {chart_id}")
    version = int(m.group(1))
    csv_text = get(
        f"https://datawrapper.dwcdn.net/{chart_id}/{version}/dataset.csv")
    rows = list(csv.reader(io.StringIO(csv_text), delimiter="\t"))
    return version, rows


def main() -> int:
    versions = {}

    version, rows = fetch_chart(CHARTS["universities"]["id"])
    versions["universities"] = version
    universities = {}
    for row in rows[1:]:
        if not row or not row[0].strip():
            continue
        values = [german_float(v) for v in row[1:]]
        total = sum(v for v in values if v is not None)
        universities[row[0].strip()] = round(total, 3)

    LAENDER_NAMES = {
        "Baden-Württemberg", "Bayern", "Berlin", "Brandenburg", "Bremen",
        "Hamburg", "Hessen", "Mecklenburg-Vorpommern", "Niedersachsen",
        "Nordrhein-Westfalen", "Rheinland-Pfalz", "Saarland", "Sachsen",
        "Sachsen-Anhalt", "Schleswig-Holstein", "Thüringen",
    }
    version, rows = fetch_chart(CHARTS["laender"]["id"])
    versions["laender"] = version
    laender = {}
    for row in rows[1:]:
        name = (row[0] if row else "").strip()
        total = german_float(row[1]) if len(row) > 1 else None
        # keeps only the 16 Laender: drops the units row and any total row
        if name in LAENDER_NAMES and total is not None:
            laender[name] = round(total, 1)

    if "Nordrhein-Westfalen" not in laender or len(universities) < 30:
        sys.exit("parsed data looks incomplete; check the source tables")

    OUT.mkdir(parents=True, exist_ok=True)
    record = {
        "source": "DFG Foerderatlas 2024 (awards 2020-2022, EUR million)",
        "attribution": "(c) Deutsche Forschungsgemeinschaft, "
                       "Foerderatlas 2024, foerderatlas.dfg.de",
        "pages": {k: v["page"] for k, v in CHARTS.items()},
        "datawrapper_versions": versions,
        "retrieved_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "universities_meur": universities,
        "laender_meur": laender,
    }
    out_path = OUT / "dfg_foerderatlas.json"
    out_path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n")
    print(f"[ok] {len(universities)} universities, {len(laender)} Laender "
          f"(NRW: {laender['Nordrhein-Westfalen']:,} M EUR)")
    print(f"[ok] wrote {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
