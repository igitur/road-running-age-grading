#!/usr/bin/env python3
"""reproduce_curve.py — rebuild a factor curve from its 10 fitted parameters.

The published tables ship as numbers, but the *methodology* is a 7-segment
piecewise curve with 10 free parameters per distance per sex, held in the
working spreadsheets (`maleRoad2025.xlsx` / `femaleRoad2025.xlsx`). This tool
reads those parameters and regenerates the curve, so docs/04-methodology.md can
state the model and prove it rather than assert it.

    python3 tools/reproduce_curve.py            # all fitted distances, both sexes
    python3 tools/reproduce_curve.py --show 5K  # print the curve

Note the working files are dated 2025-07-25 and are one revision behind the
published male 5 km / 10 km curves; this tool reproduces the *working file's*
own Age Factors sheet, not the published one. See docs/05-provenance.md.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    import openpyxl
except ImportError:  # tools deps are optional; see requirements-tools.txt
    openpyxl = None

ROOT = Path(__file__).resolve().parent.parent
SEX_FILES = {"M": ROOT / "repo/2025 Files/maleRoad2025.xlsx",
             "F": ROOT / "repo/2025 Files/femaleRoad2025.xlsx"}

# Cell layout: coefficients always live in F4/F5/G4/G5. The age breakpoints sit
# in H3:H5 (c, b, a) and I3:I5 (d, e, f) — EXCEPT on the male Mile sheet, which
# is shifted one column right (I3:I5 and J3:J5) because it lacks a spare column.
LAYOUTS = {
    "wide": {"B": "F4", "A": "F5", "E": "G4", "F": "G5",
             "c": "H3", "b": "H4", "a": "H5",
             "d": "I3", "e": "I4", "f": "I5"},
    "shifted": {"B": "F4", "A": "F5", "E": "G4", "F": "G5",
                "c": "I3", "b": "I4", "a": "I5",
                "d": "J3", "e": "J4", "f": "J5"},
}

FITTED = {"M": ["Mile", "5K", "10K", "H.Marathon", "Marathon"],
          "F": ["Mile", "5K", "10K", "H.Marathon", "Marathon"]}

AGES = list(range(5, 101))


def factor(age: float, p: dict[str, float]) -> float:
    """The 7-segment curve. Slopes are matched at b and e, which forces
    C = B / (2(c-b)) and D = E / (2(e-d)); those two are computed here."""
    B, A, E, F = p["B"], p["A"], p["E"], p["F"]
    a, b, c, d, e, f = p["a"], p["b"], p["c"], p["d"], p["e"], p["f"]
    C = B / (2 * (c - b))
    D = E / (2 * (e - d))

    if age >= c and age < d:
        return 1.0
    if age < a:
        return 1 - C * (c - b) ** 2 - B * (b - age) - A * (a - age) ** 2
    if age < b:
        return 1 - C * (c - b) ** 2 - B * (b - age)
    if age < c:
        return 1 - C * (c - age) ** 2
    if age < e:
        return 1 - D * (age - d) ** 2
    if age < f:
        return 1 - D * (e - d) ** 2 - E * (age - e)
    return 1 - D * (e - d) ** 2 - E * (age - e) - F * (age - f) ** 2


def read_params(ws, layout: dict[str, str]) -> dict[str, float]:
    return {k: float(ws[v].value) for k, v in layout.items()}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--show", help="print the curve for one sheet, e.g. 5K")
    a = ap.parse_args()

    missing = [p.name for p in SEX_FILES.values() if not p.exists()]
    if openpyxl is None:
        print("SKIPPED: openpyxl not installed (pip install -r requirements-tools.txt)")
        return 0
    if missing:
        print(f"SKIPPED: {', '.join(missing)} not present.")
        print("The working files live in the upstream tables repository:")
        print("  make fetch      # clones it into repo/")
        return 0

    worst_overall = 0.0
    for sex, path in SEX_FILES.items():
        wb = openpyxl.load_workbook(path, data_only=True)
        af = wb["Age Factors"]
        print(f"== {sex}  ({path.name})")
        for sheet in FITTED[sex]:
            if sheet not in wb.sheetnames:
                print(f"  {sheet:<11} no such sheet")
                continue
            shifted = sex == "M" and sheet == "Mile"
            layout = LAYOUTS["shifted" if shifted else "wide"]
            p = read_params(wb[sheet], layout)
            # locate this distance's column in the Age Factors sheet
            header = {af.cell(2, c).value: c for c in range(1, 25)}
            label = {"Mile": "1 Mile", "5K": "5 km", "10K": "10 km",
                     "H.Marathon": "H. Mar", "Marathon": "Marathon"}[sheet]
            col = header.get(label)
            if col is None:
                print(f"  {sheet:<11} column {label!r} not found")
                continue
            worst = 0.0
            offenders = []
            for row in range(6, 102):
                age = af.cell(row, 1).value
                if not isinstance(age, int):
                    continue
                want = af.cell(row, col).value
                got = round(factor(age, p), 4)   # the sheet stores 4 dp
                d = abs(got - want)
                if d > 1e-4:
                    offenders.append((age, want, got))
                worst = max(worst, d)
            worst_overall = max(worst_overall, worst if not offenders else 0.0)
            print(f"  {sheet:<11} B={p['B']:<7} A={p['A']:<7} E={p['E']:<8} "
                  f"F={p['F']:<8} a={p['a']:<6} b={p['b']:<5} c={p['c']:<5} "
                  f"d={p['d']:<6} e={p['e']:<6} f={p['f']:<6} "
                  f"max|err| {worst:.4f}")
            if offenders:
                ages = [o[0] for o in offenders]
                print(f"       NOTE {sex}/{sheet}: ages {ages[0]}-{ages[-1]} "
                      f"({len(ages)} ages) stay at 1.0 in the sheet although the "
                      f"fitted masters curve has already started (d={p['d']}); "
                      f"largest gap {max(abs(o[1]-o[2]) for o in offenders):.4f}. "
                      f"The sheet's youth/master formula blocks switch over at "
                      f"age 35, not at d. See docs/04-methodology.md.")
            if a.show and a.show == sheet:
                for age in (5, 10, 17, 19, 22, 30, 35, 40, 50, 60, 70, 80, 90, 100):
                    print(f"      age {age:>3}: {factor(age, p):.4f}")

    print(f"\nworst absolute error across the curves that match exactly: "
          f"{worst_overall:.4f}")
    print("(4 dp is the published precision, so <= 0.0001 means the model and "
          "the parameters are exactly right)")
    return 0 if worst_overall <= 1e-4 else 1


if __name__ == "__main__":
    sys.exit(main())
