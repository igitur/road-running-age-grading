#!/usr/bin/env python3
"""Smoke-test an INSTALLED aggrade: does the wheel carry working tables?

Run this from outside the checkout (the release workflow runs it from /tmp after
`pip install dist/*.whl`) so the source-tree fallback in aggrade.core cannot
answer on the packaged copy's behalf. The failure this exists to catch is a wheel
that imports fine and then reports the tables missing.

    python tools/wheel_smoke.py [expected-version]
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def main(argv: list[str]) -> int:
    expected_version = argv[0] if argv else None
    failures: list[str] = []

    def check(name: str, got, want, tol: float = 1e-9) -> None:
        ok = abs(got - want) <= tol if isinstance(want, float) else got == want
        print(f"{'ok  ' if ok else 'FAIL'} {name}: {got!r}"
              + ("" if ok else f" (wanted {want!r})"))
        if not ok:
            failures.append(name)

    import aggrade
    from aggrade import format_time, table

    print(f"aggrade {aggrade.__version__} from {Path(aggrade.__file__).parent}")
    if expected_version:
        check("__version__", aggrade.__version__, expected_version)

    # The tables must have travelled with the package, not been found beside it.
    data = aggrade.core.DEFAULT_DATA
    packaged = Path(aggrade.__file__).parent / "data" / "mldr_road.json"
    print(f"tables read from {data} ({data.stat().st_size:,} bytes)")
    check("tables live inside the package", str(data), str(packaged))

    tables = aggrade.load_tables()
    check("editions shipped", len(tables), 8)

    g = table(2025, "M").grade("M", 40, 40 * 60, dist_km=10)
    check("M 40 10k 40:00 factor", g.factor, 0.9636, 1e-6)
    check("M 40 10k 40:00 age-graded", format_time(g.age_graded_s), "38:32.6")
    check("M 40 10k 40:00 percent", round(g.percent, 4), 68.4932, 1e-4)

    g2 = table(2025, "F").grade("F", 65, 125 * 60, dist_km=21.0975)
    check("F 65 half 2:05:00 factor", g2.factor, 0.72, 1e-6)
    check("F 65 half 2:05:00 percent", round(g2.percent, 4), 69.8519, 1e-4)

    check("time_for_pct round trip", format_time(
        table(2025, "M").time_for_percent("M", 40, 68.49, dist_km=10)), "40:00.1")

    # An older edition must answer differently, or the edition argument is a lie.
    # The 2020 and 2025 factor curves are close, so compare the open standard too.
    old = table(2020, "M").grade("M", 40, 40 * 60, dist_km=12)
    check("2020 open standard at 12 km", table(2020, "M").event("12km").standard_s, 1923.0, 1e-6)
    check("2025 open standard at 12 km", table(2025, "M").event("12km").standard_s, 1915.0, 1e-6)
    check("2020 percent at 12 km", round(old.percent, 2), 83.02, 0.01)

    # Refusals stay refusals.
    try:
        table(2025, "M").grade("M", 40, 40 * 60, dist_km=500)
    except aggrade.OutOfRange:
        print("ok   out-of-range distance refused")
    else:
        failures.append("out-of-range distance was not refused")
        print("FAIL out-of-range distance was not refused")

    # The console script, which is what a pip user actually gets. Resolve it next
    # to this interpreter: the venv is not on PATH when the parent process
    # launched it by absolute path.
    script = Path(sys.executable).parent / ("aggrade.exe" if sys.platform == "win32" else "aggrade")
    out = subprocess.run([str(script), "40:00", "--age", "40", "--sex", "M",
                          "--distance", "10k", "--json"],
                         capture_output=True, text=True)
    if out.returncode != 0:
        failures.append("console script")
        print(f"FAIL console script exited {out.returncode}: {out.stderr.strip()[:200]}")
    else:
        payload = json.loads(out.stdout)
        check("console script percent", round(payload["percent"], 2), 68.49, 1e-9)

    if failures:
        print(f"\n{len(failures)} failure(s): {', '.join(failures)}")
        return 1
    print("\nall wheel checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
