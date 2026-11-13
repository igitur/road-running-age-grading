#!/usr/bin/env python3
"""aggrade — grade a road-running performance by sex, age and distance.

Examples
--------
    aggrade 40:00 --age 40 --sex M --distance 10k
    aggrade 2:30:00 --age 75 --sex M --event Marathon --json
    aggrade 3:15:00 --age 52 --sex F --distance 42.195 --show-standard
    aggrade --list-events --sex F
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aggrade.core import DEFAULT_DATA, OutOfRange, load_tables  # noqa: E402
from aggrade.ui import format_time, parse_time, ui_percent  # noqa: E402

DISTANCE_ALIASES = {
    "mile": 1.609344, "1mile": 1.609344, "1mi": 1.609344,
    "5k": 5.0, "6k": 6.0, "4mi": 6.437376, "4mile": 6.437376,
    "8k": 8.0, "5mi": 8.04672, "5mile": 8.04672, "10k": 10.0,
    "7mi": 11.265408, "7mile": 11.265408, "12k": 12.0, "15k": 15.0,
    "10mi": 16.09344, "10mile": 16.09344, "20k": 20.0,
    "half": 21.0975, "hm": 21.0975, "halfmarathon": 21.0975,
    "half.mar": 21.0975, "half-marathon": 21.0975,
    "25k": 25.0, "30k": 30.0,
    "marathon": 42.195, "mar": 42.195,
    "50k": 50.0, "50mi": 80.4672, "50mile": 80.4672,
    "100k": 100.0, "150k": 150.0, "100mi": 160.9344, "100mile": 160.9344,
    "200k": 200.0,
}


def parse_distance(text: str) -> float:
    key = text.strip().lower().replace("_", "").replace(" ", "")
    if key in DISTANCE_ALIASES:
        return DISTANCE_ALIASES[key]
    try:
        return float(key.removesuffix("km"))
    except ValueError:
        raise SystemExit(
            f"unknown distance {text!r}; try 5k, 10k, half, marathon or a number "
            f"of kilometres"
        ) from None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="aggrade",
        description="Age-grade a road-running performance (USATF MLDR tables).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    ap.add_argument("time", nargs="?", help="performance: h:mm:ss, mm:ss or seconds")
    ap.add_argument("--age", type=float, help="age in years at race day (fractional ok)")
    ap.add_argument("--sex", "-s", default="M", choices=["M", "F", "m", "f"],
                    help="M or F (default M)")
    ap.add_argument("--distance", "-d", help="distance, e.g. 10k, half, marathon, 12.7")
    ap.add_argument("--event", "-e", help="exact table event name, e.g. 10kmRoad")
    ap.add_argument("--year", type=int, default=2025, help="table year (default 2025)")
    ap.add_argument("--file", type=Path, default=DEFAULT_DATA, help="tables JSON")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--list-events", action="store_true", help="list table events")
    ap.add_argument("--show-standard", action="store_true",
                    help="also show open/age standard and time at 100%%")
    ap.add_argument("--ui-parity", action="store_true",
                    help="reproduce the web calculator's displayed percentage "
                         "(rounds the age standard first)")
    args = ap.parse_args(argv)

    tables = load_tables(args.file)
    sex = args.sex.upper()
    key = f"USATF MLDR {args.year} {sex}"
    if key not in tables:
        raise SystemExit(f"no table {key!r}; have: {sorted(tables)}")
    t = tables[key]

    if args.list_events:
        rows = [{"event": e.name, "distance_km": e.distance_km,
                 "open_standard_s": e.standard_s,
                 "open_standard": format_time(e.standard_s, 0),
                 "calibration": e.is_calibration}
                for e in t.events]
        if args.json:
            print(json.dumps(rows, indent=1))
        else:
            for r in rows:
                tag = " (fitted)" if r["calibration"] else ""
                print(f"{r['event']:<12} {r['distance_km']:>9.4f} km  "
                      f"open {r['open_standard']:>9}{tag}")
        return 0

    if args.time is None or args.age is None:
        ap.error("a time and --age are required")
    if args.distance is None and args.event is None:
        ap.error("pass --distance or --event")

    time_s = parse_time(args.time)
    dist_km = parse_distance(args.distance) if args.distance else None
    try:
        g = t.grade(sex, args.age, time_s, dist_km=dist_km, event=args.event)
    except OutOfRange as exc:
        raise SystemExit(f"error: {exc}") from None

    percent = ui_percent(time_s, g.age_standard_s) if args.ui_parity else g.percent
    out = {
        "sex": sex,
        "age": args.age,
        "year": args.year,
        "event": args.event,
        "distance_km": dist_km,
        "time_s": time_s,
        "time": format_time(time_s, 1),
        "factor": round(g.factor, 4),
        "age_graded_s": g.age_graded_s,
        "age_graded": format_time(g.age_graded_s, 1),
        "percent": round(percent, 2),
        "open_standard_s": g.standard_s,
        "open_standard": format_time(g.standard_s, 0),
        "age_standard_s": g.age_standard_s,
        "age_standard": format_time(g.age_standard_s, 1),
        "ui_parity": args.ui_parity,
    }
    if args.json:
        print(json.dumps(out, indent=1))
        return 0

    if args.show_standard:
        print(f"open standard  {out['open_standard']:>10}")
        print(f"age standard   {out['age_standard']:>10}  (scores 100.0%)")
    print(f"factor         {out['factor']:>10.4f}")
    print(f"age-graded     {out['age_graded']:>10}")
    print(f"age grade      {out['percent']:>10.2f}%")
    return 0


if __name__ == "__main__":
    sys.exit(main())
