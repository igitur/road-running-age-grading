#!/usr/bin/env python3
"""Extract MLDR road age-grading factor tables from the Howard Grubb calculator page.

The calculator (mldrroad25.html) embeds the factor tables as JS literals. They are
the authoritative published 2025 road tables (they match MLDRRoadFactors2025.xlsm
and Male/FemaleRoadStd2025.xlsx cell-for-cell).

Usage: python3 tools/extract_tables.py page.html data/mldr_road.json
"""
import json
import re
import sys

VERSIONS = {
    "MLDR_25_M_facs": ("M", "2025", "USATF MLDR"),
    "MLDR_25_F_facs": ("F", "2025", "USATF MLDR"),
    "MLDR_20_M_facs": ("M", "2020", "USATF MLDR"),
    "MLDR_20_F_facs": ("F", "2020", "USATF MLDR"),
    "WMA_15_M_facs": ("M", "2015", "WMA"),
    "WMA_15_F_facs": ("F", "2015", "WMA"),
    "WMA_10_M_facs": ("M", "2010", "WMA"),
    "WMA_10_F_facs": ("F", "2010", "WMA"),
}

AGES_RE = re.compile(r"(\w+)\.addAges\(new Array\(([^)]*)\)\)")
EVENT_RE = re.compile(
    r"(\w+)\.addEvent\(new facrow\(\"([^\"]+)\",([0-9.]+),([0-9.]+),([0-9.,]+)\)\)"
)


def main(src: str, dst: str) -> None:
    text = open(src, encoding="utf-8", errors="replace").read()

    ages: dict[str, list[int]] = {}
    for name, body in AGES_RE.findall(text):
        ages[name] = [int(x) for x in body.split(",")]

    out: dict = {"source": "https://www.howardgrubb.co.uk/athletics/mldrroad25.html",
                 "tables": {}}

    for var, (sex, year, body) in VERSIONS.items():
        events = []
        for v, ev, dist, std, facs in EVENT_RE.findall(text):
            if v != var:
                continue
            f = [float(x) for x in facs.split(",")]
            if len(f) != len(ages[var]):
                raise SystemExit(
                    f"{var}/{ev}: {len(f)} factors vs {len(ages[var])} ages"
                )
            events.append(
                {"event": ev, "distance_km": float(dist),
                 "open_standard_s": float(std), "factors": f}
            )
        if not events:
            continue
        key = f"{body} {year} {sex}"
        out["tables"][key] = {
            "authority": body, "year": int(year), "sex": sex,
            "vari": var,
            "ages": ages[var], "events": events,
        }

    with open(dst, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1)

    for k, t in out["tables"].items():
        print(f"{k:22s} events={len(t['events']):2d} ages={len(t['ages'])}"
              f" [{t['ages'][0]}..{t['ages'][-1]}]")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
