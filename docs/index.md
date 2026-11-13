# Documentation index

A wiki-shaped documentation set for road-running age grading on the USATF MLDR
2025 tables. Written as Markdown in the repo so it versions with the data and
the code, and so every claim can be re-derived and re-checked.

## Read in this order

| # | Page | What it answers |
| --- | --- | --- |
| 01 | [Concepts](01-concepts.md) | What age grading is; open standard, age standard, factor, percentage; why the factor is ≤ 1; what 100% means; how the three formulas are the same formula. |
| 02 | [The 2025 tables](02-tables-2025.md) | The 22 events and their open standards; ages 5–100; the seven-segment shape of a factor curve; which distances are fitted and which are interpolated; worked examples. |
| 03 | [The grading algorithm](03-algorithm.md) | **The core document.** Inputs, the two-axis lookup, the age rule, the distance rule, the percentage, the inverse, and the exact arithmetic in pseudocode. |
| 04 | [How the tables are built](04-methodology.md) | Single-age bests → open standards → the piecewise curve and its 10 fitted parameters → log-distance interpolation for the other distances; how to re-derive a factor from parameters. |
| 05 | [Provenance and integrity](05-provenance.md) | Every artefact we read, with hashes and dates; which source wins when they disagree; the four known inconsistencies and their scope. |
| 06 | [Edge cases and quirks](06-edge-cases.md) | Ages below 5, ages 99–100, distances below 1 mile and above 200 km, fractional ages, the 50 km+ plateau, rounding, naming traps. |
| 07 | [Implementing it](07-implementation.md) | This repo's API and CLI; a porting guide with the data format, plus what to get wrong and how to avoid it. |
| 08 | [Validation](08-validation.md) | Three independent checks (exact grid, JavaScript oracle, standards cross-check), their results, and how to reproduce them. |
| 09 | [History and review process](09-history.md) | 1989 → 2025 revisions, what changed in 2025 and why, and the checklist for producing the next set. |
| — | [Glossary](glossary.md) | Terms, symbols and the names different tools use for the same thing. |
| — | [References](references.md) | Primary sources, papers, upstream repository, contacts. |

## Conventions used throughout

* Distances are **kilometres**; times are **seconds** (integers or floats) when
  it matters, and `h:mm:ss` in prose and examples.
* A *factor* is written `f`, an *open standard* `S_open`, an *age standard*
  `S_age`, an *age grade* `P` (in percent).
* `M` / `F` for sex, `0` = female and `1` = male in the original VBA.
* Numeric claims are reproducible: `tools/verify.py` regenerates the checks, and
  every worked example in these pages was produced by `aggrade` itself.

## Maintenance rule for these documents

If a number appears in prose and can be computed, it must be produced by a tool
in `tools/` rather than typed by hand. When the tables are revised (expected
2030), update `data/mldr_road.json` from the new calculator page, re-run
`tools/verify.py`, then walk [09-history.md](09-history.md#checklist-for-the-next-revision).
