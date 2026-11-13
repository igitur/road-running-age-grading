# 03 — The grading algorithm

This is the document to implement from. It describes the exact arithmetic of the
published USATF MLDR 2025 road calculator
(<https://www.howardgrubb.co.uk/athletics/mldrroad25.html>), which is also the
arithmetic of the official VBA workbook and of the tables in
`Male/FemaleRoadStd2025.xlsx`. Where the three implementations differ, the
difference is called out.

The reference implementation is `brrag/core.py`; it is verified line-for-line
against the calculator's own JavaScript by `tools/verify.py`
([08-validation.md](08-validation.md)).

---

## Inputs and outputs

**Inputs**

| Name | Domain | Notes |
| --- | --- | --- |
| `sex` | `M` \| `F` | selects the table; `0` = female, `1` = male in the original VBA |
| `age` | real, typically 5–100 | years on race day; fractional allowed |
| `distance` | real > 0, km | or an exact event name if you have one |
| `time` | real > 0, seconds | `h:mm:ss` accepted at the front door, seconds inside |

**Outputs**

| Name | Meaning |
| --- | --- |
| `factor` | `f`, the interpolated age factor for (sex, age, distance) |
| `standard_s` | `S_open`, the open standard for the distance |
| `age_standard_s` | `S_open / f` — the time that scores 100% |
| `age_graded_s` | `time × f` |
| `percent` | `100 × S_open / (time × f)` |

## The whole algorithm

```
grade(sex, age, distance_km, time_s):
    table      = TABLES[sex]
    (i0, i1, pa) = bracket_age(table, age)          # age axis
    (e0, e1, pd) = bracket_distance(table, distance_km)  # distance axis

    # bilinear combination of the four surrounding published cells
    f = (1-pd) * ( (1-pa)*F[e0][i0] + pa*F[e0][i1] )
      +     pd * ( (1-pa)*F[e1][i0] + pa*F[e1][i1] )

    S_open = (1-pd) * STANDARD[e0] + pd * STANDARD[e1]

    S_age  = S_open / f
    graded = time_s * f
    percent= 100 * S_open / (time_s * f)
    return {factor: f, standard_s: S_open, age_standard_s: S_age,
            age_graded_s: graded, percent: percent}
```

That is the complete algorithm. Everything else in this document is the two
`bracket_*` functions and the boundary rules.

Note the ordering: **interpolate the factors, then divide**. It is *not*
equivalent to interpolating the age standards and then dividing — see
[Why not interpolate standards](#why-not-interpolate-standards).

---

## The age axis

The table has one column per integer age, 5 … 100.

```
bracket_age(table, age):
    if age <= 5:            return (0, 0, 0)          # clamp young
    if age >= 100:          return (95, 95, 0)        # clamp old
    i = first index with ages[i] >= age
    return (i-1, i, (age - ages[i-1]) / (ages[i] - ages[i-1]))
```

* **Integer ages are exact.** For `age = 40` this returns `(35, 36, 0.0)` — the
  `0.0` makes the second term vanish, so the stored cell is returned exactly.
  Verify: `age 40 → factor 0.9636`, bit-identical to the table cell.
* **Fractional ages interpolate linearly** between the neighbouring columns.
  `age 40.5` is the midpoint of the age-40 and age-41 cells.
* **Below 5 → age 5's factors. Above 100 → age 100's factors.** No
  extrapolation. Both boundaries are hard clamps in all three implementations.

### The 99–100 quirk (reproduce it or document that you don't)

The published JavaScript clamps as soon as its search index reaches the last
row, which happens one age early:

```
age in (99, 100]  →  uses the age-100 factors, NOT an interpolation of 99↔100
```

`age = 99` still interpolates correctly (it lands on the age-99 cell via
`pa = 1.0`); `age = 99.9` jumps to the age-100 column. Age 100 is unaffected.
The low end has no equivalent gap.

Affected population: fractional ages in the last year only — so in practice
nobody. But if you are asserting equality with the calculator, you must
reproduce it. `brrag` reproduces it by default (`age_policy="ui"`) and offers
`age_policy="linear"` to interpolate normally.

The **VBA workbook** has a different, wider quirk: `AgeFactor(event, age As
Integer, …)` and `IAgeFactor(dist, age As Integer, …)` declare the age as an
`Integer`, so a fractional age is rounded by VBA before any interpolation. The
calculator accepts fractional ages properly. Prefer the calculator's semantics.

---

## The distance axis

Twenty-two distances exist. A request is placed between the two nearest ones.

```
bracket_distance(table, dist):
    if dist < 1.609344 or dist > 200:   # outside the published range
        return NO_RESULT
    i = last index with events[i].distance <= dist
    j = min(i+1, last)
    return (i, j, (dist - events[i].distance) / (events[j].distance - events[i].distance))
```

* **Interpolation is linear in distance**, not in log-distance. Between the
  10 km row (10.0) and the 7 mile row (11.265408), a 10.5 km race sits
  (10.5−10)/1.265408 = **39.5%** of the way along and takes 39.5% of the
  difference between the two rows' factors and standards.
* **Exact distances are exact.** `dist = 10.0` returns the 10 km row with
  `pd = 0.0`.
* **The two ends refuse to answer.** The calculator leaves its fields blank for
  anything under 1 mile and for anything over 200 km. This is a real, deliberate
  consequence of how its search loop terminates — the upper end is an
  off-by-one, but it is the behaviour everyone sees.
* `brrag` raises `OutOfRange` to match (`policy="strict"`, the default) and
  offers `policy="clamp"` to use the nearest end row instead.
* The **VBA workbook** extrapolates at both ends instead of refusing. Three
  implementations, three behaviours — choose explicitly.

### Distances are *not* interpolated from the four calibration distances here

The tables themselves were built by log-distance interpolation between 5 km,
10 km, half and marathon ([04-methodology.md](04-methodology.md)). At runtime
you must **not** redo that interpolation: the 6 km, 8 km, 12 km … rows already
contain the result, and interpolating linearly between the *published* rows is
what the calculator does and what the published numbers were designed for.
Recomputing from the key distances gives a different (and unauthorised) answer.

---

## The percentage

```
percent = 100 * S_open / (time * f)
```

equivalently `100 * S_age / time`, exactly the same value. Two implementation
notes:

1. **`percent` can exceed 100.** Do not clamp it. 106.30% is a legitimate
   answer (see [01-concepts.md](01-concepts.md#percentages-above-100)).
2. **The published UI rounds before dividing.** Its display code is:

   ```
   S_age_shown = round to 2dp (if < 60 s), 1dp (if < 1 h), 0dp (otherwise)
   percent     = 100 * S_age_shown / time      → shown to 2dp
   ```

   That introduces up to ±0.005% of artefact from display rounding alone. Use
   the unrounded value for analysis; use `brrag.ui.ui_percent()` when you need
   to match the web page's digits exactly. `tools/verify.py` does the latter,
   which is why it can assert a 0.000000 pp difference.

## The inverse: time for a given percentage

The calculator's *Result* button answers "what time scores X%?":

```
time = S_age / (percent / 100)
```

Both the age-graded and the open time follow from the same lookup
(`T_graded = S_open / (percent/100)`). In `brrag`: `Tables.time_for_percent()`.

---

## Why not interpolate standards

Consider a 7 km run, between 6 km and 8 km. Two candidate approaches:

* **Interpolate the factors, then compute the standard** (what the calculator
  does): `f = mix(f_6, f_8)`, `S_age = S_open(mix) / f`.
* **Interpolate the age standards**: `S_age = mix(S_6/f_6, S_8/f_8)`.

They do not agree, because the mean of ratios is not the ratio of means. Do the
first. This is also the order the table producers used at the interpolation
stage — they interpolated *factors*, having first found that interpolating the
curve *parameters* gave a worse result
([04-methodology.md](04-methodology.md#4-distance-interpolation)).

Higher-precision consequence: because factors are only stored to 4 dp, the
bilinear mix of two factors carries about 1e-5 of granularity, which is far
below any physical meaning. Resist the urge to interpolate in log space or with
splines to "improve" it — you would no longer be reproducing the tables.

---

## Reference implementation, condensed

```python
def grade(t, sex, age, dist_km, time_s):
    ia, ib, pa = t._bracket_age(age)                 # age axis
    i0, i1, pd = t._bracket_distance(dist_km)        # distance axis
    e0, e1 = t.events[i0], t.events[i1]
    f = ((1-pd) * ((1-pa)*e0.factors[ia] + pa*e0.factors[ib])
       +      pd * ((1-pa)*e1.factors[ia] + pa*e1.factors[ib]))
    s_open = (1-pd) * e0.standard_s + pd * e1.standard_s
    return f, s_open, s_open / f, time_s * f, 100 * s_open / (time_s * f)
```

The only subtleties are the boundary rules above and the event-name lookup,
which is **case-insensitive but otherwise exact** (`10kmRoad`, not `10k`) in the
VBA; the calculator's dropdown uses the same strings. `brrag` accepts the
table name or a `--distance` alias (`10k`, `half`, `marathon`, `12.7` …).

---

## Equivalence checks to write when you port this

1. For every published cell: `lookup(sex, age, event=name).factor == cell`.
   (4 224 assertions; see check A in [08-validation.md](08-validation.md).)
2. `lookup(sex, age, dist_km=event.distance_km)` equals
   `lookup(sex, age, event=event.name)` — the two entry points must agree.
3. `S_age == S_open / f` and `percent == 100*S_age/time` to floating-point
   tolerance.
4. Invent a 40:00 10 km for a 40-year-old male and confirm **68.49%**. It is the
   canonical smoke test.
