"""Fetch the German postal-code register from GeoNames.

Source: https://download.geonames.org/export/zip/DE.zip (GeoNames postal
code dataset, CC BY 4.0). Produces data/reference/plz_land.json mapping each
five-digit postal code to its Bundesland (as NUTS-1 code) and to a centroid
coordinate.

Why this exists: CORDIS releases occasionally carry NUTS codes and
geolocations that contradict the organisation's own registered address (the
August 2026 release stamped organisations from Cologne, Juelich, Munich and
elsewhere as Berlin). The postal code in the registered address is the
signal that survives such regressions, so the build pipeline cross-validates
NUTS codes against this register and repairs coordinates from the postcode
centroid when they disagree.

Postal codes that GeoNames places in more than one Bundesland (a handful of
border villages) are stored with land=null and are never used as evidence.

Usage:
    python src/fetch_plz.py
"""

from __future__ import annotations

import csv
import io
import json
import ssl
import sys
import urllib.request
import zipfile
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

try:  # macOS framework builds of Python ship without root certificates
    import certifi
    SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    SSL_CONTEXT = ssl.create_default_context()

OUT = Path(__file__).resolve().parent.parent / "data" / "reference"
URL = "https://download.geonames.org/export/zip/DE.zip"

STATE_TO_NUTS1 = {
    "Baden-Württemberg": "DE1", "Bayern": "DE2", "Berlin": "DE3",
    "Brandenburg": "DE4", "Bremen": "DE5", "Hamburg": "DE6", "Hessen": "DE7",
    "Mecklenburg-Vorpommern": "DE8", "Niedersachsen": "DE9",
    "Nordrhein-Westfalen": "DEA", "Rheinland-Pfalz": "DEB", "Saarland": "DEC",
    "Sachsen": "DED", "Sachsen-Anhalt": "DEE", "Schleswig-Holstein": "DEF",
    "Thüringen": "DEG",
}


def main() -> int:
    req = urllib.request.Request(URL)
    with urllib.request.urlopen(req, context=SSL_CONTEXT) as resp:
        payload = resp.read()
    with zipfile.ZipFile(io.BytesIO(payload)) as zf, zf.open("DE.txt") as fh:
        reader = csv.reader(io.TextIOWrapper(fh, encoding="utf-8"),
                            delimiter="\t")
        states = defaultdict(set)
        coords = defaultdict(list)
        for row in reader:
            plz, state = row[1].strip(), row[3].strip()
            if not plz or state not in STATE_TO_NUTS1:
                continue
            states[plz].add(STATE_TO_NUTS1[state])
            try:
                coords[plz].append((float(row[9]), float(row[10])))
            except (ValueError, IndexError):
                pass

    mapping = {}
    ambiguous = 0
    for plz, lands in states.items():
        pts = coords.get(plz) or []
        lat = round(sum(p[0] for p in pts) / len(pts), 5) if pts else None
        lon = round(sum(p[1] for p in pts) / len(pts), 5) if pts else None
        if len(lands) == 1:
            mapping[plz] = {"land": next(iter(lands)), "lat": lat, "lon": lon}
        else:
            ambiguous += 1
            mapping[plz] = {"land": None, "lat": lat, "lon": lon}

    OUT.mkdir(parents=True, exist_ok=True)
    record = {
        "source": "GeoNames postal code dataset (DE)",
        "url": URL,
        "license": "CC BY 4.0",
        "retrieved_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "postal_codes": len(mapping),
        "ambiguous_multi_land": ambiguous,
        "plz": mapping,
    }
    out_path = OUT / "plz_land.json"
    out_path.write_text(json.dumps(record, separators=(",", ":")) + "\n")
    print(f"[ok] {len(mapping):,} postal codes ({ambiguous} span more than "
          f"one Land and carry land=null)")
    print(f"[ok] wrote {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
