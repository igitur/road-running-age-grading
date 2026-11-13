# 06 — Edge cases and quirks

Everything here has bitten somebody. Each entry says what happens, what the
published calculator does, and what `aggrade` does about it.

## Input boundaries

| Input | Calculator behaviour | `aggrade` behaviour | Comment |
| --- | --- | --- | --- |
| `age < 5` | clamps to the age-5 column | same, silently | No table data exists below 5. Do not extrapolate the youth parabola — it diverges fast. |
| `age = 5 … 100` (integer) | exact cell | exact cell | The normal case. |
| `age` fractional, 5 < age ≤ 99 | linear interpolation between neighbouring columns | same (`age_policy="ui"`) | See the 99–100 quirk below. |
| `age > 100` | clamps to the age-100 column | same, silently | Beyond 100 the underlying single-age bests are thin; the table is not a model of 105-year-olds. |
| `age` fractional in (99, 100] | **uses the age-100 column, no interpolation** | same by default; `age_policy="linear"` interpolates | Off-by-one in the calculator's search loop. Harmless in practice, fatal to a naive parity test. |
| `age` fractional (VBA `AgeFactor`) | the `age As Integer` argument **rounds it first** | not reproduced | The Excel UDF quietly disagrees with the web calculator for fractional ages. |
| `distance < 1 mile` | **no result** (blank fields) | `OutOfRange`; `policy="clamp"` uses the mile row | The calculator's search loop starts at index −1 and never recovers. |
| `distance > 200 km` | **no result** (blank fields) | `OutOfRange`; `policy="clamp"` uses the 200 km row | Off-by-one: its loop pushes the index one past the end. |
| `distance` exactly a listed distance | exact row | exact row | `pfac = 0`. |
| `distance` between two listed rows | linear interpolation in distance | same | Note: linear in distance, not in log-distance. |
| `distance` between 42.195 and 50 km | interpolates between the marathon row and the 50 km row | same | Both rows share the marathon factors, so only the standard moves. |
| `distance ≥ 50 km` | interpolates among rows that all share the marathon factors | same | Effectively: factors from the marathon, standard from the distance. |
| `distance` given in miles by mistake | no detection | no detection | 26.2 (miles) is read as 26.2 km → silently wrong. Guard at your boundary. |
| `time = 0` or negative | blank / rejected | `ValueError` | |
| `time` given as `h:mm:ss` | accepted | accepted (`parse_time`) | One colon = `mm:ss`, two = `h:mm:ss`, none = seconds, `;` also accepted. |
| `sex` missing | JavaScript `setFactors` logs "Missing gender" and produces nonsense | required argument | |

## Numeric quirks

* **Factors are ≤ 1 by construction, never above.** If you ever compute
  `f > 1`, you have mismatched sex tables or read the wrong column.
* **Percentages above 100 are legitimate.** Do not clamp. (`M, 65, 10 km, 32:00`
  → 106.30%.) A percentage far above 100 at a specific age is the classic smell
  of a table that is too soft at that age — that is what triggered the 2010
  women's-table revision.
* **The published UI rounds before dividing.** It converts the age standard to
  `h:mm:ss` (0 dp above an hour, 1 dp above a minute, 2 dp below) and *then*
  divides. Up to ±0.005% of artefact. Use `ui_percent()` for parity, `percent`
  for analysis.
* **Half-up rounding, not banker's rounding.** The calculator's `roundval` is
  `floor(x·10^d + 0.5)/10^d`, and `hms_string` uses it. Python's built-in
  `round()` is banker's and will differ in the 4th decimal of a factor on exact
  ties. `tools/verify.py` uses `floor(...+0.5)` for this reason.
* **4 decimal places is the ceiling of precision.** Published factors carry 1e-4;
  percentages carry about 0.01 pp. Reporting `68.4937%` is false precision.
* **Age standards in the published sheets are whole seconds**, so they differ
  from `S_open/f` by up to ±0.5 s per cell. That is rounding, not error.

## Structural traps

* **The `50 km`+ plateau.** From 50 km upward the factors are the marathon's.
  A 100 km race is therefore graded as "marathon shape, ultra standard". This is
  deliberate but surprising if you assume each distance gets a curve.
* **Independently fitted curves are not monotonic in distance.** At age 60 the
  male half marathon factor (.8082) is lower than both the 10 km (.8136) and the
  marathon (.8143). Do not build logic that assumes ordering.
* **`1/y`, not `y`.** The workbook's second curve is the reciprocal of the
  factor; it is the age standard relative to the open standard. Do not compare
  the two by eye.
* **"Road" in event names.** `1MileRoad`, `5kmRoad`, `6kmRoad`, `4MileRoad`,
  `8kmRoad`, `5MileRoad`, `10kmRoad` carry the suffix; `7Mile`, `12km`,
  `Half.Mar`, `Marathon`, … do not. The calculator strips "Road" for display
  but uses the suffixed name as the option value. Match exactly (case
  insensitively) or fall through to distance interpolation by accident.
* **Track vs road tables are different.** `wmatnf23.html` (track) and
  `wmawalk20.html` (walks) are separate products with different standards and
  different distances. Do not mix them.
* **Age is age on race day**, not age at the end of the year, and not a
  category like "M45". Rounding an age down to a bracket (e.g. all M40–44 to 40)
  throws away most of the accuracy of the table.
* **A 1 km / 3 km distance is not in the road table.** An April-2025 note says
  table entries for 1 km and 3 km were added at a user's request, but the
  2025 calculator page publishes 22 events starting at 1 mile, and the xlsm
  matches. Treat 1 km and 3 km as unsupported (the calculator returns nothing).

## Cross-implementation differences at a glance

| Behaviour | Calculator (JS) | VBA (`MLDRRoadFactors2025.xlsm`) | Published factor sheet |
| --- | --- | --- | --- |
| fractional age | interpolates | rounds (Integer arg) | n/a (integers only) |
| age in (99, 100] | age-100 column | rounds → 100 → age-100 column | n/a |
| distance < 1 mile | no result | linear extrapolation | n/a |
| distance > 200 km | no result | linear extrapolation | n/a |
| distance interpolation | linear in distance | linear in distance | n/a |
| output rounding | 4 dp factor, 2 dp percent | full precision | 4 dp |
| unknown event name | blank | returns 0.0 | n/a |

When two of these disagree, **the calculator is the arbiter**, because that is
what the public, RunScore and RunSignUp results are produced with.
