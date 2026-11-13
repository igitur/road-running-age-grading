#!/usr/bin/env python3
"""verify.py — prove the reference implementation matches the published calculator.

Three independent checks, because each catches a different class of error:

  A. EXACT EVENT GRID  — every (event, integer age) pair for both sexes is
     read straight from the table, so grading must return the stored factor
     bit-for-bit. Catches data-extraction errors.

  B. JS ORACLE         — random (sex, age, distance, time) requests are sent
     through the *published calculator's own JavaScript* executed under Node,
     and compared with this implementation. Catches algorithmic divergence:
     bracketing, interpolation order, clamping, rounding.

  C. STANDARDS FILE    — the age standards (seconds at 100%) are re-derived as
     open_standard / factor and compared with the MLDR-published
     Male/FemaleRoadStd2025.xlsx 'AgeStdSec' sheet. Catches any inconsistency
     between the two published artefacts.

Usage:
    python3 tools/verify.py [--grid] [--oracle] [--standards] [--all]
"""

from __future__ import annotations

import argparse
import json
import math
import random
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from brrag.core import OutOfRange, load_tables  # noqa: E402
from brrag.ui import ui_percent  # noqa: E402

PAGE = ROOT / "page.html"
ORACLE = ROOT / "tools" / "js_oracle.js"
STD = {"M": ROOT / "repo" / "2025 Files" / "MaleRoadStd2025.xlsx",
       "F": ROOT / "repo" / "2025 Files" / "FemaleRoadStd2025.xlsx"}


def check_exact_grid(tables) -> int:
    """A: at every published integer age, the returned factor IS the table cell."""
    bad = 0
    n = 0
    for sex in ("M", "F"):
        t = tables[f"USATF MLDR 2025 {sex}"]
        for ev in t.events:
            for idx, age in enumerate(t.ages):
                lk = t.lookup(sex, age, event=ev.name)
                n += 1
                if abs(lk.factor - ev.factors[idx]) > 1e-12:
                    bad += 1
                    if bad <= 5:
                        print(f"  MISMATCH {sex} {ev.name} age {age}: "
                              f"{lk.factor!r} != {ev.factors[idx]!r}")
                if not (ev.standard_s - 1e-9 <= lk.standard_s <= ev.standard_s + 1e-9):
                    bad += 1
                    if bad <= 5:
                        print(f"  STD MISMATCH {sex} {ev.name}: {lk.standard_s}")
    print(f"A. exact-event grid: {n} lookups, {bad} mismatches")
    return bad


def build_requests(seed: int = 20250110, n_random: int = 400) -> list[dict]:
    rng = random.Random(seed)
    reqs: list[dict] = []
    t = load_tables()[f"USATF MLDR 2025 M"]
    names = [e.name for e in t.events]

    # every event x a spread of ages, exact times
    for sex in ("M", "F"):
        for name in names:
            for age in (5, 6, 9, 17, 19, 20, 27, 28, 30, 34, 35, 40, 50, 55,
                        60, 65, 70, 75, 80, 85, 90, 95, 100):
                reqs.append({"sex": sex, "age": age, "event": name,
                             "time": "%d:%02d:%02d" % (2, rng.randrange(0, 60),
                                                       rng.randrange(0, 60))})

    # arbitrary distances (exercises the distance bracket) + odd ages
    for _ in range(n_random):
        sex = rng.choice("MF")
        dist = round(rng.uniform(1.7, 210.0), 3)
        age = rng.choice([
            rng.randint(5, 100),
            round(rng.uniform(5, 100), 1),
        ])
        secs = rng.randint(300, 8 * 3600)
        reqs.append({"sex": sex, "age": age, "event": None,
                     "distance_km": dist,
                     "time": f"{secs}"})
    return reqs


def run_oracle(reqs: list[dict]) -> list[dict]:
    proc = subprocess.run(
        ["node", str(ORACLE), str(PAGE)],
        input=json.dumps(reqs), capture_output=True, text=True, check=True,
    )
    return json.loads(proc.stdout)


def check_oracle(tables, tol_pct: float = 0.005, tol_fac: float = 1e-9) -> int:
    """B: compare against the calculator's own JavaScript."""
    if not PAGE.exists():
        print("B. JS oracle: SKIPPED (page.html missing; run fetch first)")
        return 0
    reqs = build_requests()
    results = run_oracle(reqs)
    bad = 0
    worst = 0.0
    for req, got in zip(reqs, results):
        if "error" in got:
            print(f"  ORACLE ERROR for {req}: {got['error']}")
            bad += 1
            continue
        sex = req["sex"]
        t = tables[f"USATF MLDR 2025 {sex}"]
        from brrag.ui import parse_time
        time_s = parse_time(req["time"])
        blank = str(got.get("afac", "")).strip() == ""
        try:
            g = t.grade(sex, req["age"], time_s, dist_km=req.get("distance_km"),
                        event=req.get("event"))
        except OutOfRange:
            if blank:
                continue  # both refuse to answer: parity
            bad += 1
            print(f"  OURS REFUSED but UI answered {req}: {got}")
            continue
        if blank:
            bad += 1
            print(f"  UI BLANK but we answered {req}: factor={g.factor:.6f}")
            continue
        # factor as the UI shows it (4 dp, round half up)
        want_fac = float(got["afac"])
        ui_fac = math.floor(g.factor * 1e4 + 0.5) / 1e4
        if abs(ui_fac - want_fac) > 1e-9 + tol_fac:
            bad += 1
            if bad <= 8:
                print(f"  FACTOR {req}: ours {ui_fac} vs ui {want_fac}")
        want_pct = float(got["aplp"])                     # the page: percent units
        mine_pct = 100.0 * ui_percent(time_s, g.age_standard_s)  # same display rounding
        d = abs(mine_pct - want_pct)
        worst = max(worst, d)
        if d > tol_pct:
            bad += 1
            if bad <= 8:
                print(f"  PERCENT {req}: ours {mine_pct} vs ui {want_pct} "
                      f"(diff {d:.4f})")
    print(f"B. JS oracle: {len(reqs)} requests, {bad} mismatches, "
          f"worst percent delta {worst:.6f} pp")
    return bad


def check_standards(tables, tol_s: float = 0.51) -> int:
    """C: open_standard / factor must equal the published age standards.

    One documented anomaly is expected and reported rather than failed: the
    'AgeStdSec' sheets carry a stale age-5 row for 17 of the 22 events (they
    imply a single 0.6080 factor across all distances, a leftover of the
    pre-2025 shared-youth-factor scheme). See docs/05-provenance.md.
    """
    try:
        import openpyxl
    except ImportError:
        print("C. standards file: SKIPPED (openpyxl not installed)")
        return 0
    KNOWN_CELL_ANOMALIES = {("F", "10kmRoad", 100)}
    ALIAS = {"1 Mile": "1MileRoad", "5 km": "5kmRoad", "6 km": "6kmRoad",
             "4 Mile": "4MileRoad", "8 km": "8kmRoad", "5 MIle": "5MileRoad",
             "10 km": "10kmRoad", "7 Mile": "7Mile", "12 km": "12km",
             "15 km": "15km", "10 Mile": "10Mile", "20 km": "20km",
             "H. Mar": "Half.Mar", "25 km": "25km", "30 km": "30km",
             "Marathon": "Marathon", "50 km": "50km", "50 Mile": "50Mile",
             "100 km": "100km", "150 km": "150km", "100 Mile": "100Mile",
             "200 km": "200km"}
    bad = 0
    checked = 0
    anomalies: dict[int, list[str]] = {}
    for sex in ("M", "F"):
        path = STD[sex]
        if not path.exists():
            print(f"C. standards file: SKIPPED ({path.name} missing)")
            return bad
        wb = openpyxl.load_workbook(path, data_only=True)
        sheet = wb["AgeStdSec" if sex == "M" else "AgeStanSec"]
        offset = 0  # the standards sheets have no duplicated Age column
                    # (only the female *factor* sheet does)
        t = tables[f"USATF MLDR 2025 {sex}"]
        by_name = {e.name: e for e in t.events}
        for col in range(2, 24):
            label = sheet.cell(2, col + offset).value
            ev = by_name.get(ALIAS.get(label, label))
            if ev is None:
                continue
            for row in range(6, 106):
                age = sheet.cell(row, 1 + offset).value
                want = sheet.cell(row, col + offset).value
                if not isinstance(age, int) or not isinstance(want, (int, float)):
                    continue
                got = t.lookup(sex, age, event=ev.name).age_standard_s
                checked += 1
                if abs(round(got) - want) <= tol_s:
                    continue
                if age == 5:
                    anomalies.setdefault(age, []).append(f"{sex} {ev.name}")
                    continue
                if (sex, ev.name, age) in KNOWN_CELL_ANOMALIES:
                    anomalies.setdefault(age, []).append(f"{sex} {ev.name}")
                    continue
                bad += 1
                if bad <= 6:
                    print(f"  STD {sex} {ev.name} age {age}: "
                          f"{got:.1f} (rounded {round(got)}) vs published {want}")
    for age, items in anomalies.items():
        print(f"  KNOWN ANOMALY age {age}: {len(items)} events disagree with the "
              f"factor sheet (documented; see docs/05-provenance.md)")
    total_anom = sum(len(v) for v in anomalies.values())
    print(f"C. standards file: {checked} cells, {bad} mismatches, "
          f"{total_anom} known anomalies")
    return bad


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--grid", action="store_true")
    ap.add_argument("--oracle", action="store_true")
    ap.add_argument("--standards", action="store_true")
    ap.add_argument("--all", action="store_true")
    a = ap.parse_args()
    if not any([a.grid, a.oracle, a.standards, a.all]):
        a.all = True
    tables = load_tables()
    bad = 0
    if a.grid or a.all:
        bad += check_exact_grid(tables)
    if a.oracle or a.all:
        bad += check_oracle(tables)
    if a.standards or a.all:
        bad += check_standards(tables)
    print("RESULT:", "PASS" if bad == 0 else f"FAIL ({bad} problems)")
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
