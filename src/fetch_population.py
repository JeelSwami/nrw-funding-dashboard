"""Fetch official population figures for the German Laender (NUTS-1).

Source: Eurostat, dataset demo_r_d2jan ("Population on 1 January by age,
sex and NUTS-2 region"), queried at NUTS-1 level for DE1..DEG via the
Eurostat dissemination API. Reuse of Eurostat data is permitted with
attribution (CC BY 4.0). The retrieval timestamp and the reference year
actually used per region are stored alongside the figures, so the
per-capita normalisation in the dashboard is fully traceable.

Usage:
    python src/fetch_population.py
"""

from __future__ import annotations

import json
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

GEOS = [f"DE{c}" for c in "123456789ABCDEFG"]
URL = ("https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/"
       "demo_r_d2jan?format=JSON&lang=EN&sex=T&age=TOTAL"
       "&sinceTimePeriod=2020" + "".join(f"&geo={g}" for g in GEOS))


def latest_by_geo(data: dict) -> tuple[dict[str, int], dict[str, str]]:
    """Extract the most recent non-missing value per geo from JSON-stat."""
    ids, sizes = data["id"], data["size"]
    for dim, n in zip(ids, sizes):
        if dim not in ("geo", "time") and n != 1:
            sys.exit(f"unexpected non-singleton dimension {dim!r} (size {n}); "
                     "the query filters should collapse it")
    strides, s = {}, 1
    for dim, n in zip(reversed(ids), reversed(sizes)):
        strides[dim], s = s, s * n
    geo_idx = data["dimension"]["geo"]["category"]["index"]
    time_idx = data["dimension"]["time"]["category"]["index"]
    values = data["value"]
    pop, year = {}, {}
    for geo, gpos in geo_idx.items():
        for t in sorted(time_idx, reverse=True):
            key = str(gpos * strides["geo"] + time_idx[t] * strides["time"])
            if values.get(key) is not None:
                pop[geo], year[geo] = int(values[key]), t
                break
    return pop, year


def main() -> int:
    req = urllib.request.Request(URL, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, context=SSL_CONTEXT) as resp:
        data = json.load(resp)

    pop, year = latest_by_geo(data)
    missing = sorted(set(GEOS) - set(pop))
    if missing:
        sys.exit(f"no population value returned for {missing}")

    OUT.mkdir(parents=True, exist_ok=True)
    record = {
        "source": "Eurostat, demo_r_d2jan (population on 1 January), NUTS-1",
        "url": URL,
        "license": "CC BY 4.0 (Eurostat reuse policy)",
        "retrieved_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "reference_year": year,
        "population": pop,
    }
    out_path = OUT / "population_nuts1.json"
    out_path.write_text(json.dumps(record, indent=2) + "\n")
    years = sorted(set(year.values()))
    print(f"[ok] {len(pop)} Laender, reference year(s) {', '.join(years)}")
    print(f"[ok] wrote {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
