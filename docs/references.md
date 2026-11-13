# References

## Primary sources

**Calculator** — Howard Grubb, *USATF MLDR Road age-grading calculator 2025*.
<https://www.howardgrubb.co.uk/athletics/mldrroad25.html>
Archived locally as `page.html`. This is the operational definition of the
algorithm used by the running community; the tables are embedded in its
JavaScript.

**Factors workbook (VBA)** — <https://www.howardgrubb.co.uk/athletics/data/MLDRRoadFactors2025.xlsm>
Archived as `MLDRRoadFactors2025.xlsm`. Contains `AgeStandard`, `AgeFactor`,
`IAgeStandard`, `IAgeFactor`, `dist_wrecs`, `PWWRSpeed`. Header comment credits
Howard Grubb 1999–2025 and cites the paper below.

**Tables repository** — Alan Jones, *Age-Grade-Tables*.
<https://github.com/AlanLyttonJones/Age-Grade-Tables>
Cloned to `repo/`. Contains, per edition, the standards workbooks, the working
files, the single-age bests and the methodology PDFs.

**Methodology documents** (in `repo/Docs/`):

* Jones, A. *Creating Road Running Age Tables*, 2024-10-23 — the seven-segment
  curve, the parameter layout, the interpolation scheme.
* Jones, A. *Age-Grade History*, 2025-01-13 — 1989 → 2025 timeline.
* Jones, A. & Bernhard, T. *Evaluating 2025 Standards Against 2020 Rankings*,
  2024-10-27 — acceptance testing, outliers, per-distance commentary.
* *Evaluating 2020 Standards Against 2019 Rankings* — the previous round.

## Academic reference

Grubb, H. J. (1998). *Models for comparing athletic performances.*
**The Statistician (JRSS Series D), 47**, 509–521.
The statistical basis for comparing performances across events, ages and sexes,
and the reference given in the factors workbook's VBA header.

## Related bodies and products

* USA Track & Field, Masters Long Distance Running Council (MLDR) — approving
  body for the road tables since 2020. <https://www.usatf.org>
* World Masters Athletics (WMA, formerly WAVA) — approving body for 2010/2015
  and for track & field and race-walking tables.
  Track calculator: <https://www.howardgrubb.co.uk/athletics/wmatnf23.html>
  Walks: <https://www.howardgrubb.co.uk/athletics/wmawalk20.html>
* Association of Road Racing Statists (ARRS) — single-age bests source until
  2018.
* RunScore — ships derived age-grade tables (`CreateRunScoreTables.cpp` in the
  repo).
* RunSignUp — publishes age grade for results at standard distances; estimated
  to cover 30–40% of US race results (per the history document).

## Contacts

| Who | For |
| --- | --- |
| Alan Jones — alanjones@grests.com | the tables, the fitting, corrections |
| Tom Bernhard — tlbernhard2@gmail.com | single-age bests |
| Howard Grubb — howardgrubb.co.uk | the calculator |

## In this repository

| File | Contents |
| --- | --- |
| `data/mldr_road.json` | 2025/2020/2015/2010 factors and standards |
| `data/source_sha256.txt` | hashes of the four source artefacts |
| `brrag/` | reference implementation |
| `tools/extract_tables.py` | calculator page → JSON |
| `tools/js_oracle.js` | runs the published calculator's JS as an oracle |
| `tools/verify.py` | validation harness (checks A/B/C) |
| `tools/reproduce_curve.py` | curve parameters → factors |
| `raw/` | unzipped `MLDRRoadFactors2025.xlsm` (sheet XML + `vbaProject.bin`) |
