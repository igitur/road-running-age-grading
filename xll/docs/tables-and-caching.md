# Where the tables live, and why it is cached

Three questions to answer: where do several editions live, where do custom
tables live, and what stops us paying for it on every recalculation.

## Short version

| Tier | Storage | Loaded | Cached | Who it is for |
| --- | --- | --- | --- | --- |
| 1 | **compiled into the .xll** | never — it is code | n/a | the four published editions: 2025, 2020, 2015, 2010 |
| 2 | **`<name>.csv` beside the .xll** | first use | until `AG.CACHECLEAR()` | club handicaps, trial tables, a future edition |
| 3 | **a range passed as the 5th argument** | first call | keyed by a hash of the range | one-off tables, what-if experiments |

Everything is held in one process-wide registry, behind a mutex, with counters
you can read from a cell (`AG.CACHEINFO()`).

## Tier 1 — compiled in

All four published editions are baked into the add-in as `float`:
4 editions × 2 sexes × 22 distances × 96 ages = 16 896 factors ≈ **68 kB**, plus
the source text of the generated header. `src/ag_tables_generated.h` is produced
from `../data/mldr_road.json` by `tools/gen_tables.py`, which is the same JSON
the Python implementation and the CLI use — one source of truth, three consumers.

Why bake rather than ship a data file:

- **Nothing to find, nothing to break.** The `.xll` is self-contained: copy one
  file to another PC and it works. No path configuration, no "table not found"
  on a locked-down laptop, no version skew between add-in and data.
- **No I/O on the recalculation path.** A lookup is an index into a constant
  array; there is no parsing, no file handle, no encoding question.
- **Immutable by construction.** An edition cannot drift, because changing it
  means rebuilding the add-in — which is exactly the review gate you want on a
  published table.
- 68 kB is nothing next to the 1.3 MB the PE format costs anyway.

Cost: adding an edition needs a rebuild. That is what tier 2 is for.

## Tier 2 — sidecar CSVs

Drop `<name>.csv` in any of these and refer to it by `<name>`:

1. the folder holding the `.xll`
2. `<xll folder>\tables\`
3. `%APPDATA%\aggrade\`
4. `%APPDATA%\aggrade\tables\`

The first match wins. The file format is the **matrix ad hoc format**
([ad-hoc-tables.md](ad-hoc-tables.md)) — the same parser, so a table that works
in a range works as a file, and vice versa. A CSV can be edited in Excel and
saved back; the parser handles quoted fields.

```csv
Sex,Event,OpenStd,30,35,40,45,50,55,60
M,10 k,26:24,1,0.98,0.96,0.93,0.89,0.85,0.81
F,10 k,28:46,1,0.98,0.95,0.92,0.88,0.83,0.78
```

```
=AG.GRADE(B2:B181, C2:C181, D2:D181, E2:E181, "bellville-handicap")
```

Loaded on first use and kept. After editing a CSV, run `=AG.CACHECLEAR()` (or
restart Excel). Deleting the file has no effect until the cache is cleared; that
is deliberate — a shared workbook must not change its answers because someone
renamed a file mid-session.

Rejected for this tier: a JSON schema (needs a JSON parser in the add-in and is
not editable in Excel), an `.xlsx` sidecar (needs a whole spreadsheet reader and
OLE/zip support), a Windows registry blob (invisible and hard to version).

## Tier 3 — ad hoc ranges

A range in the fifth argument is parsed once and cached under a **64-bit FNV-1a
hash of its cell contents and shape**. Two consequences:

- A column of 5 000 formulas pointing at the same range pays for one parse.
- Editing the range produces a different hash, so stale results are impossible.
  The cache cannot be wrong; it can only be big.

The cache is an LRU of **16 ranges** (configurable in code). Sixteen distinct
tables in one workbook is far beyond what a club needs; the limit stops someone
poisoning memory by dragging a volatile range into every cell.

Sizes: one 44-row × 99-column table is ~4 300 cells ≈ 100 kB as
`Cell` objects. Sixteen of those is ~2 MB — acceptable for a desktop add-in.
Hits and misses are visible in `=AG.CACHEINFO()`.

## What is cached, precisely

| Lookup | Key | Lifetime |
| --- | --- | --- |
| edition by name (`"2025"`) | the name | materialised once at start-up from the compiled arrays |
| CSV table | the name | until `AG.CACHECLEAR()` |
| ad hoc range | content hash | LRU, 16 entries, until `AG.CACHECLEAR()` |

A **failed** lookup is not cached, so fixing a typo in a table name works
immediately.

## Concurrency

Excel can recalculate on several threads. The registry is protected by a mutex
and the functions are **not** registered as thread-safe (`Args::ThreadSafe()` is
deliberately absent), so Excel calls them on its calculation thread. That is the
conservative choice: it keeps the result buffers and `AG.LASTERROR()`'s buffer
single-threaded, at no measurable cost — a lookup is a few hundred nanoseconds.

## Number formats worth knowing

- Factors are stored as `float` (published precision is 4 decimal places, float
  carries 7 significant digits, so nothing is lost) and are computed in `double`.
- Open standards are stored in **seconds**; `AG.STANDARD` converts to an Excel
  time value on the way out.
- The generated header rounds nothing: `data/mldr_road.json` holds the published
  values exactly, and `gen_tables.py --check` fails CI if the header and the JSON
  disagree.
