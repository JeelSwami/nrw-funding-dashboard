"""Download the official CORDIS bulk datasets and record their provenance.

Sources (EU Publications Office, reuse permitted under Commission Decision
2011/833/EU with attribution):
  - Horizon Europe (2021-2027): https://cordis.europa.eu/data/cordis-HORIZONprojects-csv.zip
  - Horizon 2020  (2014-2020): https://cordis.europa.eu/data/cordis-h2020projects-csv.zip

Every download is logged to data/raw/PROVENANCE.json with the retrieval
timestamp and the server's Last-Modified / ETag headers, so any figure in the
dashboard can be traced to an exact snapshot of the source data.

Usage:
    python src/fetch_cordis.py [--force]
"""

from __future__ import annotations

import argparse
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

RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"

DATASETS = {
    "HORIZON": "https://cordis.europa.eu/data/cordis-HORIZONprojects-csv.zip",
    "H2020": "https://cordis.europa.eu/data/cordis-h2020projects-csv.zip",
}


def head(url: str) -> dict:
    req = urllib.request.Request(url, method="HEAD")
    with urllib.request.urlopen(req, context=SSL_CONTEXT) as resp:
        return {
            "last_modified": resp.headers.get("Last-Modified"),
            "etag": resp.headers.get("ETag"),
            "content_length": resp.headers.get("Content-Length"),
        }


def download(url: str, dest: Path) -> None:
    tmp = dest.with_suffix(".part")
    with urllib.request.urlopen(url, context=SSL_CONTEXT) as resp, \
            open(tmp, "wb") as fh:
        while chunk := resp.read(1 << 20):
            fh.write(chunk)
    tmp.rename(dest)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true", help="re-download even if present")
    args = parser.parse_args()

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    provenance_path = RAW_DIR / "PROVENANCE.json"
    provenance = {}
    if provenance_path.exists():
        provenance = json.loads(provenance_path.read_text())

    for programme, url in DATASETS.items():
        dest = RAW_DIR / url.rsplit("/", 1)[-1]
        meta = head(url)
        if dest.exists() and not args.force:
            print(f"[skip] {dest.name} already present "
                  f"(server Last-Modified: {meta['last_modified']})")
        else:
            print(f"[get ] {dest.name} ({int(meta['content_length'] or 0) / 1e6:.1f} MB)")
            download(url, dest)
        provenance[programme] = {
            "url": url,
            "file": dest.name,
            "retrieved_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            **meta,
        }

    provenance_path.write_text(json.dumps(provenance, indent=2) + "\n")
    print(f"[ok  ] provenance written to {provenance_path.relative_to(Path.cwd())}"
          if provenance_path.is_relative_to(Path.cwd()) else f"[ok  ] {provenance_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
