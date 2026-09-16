#!/usr/bin/env python3
# WHY THIS FILE EXISTS:
# pytest-cov's own --cov-fail-under only enforces one global number
# (80%, Day 27's floor). The spec's other requirement — 100% on
# security-critical (access_control.py, auth_service.py) and
# financial-critical (kpi_service.py, anomaly_service.py) paths — needs
# a per-file check pytest-cov doesn't do on its own. Parses the
# Cobertura coverage.xml pytest --cov-report=xml already writes and
# hard-fails if any of the four drop below 100% line coverage,
# independent of (and in addition to) the global gate.

import sys
import xml.etree.ElementTree as ET
from pathlib import Path

CRITICAL_FILES = [
    "app/services/access_control.py",
    "app/services/auth_service.py",
    "app/services/kpi_service.py",
    "app/services/anomaly_service.py",
]

COVERAGE_XML = Path("coverage.xml")


def main() -> int:
    if not COVERAGE_XML.exists():
        print(f"check_coverage.py: {COVERAGE_XML} not found — run pytest --cov-report=xml first.")
        return 1

    root = ET.parse(COVERAGE_XML).getroot()
    line_rates: dict[str, float] = {}
    for cls in root.iter("class"):
        filename = cls.get("filename", "")
        line_rates[filename] = float(cls.get("line-rate", "0"))

    failures = []
    for target in CRITICAL_FILES:
        # coverage.xml's filename is relative to the --cov=app package
        # root ("services/access_control.py", no "app/" prefix) — match
        # by suffix rather than assuming either side's exact form.
        matches = [path for path in line_rates if target == path or target.endswith(path)]
        if not matches:
            failures.append(f"{target}: not found in coverage.xml (was it imported by any test?)")
            continue
        rate = line_rates[matches[0]]
        if rate < 1.0:
            failures.append(f"{target}: {rate * 100:.1f}% line coverage (100% required)")

    if failures:
        print("check_coverage.py: security/financial-critical coverage floor not met:")
        for f in failures:
            print(f"  - {f}")
        return 1

    print("check_coverage.py: all security/financial-critical files at 100% line coverage.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
