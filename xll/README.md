# `xll` — the Excel add-in

A native Excel add-in that grades road-running performances by age and sex on
the USATF MLDR tables. Built on the [xll](https://github.com/xlladdins/xll)
library; cross-compiled with mingw-w64, so no Windows machine is needed to build
it.

It exists because the published VBA macros grade **one** performance at a time
(`=PWWRSpeed(dist, time, age, gender)`), which is no use for a club secretary
with 180 finishers in a spreadsheet. Every function here takes columns.

```
=AG.GRADE(B2:B181, C2:C181, D2:D181, E2:E181)
```

One formula, 180 age grades, spilled down the column.

---

## What it is not

- Not a VBA macro: it is a compiled add-in, ~10⁴× faster per call than a UDF
  that crosses the COM boundary, and it works with dynamic arrays.
- Not a fork of the tables: the numbers are the published ones, extracted from
  the same source as the Python implementation in this repo and verified against
  it (462 ground-truth cases, see [Testing](#testing)).
- Not a replacement for `aggrade` in scripts: the CLI and the Python library in
  the parent directory do the same arithmetic for pipelines.

## Functions

| Function | Returns |
| --- | --- |
| `AG.GRADE(sex, age, distance, time, [table])` | age grade **percent** |
| `AG.GRADEDTIME(sex, age, distance, time, [table])` | age-graded **time** (Excel time value) |
| `AG.FACTOR(sex, age, distance, [table])` | the age **factor** (0 < f ≤ 1) |
| `AG.STANDARD(sex, age, distance, [table])` | the **open standard** for the distance |
| `AG.TIMEFORPCT(sex, age, distance, percent, [table])` | the time that scores `percent` |
| `AG.BLOCK(sex, age, distance, time, [table])` | **five columns**: factor, open standard, age standard, graded time, percent |
| `AG.TABLES()` | edition years available |
| `AG.TABLEINFO([table])` | year, distances, ages, sexes in a table |
| `AG.CACHEINFO()` | cache counters |
| `AG.CACHECLEAR()` | drop cached tables, return 1 |
| `AG.LASTERROR()` | why the last call failed (text) |
| `AG.VERSION()` | add-in version (text) |

Full reference with examples: [docs/functions.md](docs/functions.md).
Custom tables: [docs/ad-hoc-tables.md](docs/ad-hoc-tables.md).
Where tables live and how caching works: [docs/tables-and-caching.md](docs/tables-and-caching.md).
**What had to be patched in the xll framework to build this at all:**
[docs/framework-patches.md](docs/framework-patches.md).

## Arguments

Every data argument is **either a scalar (broadcast) or a column of the same
length as the others** — the rule you would expect for a squad sheet:

| Argument | Accepts |
| --- | --- |
| `sex` | `M`, `F`, `Male`, `Female`, `Men`, `Women`, `1`, `0` |
| `age` | age on race day, 1–120; clamped to the table's 5–100 |
| `distance` | km (`10`, `12.5`) or an event name (`10k`, `10kmRoad`, `half`, `marathon`, `5 Mile`) |
| `time` | Excel time (`0:40:00`), text (`40:00`), or **seconds** (`2400`) |
| `table` | optional: edition name (`2025`, `2020`, `2015`, `2010`, `latest`), a `<name>.csv` sidecar, or **a range** holding a custom table |

Length mismatches never silently misalign rows: they return `#NUM!` and
`AG.LASTERROR()` names both arguments and both counts.

## Sample workbook

`examples/age-grading-sample.xlsx` is a worked workbook that exercises all twelve
functions: a twelve-athlete squad graded with columns and with one `AG.BLOCK`
call, every scalar function, the four editions, the vector rules and their
errors, both custom-table layouts, time formats, and a reference sheet. Live
formulas sit next to the expected answers (grey) with an automatic OK/MISMATCH
verdict, so the workbook doubles as an acceptance test: load the add-in, open it,
and look for a MISMATCH.

```console
$ make sample                 # regenerate from the verified implementation
$ python3 examples/build_sample_workbook.py --check   # CI: is it stale?
```

Multi-value functions spill as Excel 365 dynamic arrays — no Ctrl+Shift+Enter,
no curly braces. openpyxl cannot express that on its own, so the build
post-processes the saved file the way Excel itself does it: each anchor becomes a
one-cell array formula marked `cm="1"`, backed by an `xl/metadata.xml` part
declaring `XLDAPR`/`fDynamic="1"`. Without that mark Excel reads a bare formula as
pre-365 and rewrites it to `=@AG.GRADE(…)`, which spills nothing. The workbook
also sets `calcMode="auto"`, `fullCalcOnLoad` and `forceFullCalc`.

A workbook cannot force the mode on its own, though: Excel gives every workbook in
a session the mode of the **first** one opened, ignoring what the later files say
([Microsoft's own description](https://learn.microsoft.com/en-us/troubleshoot/microsoft-365-apps/excel/current-mode-of-calculation)).
The forced recalculation on load means the values are still correct in a manual
session; only recalculation after an input changes stops. If Excel shows Manual,
close all workbooks and open this one, or set File > Options > Formulas >
Workbook Calculation to Automatic. The build refuses to write a file
that would make Excel repair itself or show `#SPILL!`: no merged range may
overlap an array's output area, no two merges may overlap, and nothing may sit in
a cell a formula is meant to spill onto. `--check` runs the same validation on
the committed file.

Every number in it is computed by `aggrade` at build time — nothing is typed by
hand, so it can be rebuilt after any change to the tables. The custom-table
expected values were additionally checked against the C++ itself
(`test_main.cpp`), and the published-table values against the calculator's own
JavaScript (23 cases, worst delta 0.006 pp).

## Build

```console
$ cd xll
$ make shim      # case-fixing symlinks the mingw build needs (once)
$ make           # native tests, then the .xll, then an export/import audit
$ make test      # 554 assertions, no Excel needed
$ make verify    # dump the PE export and import tables
```

Requires `gcc-mingw-w64-x86-64`, `g++-mingw-w64-x86-64`, and the xll library
checked out at `$(XLL_DIR)` (default `~/code/xll`). The published library does
not compile with GCC; bring it to a working state with

```console
$ ./tools/apply-xll-patches.sh          # clones upstream if absent, then patches
```

Seven files, 46 lines — see [docs/framework-patches.md](docs/framework-patches.md)
for each fix, the compiler error it removes, and the shims that live outside the
library.

`make` produces `xll_age_grading.xll` (1.3 MB, imports only KERNEL32, USER32,
ADVAPI32, SHLWAPI and msvcrt — no libgcc/libstdc++ DLLs to ship).

On Windows with Visual Studio, add the same `src/*.cpp` files to a copy of the
`xll_template` project and define `_M_X64`; the code is standard C++20 plus the
xll headers, and MSVC needs no shim (its filesystem is case-insensitive).

## Install

1. Copy `xll_age_grading.xll` somewhere permanent.
2. `File → Options → Trust Center → Trust Center Settings → Macro Settings →
   Enable VBA Macros` (XLLs count as macros).
3. If it came from another machine, right-click the file → Properties → Unblock.
4. `File → Options → Add-ins → Manage: Excel Add-ins → Go → Browse…` and pick
   the file. It stays loaded afterwards.

Excel caches registrations: after replacing the `.xll` with a new build, close
Excel and reopen it, or unload/reload the add-in, or you will keep calling the
old code.

## Typical club workflow

```
   A      B     C      D        E          F            G          H
1  Name   Sex   Age    Dist     Time       AG.GRADE     Result
2  A. M.   F     34     10      0:38:12    =AG.GRADE(B2:B9,C2:C9,D2:D9,E2:E9)
```

Or one call for the whole report:

| Column | Formula |
| --- | --- |
| factor | `=AG.BLOCK(B2:B181, C2:C181, D2:D181, E2:E181)` |
| open standard | …spills into the next column automatically |
| age standard | … |
| graded time | … |
| percent | … |

Sort by the percent column to find the club champion, or by `factor` to see who
is racing closest to their age standard.

## Testing

`make test` links the same `ag_core.cpp` / `ag_api.cpp` that go into the
`.xll` and checks 554 assertions:

| Group | What it proves |
| --- | --- |
| ground truth | 462 (sex, age, distance, time) cases match the verified Python implementation to 2e-6 in the factor |
| smoke | the canonical cases: M 40, 10 km, 40:00 → 68.49%; F 56 → 87.42%; M 75 marathon → 65.13%; above-100% is not clamped |
| vectors | broadcast, four-vector columns, length mismatch, blank rows, one bad row does not poison the column |
| tables | name coercion (`2025` numeric and text), `latest`, older editions, unknown name, out-of-range distance, age clamping |
| ad hoc | matrix and long formats agree, OpenStd optional, cache hit on the second call, bad factor/geometry rejected with the row number |
| inverse | `AG.TIMEFORPCT(…, 68.49) → 40:00` |
| diagnostics | `AG.TABLES`, `AG.TABLEINFO`, cache counters, cache clear |
| sidecar | a `<name>.csv` in a search directory loads and grades |

What is **not** tested: loading the `.xll` inside Excel. There is no Excel on
this machine. The export table is audited (`make verify`) and the marshalling
layer is deliberately thin, but "it loads and spills in Excel 365" is an
untested claim until someone runs it on Windows.

## Layout

```
src/ag_core.{h,cpp}            table model, parsing, lookup, cache — no Excel
src/ag_api.{h,cpp}             worksheet-facing API: vectors, validation
src/xll_age_grading.cpp        the only Excel-aware file: XLOPER12 <-> cells
src/ag_tables_generated.h      the four published editions, generated (147 kB)
test/test_main.cpp             native test suite
test/expected.h                ground truth from aggrade, generated
tools/gen_tables.py            data/mldr_road.json -> ag_tables_generated.h
tools/gen_expectations.py      aggrade -> test/expected.h
tools/apply-xll-patches.sh     recreate the mingw-portable xll library
patches/xll-mingw-portability.patch   the 7-file framework patch
xll_age_grading.def            exported symbols (checked against the PE table by make verify)
excel4_compat.cpp              Excel4/Excel4v shim for mingw (see docs)
shim/                          case-fixing header symlinks (generated)
```

## Attribution

Tables: Alan Jones, with single-age bests by Tom Bernhard; approved by the USATF
MLDR Council (2025-01-10). Calculator: Howard Grubb. Cite the upstream tables,
not this add-in, when publishing graded results.
