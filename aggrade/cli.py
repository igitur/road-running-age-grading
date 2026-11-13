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
import re
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aggrade import __version__  # noqa: E402
from aggrade.core import DEFAULT_DATA, OutOfRange, load_tables  # noqa: E402
from aggrade.ui import format_time, parse_time, ui_percent  # noqa: E402

MILE_KM = 1.609344
_KM_UNITS = {"k", "km", "kilometer", "kilometers", "kilometre", "kilometres"}
_MILE_UNITS = {"m", "mile", "miles"}
_DISTANCE_RE = re.compile(r"^(\d+(?:\.\d+)?)([a-z]*)$")


def parse_distance(text: str) -> float:
    """The distance grammar, the same one the Excel add-in uses.

    <number> followed by k, km, kilometer(s), kilometre(s)   -> kilometres
    <number> followed by m, mile, miles                      -> miles
    half marathon, marathon                                  -> 21.0975, 42.195 km
    a bare number is kilometres

    Case is ignored, and every space, tab, newline and hyphen is removed before
    comparison, so "10 K M", "Half-Marathon" and "6.2 miles" all work.
    """
    key = "".join(ch for ch in text.lower() if not ch.isspace() and ch not in "-_")
    if key == "halfmarathon":
        return 21.0975
    if key == "marathon":
        return 42.195
    m = _DISTANCE_RE.match(key)
    if not m:
        raise SystemExit(
            f"unknown distance {text!r}. Use a number with a unit "
            f"(10k, 10 km, 10 kilometres, 6.2 miles), half marathon, marathon, "
            f"or a bare number of kilometres")
    amount, unit = float(m.group(1)), m.group(2)
    if amount <= 0:
        raise SystemExit(f"distance must be positive, got {text!r}")
    if unit in _KM_UNITS or unit == "":
        return amount
    if unit in _MILE_UNITS:
        return amount * MILE_KM
    raise SystemExit(
        f"unknown unit {unit!r} in {text!r}. Use k, km, kilometer(s), "
        f"kilometre(s), m, mile or miles")



def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="aggrade",
        description="Age-grade a road-running performance (USATF MLDR tables).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    ap.add_argument("--version", action="version",
                    version=f"aggrade {__version__}")
    ap.add_argument("time", nargs="?", help="performance: h:mm:ss, mm:ss or seconds")
    ap.add_argument("--age", type=float, help="age in years at race day (fractional ok)")
    ap.add_argument("--sex", "-s", default="M", choices=["M", "F", "m", "f"],
                    help="M or F (default M)")
    ap.add_argument("--distance", "-d", help="distance: 10k, 10 km, 6.2 miles, half marathon, "
                         "marathon, or a bare number of km")
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
