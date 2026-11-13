#!/usr/bin/env python3
"""gen_tables.py — compile data/mldr_road.json into a C++ header.

The .xll must work with no files on disk, so every published table is baked in.
The whole set is small: 4 editions x 2 sexes x 22 distances x 96 ages of float32
is about 68 kB, which is nothing next to the PE overhead.

    python3 xll/tools/gen_tables.py            # writes xll/src/ag_tables_generated.h
    python3 xll/tools/gen_tables.py --check    # fail if the header is out of date

The generated file is committed so that a Windows/MSVC user never needs Python.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]          # repo root
SRC = ROOT / "data" / "mldr_road.json"
DST = ROOT / "xll" / "src" / "ag_tables_generated.h"

BANNER = """\
// GENERATED FILE — do not edit.
// Produced by xll/tools/gen_tables.py from data/mldr_road.json.
// Regenerate after any change to the tables:  make -C xll tables
"""


def fmt(x: float) -> str:
    """Shortest round-tripping representation, as a float literal."""
    return f"{x!r}f"


def group_editions(data: dict) -> list[dict]:
    """Collapse the flat 'authority year sex' keys into one record per edition.

    Editions are keyed by (authority, year) because both sexes of an edition
    share the event list and the age axis; only the factors differ.
    """
    by_year: dict[tuple[str, int], dict] = {}
    for key, t in data["tables"].items():
        rec = by_year.setdefault((t["authority"], t["year"]),
                                 {"authority": t["authority"], "year": t["year"],
                                  "sex": {}, "ages": t["ages"]})
        if rec["ages"] != t["ages"]:
            raise SystemExit(f"{key}: age axis differs within an edition")
        rec["sex"][t["sex"]] = t

    out = []
    for (_, year), rec in sorted(by_year.items(), key=lambda kv: -kv[0][1]):
        # one event list for the edition; both sexes must agree on it
        reference = rec["sex"].get("M") or rec["sex"].get("F")
        events = {e["event"]: {"name": e["event"], "km": e["distance_km"],
                               "std": {}} for e in reference["events"]}
        for sex, t in rec["sex"].items():
            names = {e["event"] for e in t["events"]}
            if names != set(events):
                raise SystemExit(
                    f"{year}: event lists differ between sexes "
                    f"({sorted(names ^ set(events))})")
            for e in t["events"]:
                d = events[e["event"]]
                # Editions disagree slightly on some distances (2020/2015:
                # 50 mile 80.46736 vs 80.4672; 2010: several one-decimal values
                # such as 42.2 vs 42.195). The event list is shared between the
                # sexes, so keep the first value seen and note any drift: it can
                # only move an interpolated lookup, never an exact one.
                if abs(d["km"] - e["distance_km"]) > 1e-6:
                    print(f"note: {year}/{e['event']} distance differs by sex: "
                          f"{d['km']} vs {e['distance_km']}; using {d['km']}")
                d["std"][sex] = e["open_standard_s"]
        for name, d in events.items():
            for sex in ("F", "M"):
                d["std"].setdefault(sex, d["std"].get("M", d["std"].get("F")))
        rec["events"] = sorted(events.values(), key=lambda d: d["km"])
        out.append(rec)
    return out


def emit(data: dict) -> str:
    editions = group_editions(data)

    out: list[str] = [BANNER, "#pragma once", "", "#include <cstddef>", "",
                      "namespace ag::builtin {", ""]
    out += [
        "struct GenEvent {",
        "    const char* name;",
        "    double distance_km;",
        "    float open_std_f;",
        "    float open_std_m;",
        "};",
        "",
        "struct GenSex {",
        "    int n_events;",
        "    const GenEvent* events;",
        "    int n_ages;",
        "    const int* ages;",
        "    const float* factors;   // n_events * n_ages, event-major; null if absent",
        "};",
        "",
        "struct GenTable {",
        '    const char* name;       // "2025"',
        '    const char* authority;  // "USATF MLDR"',
        "    int year;",
        "    GenSex sex[2];          // 0 = female, 1 = male",
        "};",
        "",
    ]

    # ---- age axes (one symbol per distinct axis) -------------------------
    age_sym: dict[tuple[int, ...], str] = {}
    for rec in editions:
        sym = f"ages_{rec['ages'][0]}_{rec['ages'][-1]}"
        age_sym[tuple(rec["ages"])] = sym
    for ages, sym in age_sym.items():
        out.append(f"inline constexpr int {sym}[] = {{{','.join(map(str, ages))}}};")
    out.append("")

    # ---- per edition: events + factors -----------------------------------
    for rec in editions:
        year = rec["year"]
        out.append(f"inline constexpr GenEvent events_{year}[] = {{")
        for d in rec["events"]:
            out.append(f'    {{"{d["name"]}", {d["km"]!r}, '
                       f'{fmt(d["std"]["F"])}, {fmt(d["std"]["M"])}}},')
        out.append("};")
        out.append("")
        for sex in ("F", "M"):
            t = rec["sex"].get(sex)
            if t is None:
                continue
            tag = f"{year}_{sex.lower()}"
            by_name = {e["event"]: e for e in t["events"]}
            vals: list[str] = []
            for d in rec["events"]:
                e = by_name[d["name"]]
                if len(e["factors"]) != len(t["ages"]):
                    raise SystemExit(f"{year}/{sex}/{d['name']}: factor count mismatch")
                vals.extend(fmt(v) for v in e["factors"])
            out.append(f"inline constexpr float factors_{tag}[] = {{")
            for i in range(0, len(vals), 8):
                out.append("    " + ", ".join(vals[i:i + 8]) + ",")
            out.append("};")
            out.append("")

    # ---- the table list ---------------------------------------------------
    out.append("inline constexpr GenTable tables[] = {")
    for rec in editions:
        year = rec["year"]
        n_ev, n_ag = len(rec["events"]), len(rec["ages"])
        ages = age_sym[tuple(rec["ages"])]
        out.append(f'    {{"{year}", "{rec["authority"]}", {year},{{')
        for sex in ("F", "M"):
            tag = f"{year}_{sex.lower()}"
            if sex in rec["sex"]:
                out.append(f"        {{{n_ev}, events_{year}, {n_ag}, {ages}, "
                           f"factors_{tag}}},")
            else:
                out.append("        {0, nullptr, 0, nullptr, nullptr},")
        out.append("    }},")
    out.append("};")
    out.append("")
    out.append("inline constexpr int n_tables = "
               "static_cast<int>(sizeof(tables) / sizeof(tables[0]));")
    out.append("")
    out.append("}  // namespace ag::builtin")
    out.append("")
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="verify the generated header matches the JSON")
    a = ap.parse_args()

    text = emit(json.loads(SRC.read_text(encoding="utf-8")))
    if a.check:
        current = DST.read_text(encoding="utf-8") if DST.exists() else ""
        if current != text:
            print(f"STALE: {DST.relative_to(ROOT)} — run xll/tools/gen_tables.py")
            return 1
        print(f"up to date: {DST.relative_to(ROOT)}")
        return 0

    DST.parent.mkdir(parents=True, exist_ok=True)
    DST.write_text(text, encoding="utf-8")
    print(f"wrote {DST.relative_to(ROOT)} ({len(text) / 1024:.0f} kB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
