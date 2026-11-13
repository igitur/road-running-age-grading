#!/usr/bin/env python3
"""gen_expectations.py — ground truth for the C++ tests.

The Python implementation in this repo is itself verified against the published
calculator and the official workbook (see docs/08-validation.md). So it, not a
hand-copied table of numbers, is what the add-in's tests compare against.

    python3 xll/tools/gen_expectations.py            # writes xll/test/expected.h
    python3 xll/tools/gen_expectations.py --check    # fail if stale

Emits a table of (sex, age, distance_km, time_s, factor, age_std_s, graded_s,
percent) covering integer and fractional ages, published and off-grid
distances, and the whole age range on both sides of the plateau.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from aggrade.core import load_tables            # noqa: E402

DST = ROOT / "xll" / "test" / "expected.h"

AGES = [5, 6, 8, 12, 17, 19, 20, 27, 33, 40, 47, 55, 63, 70, 78, 85, 92, 100,
        33.5, 60.25, 99.5]
DISTANCES = [1.609344, 5.0, 6.437376, 8.0, 10.0, 12.5, 16.09344, 21.0975,
             30.0, 42.195, 80.4672]
# one time per (index) so the grid is deterministic and varied
TIMES = [1620, 2400, 3600, 5400, 7200, 9000, 10800, 12600, 14400, 16200, 21600]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()

    tables = load_tables()
    rows: list[str] = []
    n = 0
    for sex in ("M", "F"):
        t = tables[f"USATF MLDR 2025 {sex}"]
        for i, age in enumerate(AGES):
            for j, dist in enumerate(DISTANCES):
                time_s = TIMES[(i + j) % len(TIMES)]
                g = t.grade(sex, age, time_s, dist_km=dist)
                pct = g.percent
                rows.append(
                    f'    {{"{sex}", {age!r}, {dist!r}, {time_s!r}, '
                    f"{g.factor:.6f}, {g.age_standard_s:.4f}, "
                    f"{g.age_graded_s:.4f}, {pct:.4f}}},")
                n += 1

    text = f"""\
// GENERATED FILE — do not edit.
// Produced by xll/tools/gen_expectations.py from the verified Python
// implementation (aggrade). Regenerate with:  make -C xll expectations
#pragma once

namespace ag::test {{

struct Expect {{
    const char* sex;
    double age;
    double distance_km;
    double time_s;
    double factor;
    double age_standard_s;
    double graded_s;
    double percent;
}};

inline constexpr Expect expectations[] = {{
{chr(10).join(rows)}
}};

inline constexpr int n_expectations =
    static_cast<int>(sizeof(expectations) / sizeof(expectations[0]));

}}  // namespace ag::test
"""
    if a.check:
        cur = DST.read_text(encoding="utf-8") if DST.exists() else ""
        if cur != text:
            print(f"STALE: {DST.relative_to(ROOT)}")
            return 1
        print("up to date")
        return 0
    DST.parent.mkdir(parents=True, exist_ok=True)
    DST.write_text(text, encoding="utf-8")
    print(f"wrote {DST.relative_to(ROOT)} ({n} cases)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
