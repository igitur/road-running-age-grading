# BRRAG — Botha's Road Running Age Grading

Age grading on the USATF MLDR 2025 road tables. The Python package, the
CLI and the PyPI distribution are called `brrag`; the repository keeps its
name and URL.

[![check](https://github.com/igitur/road-running-age-grading/actions/workflows/check.yml/badge.svg)](https://github.com/igitur/road-running-age-grading/actions/workflows/check.yml)

Reference documentation and a verified implementation of **road-running age
grading** on the USATF Masters Long Distance Running (MLDR) 2025 tables.

You give it a sex, an age, a distance and a time. It tells you the **age-graded
time** and the **age grade percentage** — one number that lets a 12-year-old's
5 km and a 72-year-old's marathon be compared on the same scale.

```console
$ brrag 40:00 --age 40 --sex M --distance 10k
factor             0.9636
age-graded        38:32.6
age grade           68.49%

$ brrag 32:00 --age 65 --sex M --distance 10k
factor             0.7761
age-graded        24:50.1
age grade          106.30%      # above 100% = better than the age standard
```

## Install

```console
$ pip install brrag
$ brrag 40:00 --age 40 --sex M --distance 10k
```

Stdlib-only, no dependencies, and the wheel carries its own tables so it works
offline. Versions come from the git tag; see
[docs/11-releasing.md](docs/11-releasing.md).

## Where to start

| If you want to… | Read |
| --- | --- |
| Understand the idea and the numbers | [docs/01-concepts.md](docs/01-concepts.md) |
| See what the 2025 tables contain | [docs/02-tables-2025.md](docs/02-tables-2025.md) |
| **Grade a time (the algorithm)** | [docs/03-algorithm.md](docs/03-algorithm.md) |
| Know how the tables were built | [docs/04-methodology.md](docs/04-methodology.md) |
| Trust or audit the data | [docs/05-provenance.md](docs/05-provenance.md) |
| Handle weird inputs | [docs/06-edge-cases.md](docs/06-edge-cases.md) |
| Write your own implementation | [docs/07-implementation.md](docs/07-implementation.md) |
| Check our claims | [docs/08-validation.md](docs/08-validation.md) |
| Know the revision history / what 2026 needs | [docs/09-history.md](docs/09-history.md) |
| **Grade a whole club in Excel** | [docs/10-excel-addin.md](docs/10-excel-addin.md) |
| Release or publish a version | [docs/11-releasing.md](docs/11-releasing.md) |

Full index: [docs/index.md](docs/index.md).

## Quick use (Python)

```python
from brrag import table, format_time

t = table(2025, "M")                       # or table(2025, "F")
g = t.grade("M", 40, 40 * 60, dist_km=10)  # 40:00 for 10 km at age 40
print(g.factor, g.percent)                 # 0.9636  68.49
print(format_time(g.age_graded_s))         # 38:32.6
```

No dependencies outside the standard library for the library itself
(`openpyxl` is only needed by the table-extraction and verification tools).

## In Excel

`xll/road_running_age_grading.xll` is a native add-in for grading a whole squad at once:

```excel
=RRAG.GRADE(B2:B181, C2:C181, D2:D181, E2:E181)     180 age grades, spilled
=RRAG.BLOCK(B2:B181, C2:C181, D2:D181, E2:E181)     factor, standards, graded time, percent
```

Four editions are compiled in (2025/2020/2015/2010), the fifth argument selects
one or names a custom `<name>.csv` table, and a range passed there is used as an
ad-hoc table. Build and install: [xll/README.md](xll/README.md); design notes:
[docs/10-excel-addin.md](docs/10-excel-addin.md).

## Getting started

```console
$ git clone https://github.com/igitur/road-running-age-grading.git
$ cd road-running-age-grading
$ make setup          # .venv + openpyxl/oletools/pypdf
$ make check          # the full validation suite
```

The repo ships `data/mldr_road.json`, so the library and CLI work immediately
with nothing but Python 3.10+. `make fetch` downloads the two source artefacts
and clones the upstream tables repository when you want checks B and C to run
(after a fresh clone they are already present, since the artefacts are committed).

## Layout

```
data/mldr_road.json        2025 (+2020/2015/2010) factors, extracted and hashed
data/source_sha256.txt     hashes of every source artefact we read
brrag/                   reference implementation (core.py, ui.py, cli.py)
tools/extract_tables.py    pull factor tables out of the calculator page -> JSON
tools/js_oracle.js         run the *published calculator's own JS* under Node
tools/verify.py            three-way validation harness (A/B/C)
tools/reproduce_curve.py   rebuild each factor curve from its 10 fitted parameters
tools/render_wiki.py       docs/*.md -> wiki/*.html (no JS, no CDN)
xll/                       native Excel add-in: columns in, age grades out
docs/                      the documentation set (Markdown; source of truth)
page.html                  archived copy of the calculator page we read
MLDRRoadFactors2025.xlsm   archived copy of the official factors workbook (VBA)
```

Generated or fetched, not committed: `wiki/` (`make wiki`), `raw/` (`make unpack`),
`repo/` and `notes/` (`make fetch` + `pypdf`).

`make help` lists the tasks; `make all` re-downloads the sources, re-extracts the
data, validates it, reproduces the curves and re-renders the wiki.

## Verify it

```console
$ make check
A. exact-event grid: 4224 lookups, 0 mismatches
B. JS oracle: 1412 requests, 0 mismatches, worst percent delta 0.000000 pp
C. standards file: 4224 cells, 0 mismatches, 18 known anomalies
RESULT: PASS
worst absolute error across the curves that match exactly: 0.0001
links: 0 problem(s)
```

Details and what each check catches: [docs/08-validation.md](docs/08-validation.md).

## Reading it as a wiki

The Markdown in `docs/` is the source of truth — it versions with the data, diffs
cleanly, and renders on GitHub. If you would rather click through it, render the
HTML copy and serve it:

```console
$ .venv/bin/python tools/render_wiki.py      # writes wiki/*.html
```

Twelve self-contained pages, a sticky sidebar, no JavaScript, no CDN, no build
step beyond that one command — which is why it drops straight into the existing
Caddy static-site setup if you want it online.

## Status of the tables

The 2025 road tables were approved by the USATF MLDR Council on **2025-01-10**;
the published workbooks are dated **2025-07-27**. The tables are re-fitted
roughly every five years (2010 → 2015 → 2020 → 2025), so treat 2025 as current
and expect a 2030 revision. Everything in this repo is pinned to the published
2025 artefacts by SHA-256 — see [docs/05-provenance.md](docs/05-provenance.md).

One caveat worth knowing up front: the *working* spreadsheets shipped in the
upstream repo (`maleRoad2025.xlsx`, dated 2025-07-25) do **not** reproduce the
published male 5 km / 10 km curves. The published factor workbook, the
calculator and the `…Std2025.xlsx` standards files all agree with each other;
the male working file is one revision behind. [docs/05-provenance.md](docs/05-provenance.md)
has the numbers.

## Licence / attribution

**Code and prose: MIT.** Third-party components keep their own terms — the factor
tables are CC0-1.0, the xll framework is MIT, the GCC runtime inside the .xll is
GPLv3 with the Runtime Library Exception, and the verification inputs are not
ours to license. [THIRD-PARTY.md](THIRD-PARTY.md) lists every one of them with the
evidence.

Tables compiled by **Alan Jones** (alanjones@grests.com) with single-age bests
by **Tom Bernhard**; approved by the USATF MLDR Council. Calculator by
**Howard Grubb** (howardgrubb.co.uk). Upstream repository:
<https://github.com/AlanLyttonJones/Age-Grade-Tables>. Cite the upstream tables,
not this repo, when publishing results.
