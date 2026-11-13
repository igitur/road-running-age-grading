# 09 — History and review process

Compiled from *Age-Grade History* (Jones, 2025-01-13) plus the artefacts in the
upstream repository.

## Timeline

| Year | Edition | Notes |
| --- | --- | --- |
| 1989 | *Masters Age-Graded Tables* | National Masters News + WAVA. Track & field, long distance, race walking. **Ages 30+ only.** Committee: Charnock, Mundle, Phillips, Miller, Fine, Harvey, Mulkey, Stone, Tymn, C. Miller, Raschker, Sheahen. |
| 1994 | update | Extended to ages **8–19**. |
| 2002–04/06 | WMA 2002 tables ("male 2004 / female 2006") | New curve-fitting method by Alan Jones, working with Rex Harvey (WMA). In-stadium and road events. Male set finished 2004, female 2006. |
| 2009–10 | **WMA/USATF 2010** | Female long-distance tables found *too soft* for older runners — several athletes scored above 100%. Rebuilt using data from Marian and Don Lein. Male tables unchanged since 2004; track tables unchanged since 2004/06. Approved by both WMA and USATF. |
| 2015 | **2015** | Prompted by Kimetto's 2:02:57 marathon (Berlin, 2014-09-28) and a Runner's World blog by Robert James Reese. ARRS (Ken Young) helped evaluate. Approved January 2015 by USATF MLDR and WMA. |
| 2018 | — | Ken Young (ARRS) dies. **Tom Bernhard** takes over producing single-age bests. |
| 2020 | **2020** | Approved 2020-05-20 by the USATF MLDR Council. First edition built from Bernhard's bests. Working files + methodology document published, explicitly so others can fork and re-do it. |
| 2025 | **2025** | Approved 2025-01-10 by MLDR. Improved interpolated-distance scheme (interpolate factors, log-distance weighted, instead of one shared youth factor). April 2025: entries for 1 km and 3 km reportedly added at a user's request (not present in the 2025 calculator/xlsm, which start at 1 mile). Published workbooks dated 2025-07-27. |
| 2030? | next | Expect a ~5-year cadence. |

## What changed in 2025, specifically

* **New single-age bests** from Bernhard for all distances.
* **Records moved**, so whole curves shifted: female 5 km 14:44 → 14:13;
  female half marathon 1:04:31 → 1:02:52; male 5 km 12:51 → 12:49; male
  marathon 2:01:39 → 2:00:35. Female rows changed far more than male rows.
* **Youth fit improved.** In 2020 all distances shared one youth factor; 2025
  interpolates per-age factors in log-distance, which the evaluation document
  says fixed visible youth irregularities at the 8 km and elsewhere.
* **Outliers declared and excluded**: female 5 km age 68; female marathon ages
  63, 77, 82.
* **Target achieved**: several exact 100.0% scores per distance (e.g. female
  5 km at ages 7, 22, 23, 64).

The 2025 evaluation document is worth reading in full: it applies the *new*
bests to the *old* standards, and any value above 100 there is direct evidence
the old standard was too soft.

## How a revision gets approved

1. Jones refits using the new single-age bests and produces candidate standards.
2. Jones + Bernhard evaluate: every age best must score ≤ 100.0, as many ages as
   possible exactly 100.0, outlier decisions stated explicitly.
3. The Masters Long Distance Running (MLDR) Council of USATF votes (2025:
   approved 2025-01-10).
4. Artefacts published: factor workbook, standards workbooks, working files,
   calculator data, and (since 2020) the methodology document.
5. Community tools update: Howard Grubb's calculator, RunScore tables
   (`CreateRunScoreTables.cpp` in the repo), RunSignUp/RunScore integrations.

## Checklist for the next revision

Written so this repo can be updated without re-deriving the process.

- [ ] Obtain the new single-age bests spreadsheet from Tom Bernhard (or
      successor) — one sheet per distance, world record highlighted.
- [ ] Update the `Parameters` sheet: new records, then hand-adjust the
      non-calibration standards until pace vs distance is smooth (plot it).
- [ ] Refit the ten parameters per distance per sex for 5 km, 10 km, half,
      marathon (and the mile, borrowing youth parameters if there is no youth
      data).
- [ ] Recompute the `u` weights if the event list changed:
      `u = (log10 d − log10 d_lo)/(log10 d_hi − log10 d_lo)`.
- [ ] Regenerate all 22 rows per sex; round factors to 4 dp.
- [ ] Run the three acceptance tests: no age best above 100.0; several ages at
      exactly 100.0; pace-vs-distance plots free of bumps.
- [ ] Apply the new bests to the *previous* standards and publish the comparison
      (this is how the community sees what moved).
- [ ] Get MLDR Council approval; record the approval date in the workbooks.
- [ ] Publish factor + standards workbooks, working files, RunScore tables, and
      send Howard Grubb the new factor arrays for the calculator page.
- [ ] **Update this repo**: re-fetch the calculator page, run
      `tools/extract_tables.py`, `tools/verify.py --all`,
      `tools/reproduce_curve.py`; refresh `data/source_sha256.txt`, the parameter
      table in [04-methodology.md](04-methodology.md), the open-standards table
      in [02-tables-2025.md](02-tables-2025.md), the worked examples, and the
      anomaly list in [05-provenance.md](05-provenance.md).
- [ ] Rename/duplicate the docs for the new edition rather than overwriting, so
      that "68.49%" always has a year attached.

## Watch items for the next edition

* Whether the 1 km / 3 km distances actually appear in the published data
  (2025 documentation claims them; the calculator does not carry them).
* Whether the male working file is brought back in step with the published
  tables ([05-provenance.md](05-provenance.md#c-male-working-file-vs-published-tables)).
* Whether the stale age-5 row in `AgeStdSec` is fixed
  ([05-provenance.md](05-provenance.md#a-agestdsec-has-a-stale-age-5-row-17-events)).
* Whether the VBA UDFs drop their `age As Integer` signature.
* Whether WMA re-asserts control of road tables, which would change the
  authority field in `data/mldr_road.json`.
