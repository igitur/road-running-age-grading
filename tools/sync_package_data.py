#!/usr/bin/env python3
"""Copy the table data into the package, so a wheel carries its own tables.

`data/mldr_road.json` is the artefact `tools/extract_tables.py` derives from the
published calculator page. `brrag/data/mldr_road.json` is the same bytes, placed
where `brrag.core.DEFAULT_DATA` looks first when the package is installed rather
than run from a checkout.

    tools/sync_package_data.py          # copy
    tools/sync_package_data.py --check  # fail if the two differ (CI, make check)
"""

from __future__ import annotations

import filecmp
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "data" / "mldr_road.json"
TARGET = ROOT / "brrag" / "data" / "mldr_road.json"


def main(argv: list[str]) -> int:
    check = "--check" in argv

    if not SOURCE.exists():
        print(f"SKIPPED: {SOURCE.relative_to(ROOT)} is missing "
              f"(run `make data` to derive it from page.html)")
        return 0

    if check:
        if not TARGET.exists():
            print(f"STALE: {TARGET.relative_to(ROOT)} does not exist; run `make pkgdata`")
            return 1
        if not filecmp.cmp(SOURCE, TARGET, shallow=False):
            print(f"STALE: {TARGET.relative_to(ROOT)} differs from "
                  f"{SOURCE.relative_to(ROOT)}; run `make pkgdata`")
            return 1
        print(f"up to date: {TARGET.relative_to(ROOT)}")
        return 0

    TARGET.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SOURCE, TARGET)
    print(f"copied {SOURCE.relative_to(ROOT)} -> {TARGET.relative_to(ROOT)} "
          f"({TARGET.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
