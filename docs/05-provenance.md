# 05 — Provenance and integrity

Everything in this repo is derived from four artefacts. This page records what
they are, what each is authoritative *for*, and the four places where they
disagree with each other.

## The artefacts

| # | Artefact | Where we keep it | SHA-256 | Date on it |
| --- | --- | --- | --- | --- |
| A | Calculator page `mldrroad25.html` (JS + embedded 2025/2020/2015/2010 tables) | `page.html` | `78bfb2f6…e51be` | 2025 tables, fetched 2026-11 |
| B | `MLDRRoadFactors2025.xlsm` (official factors workbook, VBA lookup functions) | `MLDRRoadFactors2025.xlsm` | `bf906588…c204e` | "Howard Grubb 1999-2025" |
| C | `MaleRoadStd2025.xlsx` / `FemaleRoadStd2025.xlsx` (published standards) | `repo/2025 Files/` | `f9fc6cdc…6099e` / `3dd4fc6c…60c99` | **Version 2025-07-27** |
| D | Working files `maleRoad2025.xlsx` / `femaleRoad2025.xlsx` | `repo/2025 Files/` | (in the clone) | **male 2025-07-25**, female undated |

Full hashes: `data/source_sha256.txt`. Upstream: `repo/` is a clone of
<https://github.com/AlanLyttonJones/Age-Grade-Tables> (`--depth 1`, single
commit `4aac673`).

Also read, for methodology only (no numbers taken from them):
`Docs/Creating Road Running Age Tables.pdf`, `Docs/Age-Grade History.pdf`,
`Docs/Evaluating 2025 Standards Against 2020 Rankings.pdf`.

## Which source wins

**For grading, the factor table wins.** Precedence, strongest first:

1. **A (calculator) = B (xlsm) for the factor values.** They agree
   cell-for-cell on all 22 events × 96 ages for both sexes — checked in
   `tools/verify.py` check A and by direct comparison. Either can be the
   reference.
2. **C's `Age Factors` sheet** also agrees with A/B on every cell, **except**
   the female mile ages 31–34 (see issue D below) and the male 5 km / 10 km
   derived rows, which are the *published* revision and are therefore correct
   for grading (A and B carry the same values).
3. **C's `AgeStdSec` / `AgeStanHMS` sheets** are derived (`S_open/f`) and
   rounded to whole seconds. Use them only as a cross-check; do not grade from
   them.
4. **D (working files)** are the construction inputs. Use them for parameters
   and for `u` weights, *not* for factor values.

Practical rule: `data/mldr_road.json` is built from A, validated against A, B and
C, and is the only file the library reads.

## The four known inconsistencies

### A. `AgeStdSec` has a stale age-5 row (17 events)

In both published standards files, the **age-5 row** implies a single factor of
**0.6080** — which is the *male 5 km* age-5 factor — for 17 of the 22 events.
Worked example, male:

| Event | Sheet standard at 5 | Implied factor | Factor sheet says |
| --- | ---: | ---: | ---: |
| 4 mile | 1645 s | 0.6079 | 0.5713 |
| 8 km | 2064 s | 0.6080 | 0.5397 |
| half marathon | 5676 s | 0.6080 | 0.4621 |
| marathon | 11900 s | 0.6080 | 0.4414 |
| 5 km | 1265 s | 0.6079 | 0.6080 ✓ |
| 10 km | 3122 s | 0.5074 | 0.5073 ✓ |

Diagnosis: a leftover of the pre-2025 scheme in which *all* distances shared one
youth factor (the 2020 tables did exactly that: age-5 factors ≈ 0.6056 across
every distance). Someone filled one row before the youth curves were re-fitted
per distance, and the row was never regenerated.

Consequence: an age-5 standard taken from `AgeStdSec` is wrong for 17 events and
would grade a 5-year-old far too leniently. **Use the factor sheet.** Check C in
`tools/verify.py` reports these 18 cells as `KNOWN ANOMALY` rather than failing,
so the exception stays visible instead of silently accepted.

### B. Female `AgeStdSec` 10 km, age 100 is wrong

One cell: published 12172 s. The factor sheet gives 0.1477 →
`1726/0.1477 = 11686 s`. The published value corresponds to
`1726/0.1418`, and **0.1418 is the 7-mile age-100 factor** — a one-column paste
error. Single cell, no other impact.

### C. Male working file vs published tables

`maleRoad2025.xlsx` is dated **2025-07-25**; the published workbooks are
**2025-07-27**. The male curves were re-fitted in between, and the working file
was shipped one revision behind:

| Event group | Cells differing | Largest difference |
| --- | ---: | --- |
| 1 mile, half, 25 km, 30 km, marathon → 200 km | 0 / 96 | — (identical) |
| 5 km | 81 / 96 | 0.0547 at age 5 (0.5533 vs 0.6080) |
| 6 km, 4 mile, 8 km, 5 mile (interpolated 5K–10K) | 73–84 / 96 | 0.0127–0.0386 |
| 10 km | 87 / 96 | 0.0065 at age 19 (0.9968 vs 0.9903) |
| 7 mile … 20 km (interpolated 10K–HM) | 57–87 / 96 | ≤ 0.0055 |

So the 07-25 → 07-27 change touched **the 5 km and 10 km curves only** (and
everything interpolated from them); the half marathon and marathon curves are
untouched. We do not know why from the repository alone — the shipped Readme
predates the change.

Impact on a graded result, computed both ways:

| Case | 07-25 factor | 07-27 factor | Age grade, 07-25 | Age grade, 07-27 |
| --- | ---: | ---: | ---: | ---: |
| M, age 19, 10 km, 40:00 | 0.9968 | 0.9903 | 66.21% | 66.65% |
| M, age 5, 5 km, 24:00 | 0.5533 | 0.6080 | 96.52% | 87.83% |

So: under half a percentage point for adults, nearly 9 pp for a 5-year-old.

The **female** working file, by contrast, matches the published female sheet on
every cell of every event, so there is no female version skew.

Nothing is wrong with the published tables here — the trap is only for someone
who opens `maleRoad2025.xlsx`, re-derives factors, and compares with the
calculator.

### D. Female mile, ages 31–34

In the published female factor sheet, ages 31–34 are exactly 1.0000, while the
fitted masters curve (which starts at `d = 30.1`) has already begun:
0.9998, 0.9991, 0.9978, 0.9961. The workbook assembles its youth and masters
formula blocks with a changeover at age 35, so four ages keep the flat value.
Largest effect 0.0039 on the factor — under half a percent, a few tenths of a
percentage point of age grade. `tools/reproduce_curve.py` reports it as a `NOTE`.

### Cosmetic issues worth knowing about

* The female factor sheet is named **`Age Facctors`** (typo) and duplicates the
  `Age` column in both A and B, shifting every distance one column right. The
  male sheet is `Age Factors` with a single `Age` column. Any parser must handle
  both.
* Header labels are inconsistent between sheets: `5 MIle`, `H. Mar`, `1 Mile`,
  `100 Mile`. The calculator's JS event names are different again (`5MileRoad`,
  `Half.Mar`, `1MileRoad`). Mapping table in
  [glossary.md](glossary.md#event-name-mapping).
* The male `Mile` sheet in the working file puts its breakpoints in `I3:I5` and
  `J3:J5` instead of `H3:H5` and `I3:I5`.
* Cells `F4/G4/G5/I4/I5` of the *interpolated* distance sheets (`6K`, `8K`, …)
  hold parameter values that are **not used** — those sheets compute their
  factors by referencing the 5K/10K sheets, e.g.
  `='5K'!$E11*(1-$K$2)+'10K'!$E11*$K$2`.
* The VBA module header still says "2020 factors" although the workbook is the
  2025 edition; and `AgeFactor`/`IAgeFactor` take `age As Integer`, so fractional
  ages are rounded before lookup.

## Reproducing this audit

```console
$ .venv/bin/python tools/verify.py --all          # A, B and C cross-checks
$ .venv/bin/python tools/reproduce_curve.py       # parameters -> factors
$ sha256sum page.html MLDRRoadFactors2025.xlsm \
    "repo/2025 Files/MaleRoadStd2025.xlsx" "repo/2025 Files/FemaleRoadStd2025.xlsx"
```

If a future fetch of the calculator page no longer matches
`data/source_sha256.txt`, the tables may have been revised: re-run
`tools/extract_tables.py`, diff `data/mldr_road.json`, and treat any change as a
new edition rather than a bug.
