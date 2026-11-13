# Glossary

## Symbols used in these docs

| Symbol | Meaning |
| --- | --- |
| `f` | age factor, in `(0, 1]` |
| `S_open` | open standard, seconds (a.k.a. open-age standard, open class time) |
| `S_age` | age standard, seconds — the time that scores 100% for that age |
| `T` | performance time, seconds |
| `T_graded` | age-graded time = `T × f` |
| `P` | age grade, percent |
| `u` | log-distance interpolation weight, in `[0, 1]` |
| `a, b, c, d, e, f` | age breakpoints of the fitted curve (note: `f` is both the factor symbol and the last breakpoint in the methodology pages — context disambiguates) |
| `A, B, C, D, E, F` | coefficients of the fitted curve; `C` and `D` are derived, the rest are free |

## Terms

**age factor** — the multiplier applied to a performance time to express it at
open-class age. The single number that encodes "how much slower should a
45-year-old be at 10 km".

**age grade / age-graded percentage / age percentage / PLP / `wma%`** — the
percentage score. Different tools call it different names; RunSignUp shows
"Age Percentage", RunScore shows "PLP" in some contexts.

**age-graded time / age-adjusted time** — `T × f`, a time comparable across ages.

**age standard** — the 100% time for a given age and distance (`S_open / f`).
Also called the *age record* in older documents.

**calibration distance** — one of the distances actually fitted to data: 5 km,
10 km, half marathon, marathon (and the mile, fitted with borrowed youth
parameters).

**open standard / open class time** — the distance's world-class mark with no
age adjustment. The numerator of the percentage.

**single-age best** — the best known performance by an athlete of a given exact
age at a given distance. The raw material of the tables.

**plateau** — the range of ages where `f = 1` exactly, spanning the breakpoints
`c` to `d` in the fitted model.

**prime age / open age** — loosely, the plateau; the ages where the world record
is a realistic target.

**interpolated distance** — a distance whose row is computed from the
calibration distances rather than fitted: 6 km, 4 mile, 8 km, 5 mile, 7 mile,
12 km, 15 km, 10 mile, 20 km, 25 km, 30 km.

**MLDR** — Masters Long Distance Running Council of USA Track & Field; the
approving body for the road tables since 2020.

**WMA / WAVA** — World Masters Athletics (formerly World Association of Veteran
Athletes); governed the earlier editions.

**ARRS** — Association of Road Racing Statisticians; supplied single-age bests
until 2018 (Ken Young).

## Event-name mapping

The same row is called different things in different artefacts. Use this table
when joining data across them.

| Calculator JS | xlsm / factor sheet | Standards sheet header | Distance (km) |
| --- | --- | --- | ---: |
| `1MileRoad` | `1MileRoad` | `1 Mile` | 1.609344 |
| `5kmRoad` | `5kmRoad` | `5 km` | 5 |
| `6kmRoad` | `6kmRoad` | `6 km` | 6 |
| `4MileRoad` | `4MileRoad` | `4 Mile` | 6.437376 |
| `8kmRoad` | `8kmRoad` | `8 km` | 8 |
| `5MileRoad` | `5MileRoad` | `5 MIle` (typo) | 8.04672 |
| `10kmRoad` | `10kmRoad` | `10 km` | 10 |
| `7Mile` | `7Mile` | `7 Mile` | 11.265408 |
| `12km` | `12km` | `12 km` | 12 |
| `15km` | `15km` | `15 km` | 15 |
| `10Mile` | `10Mile` | `10 Mile` | 16.09344 |
| `20km` | `20km` | `20 km` | 20 |
| `Half.Mar` | `Half.Mar` | `H. Mar` | 21.0975 |
| `25km` | `25km` | `25 km` | 25 |
| `30km` | `30km` | `30 km` | 30 |
| `Marathon` | `Marathon` | `Marathon` | 42.195 |
| `50km` | `50km` | `50 km` | 50 |
| `50Mile` | `50Mile` | `50 Mile` | 80.4672 |
| `100km` | `100km` | `100 km` | 100 |
| `150km` | `150km` | `150 km` | 150 |
| `100Mile` | `100Mile` | `100 Mile` | 160.9344 |
| `200km` | `200km` | `200 km` | 200 |

Note the calculator's dropdown *displays* the name with the "Road" suffix
stripped (`1Mile`, `5km`) but the option **value** keeps it. One genuine numeric
drift exists between editions: the 50-mile distance is `80.46736` km in the 2020
table and `80.4672` km in the 2025 table (a 0.16 m difference — irrelevant to any
grade, but a trap if you diff editions by distance). Otherwise all artefacts
agree on distances to the published precision.
