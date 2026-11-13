# BRRAG — Botha's Road Running Age Grading

Age-grade a road-running performance against the **USATF MLDR 2025** tables (and
the 2020, 2015 and 2010 editions), from Python or from the command line.

An age grade answers one question: *how good was that run, for that athlete, at
that age?* It divides your time by the world-standard time for your exact sex and
age, so a 68 % at 40 and a 68 % at 70 are the same quality of performance.

- **The tables are the published ones**, not retyped: they are extracted from
  Alan Jones's USATF MLDR workbook and checked against the published calculator's
  own JavaScript — 4 224 cases, exact to the displayed digit.
- **No dependencies.** Pure standard library, Python 3.10 and later.
- **Both directions.** Grade a time, or find the time that scores a given grade.

```console
$ pip install brrag
$ brrag 40:00 --age 40 --sex M --distance 10k
factor             0.9636
age-graded        38:32.6
age grade          68.49%
```

That reads: a 40-year-old man running 40:00 for 10 km has an **age-graded time of
38:32.6** — the equivalent open-age performance — which is **68.49 %** of the
world standard for his age.

## Install

```console
$ pip install brrag
```

Python 3.10+. Nothing else is installed; `brrag` has no runtime dependencies.

## The percentage is a fraction

`0.6849`, not `68.49`. Every percentage this package returns or accepts is a
fraction out of 1, so it behaves like a spreadsheet percentage: format the cell
`00.00%` and Excel shows 68.49 % without any arithmetic. Multiply by 100 yourself
only when you are printing text, and use `format_time()` when you are printing a
duration.

## From the command line

```console
$ brrag 40:00 --age 40 --sex M --distance 10k
factor             0.9636
age-graded        38:32.6
age grade          68.49%

$ brrag 2:30:00 --age 75 --sex M --event Marathon --show-standard
open standard     2:00:35
age standard    2:55:51.3  (scores 100.0%)
factor             0.6857
age-graded      1:42:51.3
age grade         117.24%
```

Above 100 % is not an error: it means the athlete beat the world standard for
their age, and it is reported rather than clamped.

Times can be written `h:mm:ss`, `mm:ss` or as plain seconds. Distances can be
written `10k`, `10 km`, `6.2 miles`, `half marathon`, `marathon`, or a bare
number of kilometres; `--event` takes an exact table name such as `10kmRoad`.

### Machine-readable output

`--json` prints one object per run:

```console
$ brrag 40:00 --age 40 --sex M --distance 10k --json
{
 "sex": "M",
 "age": 40.0,
 "year": 2025,
 "event": null,
 "distance_km": 10.0,
 "time_s": 2400.0,
 "time": "40:00.0",
 "factor": 0.9636,
 "age_graded_s": 2312.64,
 "age_graded": "38:32.6",
 "percent": 0.6849,
 "percent_display": 68.49,
 "open_standard_s": 1584.0,
 "open_standard": "26:24",
 "age_standard_s": 1643.835616438356,
 "age_standard": "27:23.8",
 "ui_parity": false
}
```

## From Python

```python
from brrag import table

t = table(2025, "M")                    # the 2025 USATF MLDR men's table
g = t.grade("M", 40, 2400, dist_km=10)  # 40 years old, 2400 s = 40:00, 10 km

g.percent        # 0.684931506849315  -> 68.49 %
g.factor         # 0.9636   age factor applied to the open standard
g.age_graded_s   # 2312.64  equivalent open-age time, in seconds
g.standard_s     # 1584.0   open standard for 10 km M
g.age_standard_s # 1643.83  the time that scores 100 % at age 40
```

`grade()` also accepts `event="10kmRoad"` instead of `dist_km`, a fractional age,
and `policy="clamp"` to use the nearest published distance instead of raising on
one outside the table.

### The inverse: what time scores this grade?

```python
>>> from brrag import table, format_time
>>> t = table(2025, "M")
>>> format_time(t.time_for_percent("M", 40, 0.6849, dist_km=10))
'40:00.1'
```

The 0.1 s is the calculator's own display rounding, not a discrepancy.

### The raw row, without grading

```python
>>> t.lookup("M", 45, dist_km=10)
Lookup(factor=0.9261, standard_s=1584.0)
```

### Older editions

```python
>>> from brrag import table
>>> table(2010, "M")            # WMA 2010 — the authority follows the year
>>> table(2020, "F")
```

The same run scores differently in each edition, because the tables were revised:

| Edition | Authority | Factor at 12 km, M40 | Age grade, 40:00 |
|---|---|---|---|
| 2025 | USATF MLDR | 0.9636 | 82.81 % |
| 2020 | USATF MLDR | 0.9651 | 83.02 % |
| 2015 | WMA | 0.9662 | 83.75 % |
| 2010 | WMA | 0.9485 | 85.71 % |

**Always quote the year with a percentage.** A grade without a table year is not
an answer.

```console
$ brrag 40:00 --age 40 --sex M --distance 12k --year 2015 --json
```

### When a distance is not in the table

```python
>>> from brrag import table, OutOfRange
>>> table(2025, "M").grade("M", 40, 2400, dist_km=0.4)
Traceback (most recent call last):
  ...
brrag.core.OutOfRange: 0.4 km is outside the published range 1.609344-200.0 km;
the calculator returns no result (pass policy='clamp' to use the nearest event
instead)
```

The strict policy is the default because inventing an answer between two
published distances would be a guess. `policy="clamp"` is there for when you
want the nearest event deliberately.

## Command reference

| Option | Meaning |
|---|---|
| `time` | performance: `h:mm:ss`, `mm:ss` or seconds |
| `--age` | age in years at race day; fractional ages interpolate |
| `--sex` | `M` or `F` |
| `--distance` | `10k`, `6.2 miles`, `half marathon`, bare km … |
| `--event` | exact table name, e.g. `10kmRoad` |
| `--year` | 2025 or 2020 (USATF MLDR), 2015 or 2010 (WMA) |
| `--json` | machine-readable output |
| `--list-events` | the distances this table covers |
| `--show-standard` | also show the open and age standards |
| `--ui-parity` | reproduce the web calculator's displayed percentage exactly (it rounds the age standard before dividing) |
| `--file` | use a different tables JSON |

## How this is validated

Every number is checked against the published calculator, not against
documentation:

- the factors are extracted from the published workbook and hashed, so a silent
  upstream change is caught;
- the whole grid — 22 events × 96 ages × 2 sexes = **4 224 cells** — is checked for
  exact agreement;
- **1 412 grading cases** are driven through the calculator page's own JavaScript
  and compared with this implementation, worst delta 0.000000 percentage points;
- the generated tables, expectations and documentation are rebuilt in CI and
  required to match the committed files.

The output above is real; run the commands and you will get the same digits.

## The Excel add-in

There is also an Excel add-in — twelve worksheet functions (`RRAG.GRADE`,
`RRAG.TIMEFORPCT`, `RRAG.STANDARD`, …) in a `Road Running` category, for grading a
whole squad in a spreadsheet — but it is **not part of this package** and does not
install with `pip`. It is published on the GitHub repository, together with a
sample workbook that demonstrates every function:

<https://github.com/igitur/road-running-age-grading/releases>

## Documentation

The algorithm, the tables, the edge cases and the validation method are written
up in the repository:

- [Documentation index](https://github.com/igitur/road-running-age-grading/blob/main/docs/index.md)
- [The algorithm](https://github.com/igitur/road-running-age-grading/blob/main/docs/03-algorithm.md)
- [The 2025 tables](https://github.com/igitur/road-running-age-grading/blob/main/docs/02-tables-2025.md)
- [Validation](https://github.com/igitur/road-running-age-grading/blob/main/docs/08-validation.md)

## Licence and attribution

The code and prose are **MIT**. The age factors are **not** mine and are not
relicensed: they are Alan Jones's USATF MLDR tables, with single-age bests by Tom
Bernhard, approved by the USATF Masters Long Distance Running committee, and the
calculator they ship with is Howard Grubb's. The upstream table repository is
**CC0-1.0**, so the values in `brrag/data/mldr_road.json` carry no condition —
the credit below is scholarly, not legal.

Every third-party component is listed, with its licence and where it lands, in
[THIRD-PARTY.md](https://github.com/igitur/road-running-age-grading/blob/main/THIRD-PARTY.md);
this wheel ships it as `dist-info/licenses/THIRD-PARTY.md`. If you publish a
percentage, quote the table year and credit the tables to their authors.
