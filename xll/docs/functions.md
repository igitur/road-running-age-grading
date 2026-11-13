# Function reference

Twelve functions. The six grading ones take the same first four arguments and an
optional fifth; the diagnostics ones take nothing or just the table argument.

Everything returns a **dynamic array**. A scalar in, a 1×1 out; columns in,
columns out — so one formula per column grades the whole squad.

## Conventions

### One argument, one data type

| Argument | Scalar | Column |
| --- | --- | --- |
| `sex` | `"M"` | `B2:B181` |
| `age` | `40` | `C2:C181` |
| `distance` | `10` or `"10k"` | `D2:D181` |
| `time` | `0:40:00` / `"40:00"` / `2400` | `E2:E181` |
| `percent` | `75` | `F2:F181` |
| `table` | `"2025"` / `2025` / `"latest"` | a range (custom table) |

A scalar broadcasts. Every *vector* must be the same length; otherwise the call
returns `#NUM!` and `AG.LASTERROR()` says something like
`row 1: time has 2 values but age has 3; every vector argument must be the same length`.

### Times

Three ways to say forty minutes, all equivalent:

| You type | Excel stores | Treated as |
| --- | --- | --- |
| `0:40:00` (formatted as time) | 0.0277… | Excel time value |
| `"40:00"` (text) | text | `mm:ss` |
| `2400` (a plain number) | 2400 | **seconds** |

The rule for numbers: **below 1 is an Excel time value, 1 or above is seconds.**
A serial of 2400 would be six and a half years, so there is no ambiguity in
practice. Times returned by `AG.GRADEDTIME`, `AG.STANDARD` and `AG.TIMEFORPCT`
are Excel time values — format the column as `[h]:mm:ss`, or multiply by 86400
for seconds.

### Distances

A number with a unit, or one of the two races by name:

| You type | Distance |
| --- | --- |
| `10k`, `10 km`, `10 kilometer`, `10 kilometers`, `10 kilometre`, `10 kilometres` | 10 km |
| `6.2 m`, `6.2 mile`, `6.2 miles` | 6.2 miles = 9.9779 km |
| `half marathon`, `half-marathon` | 21.0975 km |
| `marathon` | 42.195 km |
| `12.5`, or the text `"12.5"` | 12.5 km — interpolated between 12 km and 15 km |

Comparison ignores case and discards **every** space, tab, newline and hyphen
first, so `10 K M`, `HALF-MARATHON` and `10\tkilometres` all mean the same thing.

`m` after a number means **miles**, not metres: the tables are kilometres, and a
road-race distance below one mile has no grade anyway. `10 m` is 16.09 km.

Off-grid distances interpolate linearly between the two nearest published rows,
which is what the published calculator does. Below 1 mile (1.609344 km) and above
200 km there is no answer: the row comes back `#NUM!`.

Anything else is refused — `10kmRoad`, `half`, `hm`, `10kms`, `ten k`. A
misspelt distance that is quietly snapped to a neighbour produces a plausible,
wrong grade, which is worse than an error.

### Errors

| Situation | Result |
| --- | --- |
| any failure at cell level (bad age, unknown event, out-of-range distance) | `#NUM!` in **that row only** |
| vector length mismatch, unknown table, unreadable table range | `#NUM!` for the whole call |
| blank time in a row | row left as `0` — not an error, so partial sheets work |

`AG.LASTERROR()` returns the first failure's explanation. Because results are
returned as numeric arrays (which is what makes them spill), a specific Excel
error type like `#VALUE!` is not available: every failure is `#NUM!`, and the
reason lives in `AG.LASTERROR()`.

---

## `AG.GRADE(sex, age, distance, time, [table])`

The age grade, as a percentage. 100 means "as good as the world-standard mark
for that exact age and sex"; 68.49 means the athlete took 100/68.49 = 1.46× as
long as that standard.

```
=AG.GRADE("M", 40, 10, "40:00")                 → 68.49
=AG.GRADE(B2:B181, C2:C181, D2:D181, E2:E181)   → 180 percentages
=AG.GRADE(B2, C2, D2, E2, "2020")               → graded on the 2020 tables
```

Above 100% is a real answer (a 65-year-old running 32:00 for 10 km scores ~106%).
It is never clamped: a whole age band scoring over 100 is the classic sign that
the table is too soft there.

## `AG.GRADEDTIME(sex, age, distance, time, [table])`

The performance converted to open-class age: `time × factor`, as an Excel time
value.

```
=AG.GRADEDTIME("M", 40, 10, "40:00")    → 0:38:33  (= 38:32.6)
```

## `AG.FACTOR(sex, age, distance, [table])`

The factor from the table, 4 decimal places of meaningful precision. Useful for
sorting a field by "how well did they run for their age" without needing a time.

```
=AG.FACTOR("F", 56, 10)     → 0.8226
```

## `AG.STANDARD(sex, age, distance, [table])`

The **open standard** for the distance — the world-class mark with no age
adjustment (`26:24` for a male 10 km). It does not depend on age; the age
argument is accepted only so the signature matches its siblings.

## `AG.TIMEFORPCT(sex, age, distance, percent, [table])`

The calculator's *Result* button: what time scores the given percentage?

```
=AG.TIMEFORPCT("M", 40, 10, 68.49)      → 0:40:00
=AG.TIMEFORPCT("F", 52, "21.1", 80)     → the half marathon that scores 80%
```

Useful for setting club standards: "a bronze badge is 65% at your age and
distance" — compute the target time per member and paste it into the sheet.

## `AG.BLOCK(sex, age, distance, time, [table])`

Everything in one spill — the function to use when building a report.

| Column | Contents | Format as |
| --- | --- | --- |
| 1 | factor | `0.0000` |
| 2 | open standard | `[h]:mm:ss` |
| 3 | age standard (the 100% time) | `[h]:mm:ss` |
| 4 | age-graded time | `[h]:mm:ss` |
| 5 | age grade % | `0.00` |

```
     A        B     C      D       E            F                              G H I J K
1    Name     Sex   Age    Dist    Time         <one formula in F2, spills to J>
2    A. M.    F     34     10      0:38:12      =AG.BLOCK(B2:B181,C2:C181,D2:D181,E2:E181)
```

Put the five headers in row 1 first (an XLL result cannot carry text labels).

## `AG.TABLES()`

The edition years this add-in can grade with, newest first.

```
=AG.TABLES()      → 2025 / 2020 / 2015 / 2010   (one per row)
```

## `AG.TABLEINFO([table])`

One row, four values: year, number of distances, number of ages, number of sexes
(2 for a published edition, 1 for a single-sex custom table).

```
=AG.TABLEINFO()          → 2025 | 22 | 96 | 2
=AG.TABLEINFO(A1:F40)    → describes your custom table
```

## `AG.CACHEINFO()`

One row, six values: built-in editions, loaded CSV tables, custom ranges held,
cache hits, cache misses, and the custom-range capacity.

Watch `hits` climb while a long column recalculates: the range is parsed once,
not once per cell.

## `AG.CACHECLEAR()`

Drops cached CSV and custom-range tables and returns 1. Run it after editing a
table CSV — the only case where the cache can go stale, since ad hoc ranges are
keyed by a hash of their contents and cannot go stale.

## `AG.LASTERROR()`

The explanation for the most recent failure, or `no error`.

```
=AG.LASTERROR()
→ row 47: distance 500 km is outside the published range 1.609344-200 km
```

Put it next to a column of `#NUM!` and the diagnosis is immediate.

## `AG.VERSION()`

Add-in version and how many editions are built in, e.g.
`aggrade-xll 2025.1 (4 built-in editions)`.

---

## Worked example: a club time trial

```
     A          B     C      D        E        F          G            H
 1   Athlete    Sex   Age    Dist     Time     Grade      Graded       Factor
 2   T. Mokoena  M     47     10       0:39:40  =AG.GRADE(B2,C2,D2,E2)   =AG.GRADEDTIME(...)  =AG.FACTOR(...)
 3   ...
```

To fill all three columns in one go, use `AG.BLOCK` in F2 and copy the formulas
downwards only if you want the per-row form; the array form needs one cell.

Sanity check the output before publishing it: masters cluster in the 50–75%
band, an age grade over 100% should be a genuine outlier, and anything blank
means the row's time was blank.

## Mixing editions

The fifth argument chooses the tables. Grade a 2019 race with `"2020"` — the
edition that was current then — to get the number the club published at the
time, and `"2025"` for the number it would be given now. Percentages move
slightly between editions; always quote the year with the percentage.
