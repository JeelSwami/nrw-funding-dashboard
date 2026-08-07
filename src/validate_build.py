"""Sanity-check a freshly built dataset against the previously published one.

Compares data/processed/summary.json (working tree) with the version at git
HEAD. Framework-programme data is cumulative: participation counts can only
grow, and totals should move gradually between monthly releases. A refresh
that violates these bounds points to a corrupted source snapshot (for
example, the August 2026 CORDIS release stamped Cologne- and Juelich-based
organisations with a Berlin NUTS code) and must not be published.

Exit code 0 = plausible; 1 = refuse to publish. Used by the data-refresh
workflow between the build and commit steps.

Usage:
    python src/validate_build.py
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

SUMMARY = Path(__file__).resolve().parent.parent / "data" / "processed" / "summary.json"

# A monthly refresh may lose at most this fraction of participations
# (small corrections happen), and totals may move at most this fraction.
MAX_COUNT_DROP = 0.02
MAX_EC_CHANGE = 0.20

CHECKS = [
    ("german_participations", MAX_COUNT_DROP, None),
    ("nrw_participations", MAX_COUNT_DROP, None),
    ("nrw_ec_contribution_eur", MAX_EC_CHANGE, MAX_EC_CHANGE),
    ("german_ec_contribution_eur", MAX_EC_CHANGE, MAX_EC_CHANGE),
]


def main() -> int:
    new = json.loads(SUMMARY.read_text())
    try:
        blob = subprocess.run(
            ["git", "show", "HEAD:data/processed/summary.json"],
            capture_output=True, text=True, check=True,
            cwd=SUMMARY.parent.parent.parent).stdout
        old = json.loads(blob)
    except (subprocess.CalledProcessError, json.JSONDecodeError):
        print("[warn] no previous summary at git HEAD; skipping validation")
        return 0

    failures = []
    for key, max_drop, max_rise in CHECKS:
        o, n = old.get(key), new.get(key)
        if not o:
            continue
        change = (n - o) / o
        print(f"{key}: {o:,.0f} -> {n:,.0f} ({change:+.1%})")
        if max_drop is not None and change < -max_drop:
            failures.append(f"{key} dropped {change:.1%} (limit -{max_drop:.0%})")
        if max_rise is not None and change > max_rise:
            failures.append(f"{key} rose {change:.1%} (limit +{max_rise:.0%})")

    recovered = new.get("nrw_recovered_from_nuts_conflicts", 0)
    if recovered:
        print(f"[note] {recovered:,} NRW rows recovered from NUTS/address "
              f"conflicts (EUR {new.get('nrw_recovered_ec_eur', 0):,.0f})")

    if failures:
        print("\n[FAIL] refusing to publish this build:")
        for f in failures:
            print(" -", f)
        return 1
    print("[ok] build is plausible against the previous release")
    return 0


if __name__ == "__main__":
    sys.exit(main())
