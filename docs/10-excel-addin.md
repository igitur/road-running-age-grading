# 10 — The Excel add-in

The Python library and CLI in this repo grade one performance at a time (or a
file). A club secretary has 180 finishers in a spreadsheet and wants one column
of age grades. That is what [`xll/`](../xll/README.md) is for: a native Excel
add-in (`xll_age_grading.xll`) built on the
[xll](https://github.com/xlladdins/xll) framework, which accepts **columns**.

```excel
=AG.GRADE(B2:B181, C2:C181, D2:D181, E2:E181)     → 180 age grades, spilled
```

Full documentation lives with the add-in:

| Page | Contents |
| --- | --- |
| [xll/README.md](../xll/README.md) | build, install, function list, testing |
| [xll/docs/functions.md](../xll/docs/functions.md) | every function, argument rules, worked examples |
| [xll/docs/ad-hoc-tables.md](../xll/docs/ad-hoc-tables.md) | custom table formats and the alternatives rejected |
| [xll/docs/tables-and-caching.md](../xll/docs/tables-and-caching.md) | where several tables live, and the cache |
| [xll/docs/framework-patches.md](../xll/docs/framework-patches.md) | what had to be patched in the xll framework to build this at all |
| [xll/examples/age-grading-sample.xlsx](../xll/examples/age-grading-sample.xlsx) | a worked workbook: all twelve functions, live, with expected values and an OK/MISMATCH check |

## Design decisions worth recording here

**Vector arguments, checked.** Every data argument is a scalar (broadcast) or a
column; all vectors must be the same length. A mismatch returns `#NUM!` and
`AG.LASTERROR()` names both arguments and both counts — the failure a squad
sheet needs, not Excel's silent broadcasting, which would pair one athlete's age
with another's time.

**Four editions compiled in.** 2025, 2020, 2015 and 2010 are baked into the
`.xll` (68 kB of floats, generated from `data/mldr_road.json` by
`xll/tools/gen_tables.py`). No data file to find, no I/O on the recalculation
path, nothing to version-skew. The fifth argument selects the edition by name
(`"2025"`, `2020`, `latest`), or names a `<name>.csv` sidecar, or takes a range
as an ad hoc table.

**Cached, in three tiers.** Compiled editions (never loaded), sidecar CSVs
(parsed on first use, held until `AG.CACHECLEAR()`), and ad hoc ranges (parsed
once and keyed by a 64-bit hash of their contents, so editing the range cannot
give a stale answer). One process-wide registry, mutex-guarded, with counters in
`AG.CACHEINFO()`.

**Two table layouts, auto-detected.** A matrix layout that is one column away
from the official `Age Factors` sheet (add `Sex`, paste the open standards), and
a long layout for machine-generated tables. Open standards may be omitted, in
which case the built-in 2025 standard for that distance is used.

**Arithmetic unchanged.** The add-in implements exactly the lookup and grading of
[03-algorithm.md](03-algorithm.md) — bilinear in age and distance, interpolate
the factors and then divide — including the age clamps and the refusal to answer
outside 1 mile … 200 km.

## Verification status

| What | How | Result |
| --- | --- | --- |
| core arithmetic | 462 ground-truth cases from the verified Python implementation (`xll/tools/gen_expectations.py`) | factors match to 2e-6, percentages to 0.002 pp |
| argument handling | 555 assertions: broadcast, alignment errors, blank rows, bad rows, cache behaviour, both ad hoc layouts, sidecar CSVs | pass |
| the `.xll` itself | `make verify` audits the PE export table and imports | 12 functions + the Excel entry points exported; imports only system DLLs |
| **loading it in Excel** | not possible on a Linux host | **untested** — see below |

The marshalling layer (`xll/src/xll_age_grading.cpp`) is the only code that
touches Excel types. It is deliberately thin — convert `XLOPER12` to plain cells,
call the tested API, convert back — but "the add-in loads and spills in Excel
365" remains an unverified claim until someone runs it on Windows.

## What the VBA in the original workbook did, and what changed

| Original (`MLDRRoadFactors2025.xlsm`) | Add-in |
| --- | --- |
| `PWWRSpeed(dist, time, age, gender)` — one performance, scalars only | `AG.GRADE` accepts columns |
| `AgeFactor(event, age, gender)` — exact event name, case-insensitive | same, plus distance in km and aliases |
| `IAgeFactor(dist, age, gender)` — interpolates distance | same interpolation, plus a refusal outside the published range |
| `age As Integer` — silently rounds a fractional age | ages are doubles, interpolated properly |
| one edition (the file's own) | four editions, selected by argument |
| no caching (Excel recalculates the UDF per cell) | parsed tables cached; a lookup is an array index |

## Building it

```console
$ cd xll && make shim && make        # needs mingw-w64 + the xll library
$ make test                          # 555 assertions, no Excel needed
```

CI runs `make test` plus the two generator freshness checks; building the `.xll`
needs the mingw-patched xll library and is a local step
([07-implementation.md](07-implementation.md) covers the patches that library
needs).
