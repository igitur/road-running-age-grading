# 04 — How the tables are built

Age-grading tables are **not** a formula you can derive. Each table is fitted to
observed results, and the fitting is a human-in-the-loop process that ends with
ten hand-tuned parameters per distance per sex. This page describes that
process, in enough detail that the next revision (or a hostile audit) can follow
it.

Primary sources: Jones, *Creating Road Running Age-Grade Tables* (2024-10-23)
and *Age-Grade History* (2025-01-13), both in the upstream repository under
`Docs/`. All numeric parameters below are read from
`maleRoad2025.xlsx` / `femaleRoad2025.xlsx` and can be re-derived with
`tools/reproduce_curve.py`.

The pipeline in one line:

> single-age bests → open standards → fit a 5-segment curve to handicap vs age
> at four distances → interpolate the rest in log-distance → round to 4 dp.

---

## 1. Input data: single-age bests

The raw material is a table of the **best performance ever recorded by an
athlete of each age**, at each distance — not a sample of results, and not a
model of the population. On a scatter of time vs age these form the dots the
curve must stay *on or below* (a standard can never be slower than a best, or
someone would score over 100%).

History of the data source matters for reproducibility:

| Years | Provider |
| --- | --- |
| ≤ 2019 | Association of Road Racing Statisticians (ARRS), Ken Young |
| 2020 → | Tom Bernhard (single-age bests spreadsheets) |

Bernhard's files (`Men/Women Single Age Bests 2025.xlsx`) have one sheet per
distance; the world record for the distance is highlighted. Ages with no data
are left blank, which is why youth ages exist for 5 km but not for the mile.

Records are also the anchor for the open standard, and they move:

| Record | 2020 | 2025 |
| --- | ---: | ---: |
| Female 5 km | 14:44 | **14:13** |
| Female half marathon | 1:04:31 | **1:02:52** |
| Male 5 km | 12:51 | **12:49** |
| Male marathon | 2:01:39 | **2:00:35** |

A faster record drags the whole curve down at that distance, because the
handicap `f` is measured *relative to* the standard.

## 2. Open standards

The open standard is the fastest time in the table for that distance:

* **Calibration distances (5 km, 10 km, half, marathon): the world record.**
* **Every other distance: the record adjusted by hand**, so that pace varies
  smoothly with distance. The workbook has a `Parameters` sheet with both the
  raw record and the adjusted value, plus a pace-vs-distance plot used to eyeball
  the smoothness. Adjustments are usually faster than the record and can be
  large — the male 50 km standard is 2:27:00 against a 2:43:38 record; see the
  table in [02-tables-2025.md](02-tables-2025.md#the-open-standards-are-not-always-the-world-record).

Distances beyond the marathon do not get their own curve at all: they reuse the
marathon's factors and differ only in open standard. That is why male 50 km →
200 km factor rows are identical.

## 3. The seven-segment curve

The factor curve is a single hand-tuned function of age, made of five joined
pieces (two parabolas, two lines, one constant) spanning seven formula
branches. The breakpoints are `a < b < c < d < e < f`:

```
y = 1 - C(c-b)² - B(b-x) - A(a-x)²      for  x < a     youth parabola
y = 1 - C(c-b)² - B(b-x)                for  a ≤ x < b linear youth
y = 1 - C(c-x)²                         for  b ≤ x < c quadratic run-in
y = 1                                   for  c ≤ x < d the plateau
y = 1 - D(x-d)²                         for  d ≤ x < e quadratic masters onset
y = 1 - D(e-d)² - E(x-e)                for  e ≤ x < f linear decline
y = 1 - D(e-d)² - E(x-e) - F(x-f)²      for  x ≥ f     accelerating decline
```

with slopes forced to match at `b` and `e`, which fixes two of the twelve
constants:

```
C = B / (2(c-b))          D = E / (2(e-d))
```

leaving **ten free parameters**: `a, b, c, d, e, f` (ages) and `A, B, E, F`
(coefficients). `y` is always ≤ 1, and the upper curve in the workbook is `1/y`
— the age standard relative to the open standard.

Reading the pieces as a story: the youth parabola handles children (where the
curve is steepest and data is thinnest), a linear ramp carries teenagers to the
plateau, the plateau spans prime racing age, then a quadratic onset, a long
straight decline through the masters years, and a final parabola for the oldest
ages where decline accelerates.

### Why this shape, and not a smooth spline

It is deliberately piecewise: the author's stated aim was a curve that never
exceeds any observed age best, is smooth in slope at the joins, and can be
adjusted by a human who understands the sport. A spline fitted automatically
would chase outliers (a single absurd age-68 female 5 km mark was declared an
outlier in 2025 and excluded by judgement, not by algorithm).

### The 2025 parameter sets

From the working files (`tools/reproduce_curve.py` prints these):

| Sex | Sheet | B | A | E | F | a | b | c | d | e | f |
| --- | --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| M | Mile | 0.017 | 0.0018 | 0.00694 | 0.000349 | 15 | 17 | 19 | 29 | 30.5 | 68.25 |
| M | 5K | 0.01202 | 0.0024 | 0.007 | 0.0003 | 16 | 17 | 19 | 29.6 | 34.958 | 67.389 |
| M | 10K | 0.0065 | 0.002 | 0.0075 | 0.000335 | 19 | 19 | 20 | 29 | 41.5 | 70 |
| M | Half | 0.01 | 0.00287 | 0.00778 | 0.000341 | 16.7 | 19 | 20 | 31 | 39.7 | 70 |
| M | Marathon | 0.02 | 0.00222 | 0.0082 | 0.00035 | 16 | 17 | 22 | 35.7 | 39 | 71 |
| F | Mile | 0.016 | 0.0007 | 0.00971 | 0.00047 | 15 | 17 | 19 | 30.1 | 49 | 78.5 |
| F | 5K | 0.0189 | 0.00074 | 0.00971 | 0.00038 | 14.3 | 17 | 19 | 26 | 45 | 76.8 |
| F | 10K | 0.016 | 0.00091 | 0.00994 | 0.00038 | 15 | 17 | 21 | 27 | 49.3 | 75 |
| F | Half | 0.02 | 0.00102 | 0.01035 | 0.0004 | 15 | 17 | 22 | 27 | 48.9 | 75.15 |
| F | Marathon | 0.0174 | 0.00155 | 0.01106 | 0.0004 | 15 | 19 | 26 | 27 | 56.2 | 73 |

What the numbers say about the sport:

* `d`, where decline starts, is **26 for the female 5 km but 35.7 for the male
  marathon** — women's road results peak earlier and the marathon peak is older
  than the 5 km peak.
* `E`, the slope of the masters decline, rises with distance (0.007 at 5 km to
  0.0082 at the marathon for men), which is the formal statement of "aging costs
  more over longer races".
* `c - d` is the plateau; `F` (the late-life acceleration) is small and slowly
  varying, which is why the very old ages are the least reliable part of the
  table.

### Worked reproduction

Male, 5 km, age 60, parameters straight from the sheet:

```
C = B/(2(c-b))     = 0.01202/(2·2)          = 0.003005
D = E/(2(e-d))     = 0.007/(2·5.358)        = 0.00065323
age 60 ≥ e (34.958) and < f (67.389)  →  linear branch
f = 1 - D(e-d)² - E(60-e)
  = 1 - 0.00065323·28.71 - 0.007·25.042
  = 1 - 0.018754 - 0.175294              = 0.805952  → 0.8060
```

`tools/reproduce_curve.py` does this for all ten curves and reports:

```
worst absolute error across the curves that match exactly: 0.0001
```

i.e. the model reproduces the factor sheet it was taken from essentially
perfectly, so the description above is the real generating function and not a
plausible story. (It reproduces the **working file's** sheet, dated 2025-07-25;
the published male 5 km and 10 km curves are a later revision — see
[05-provenance.md](05-provenance.md#c-male-working-file-vs-published-tables).)

One documented exception: on the **female mile**, the workbook's youth and
masters formula blocks switch over at age 35 instead of at `d = 30.1`, so ages
31–34 keep a flat 1.0 where the fitted curve has already begun to decline
(largest gap 0.0039 — a few tenths of a percentage point of age grade). It is a
spreadsheet-assembly artefact, not a modelling decision
([05-provenance.md](05-provenance.md#d-female-mile-ages-3134)).

## 4. Distance interpolation

Only four distances are fitted, because only those are raced often enough to
support single-age bests: **5 km, 10 km, half marathon, marathon**. The mile is
fitted too, with youth parameters borrowed from the 5 km (no youth mile data
exists). Every other distance is derived.

The first attempt interpolated the *parameters* (`A`, `B`, …) between
neighbouring distances and then computed factors. That failed — the parameters
have wildly different scales and sensitivities, so a linear blend of them
produces bumps. The adopted method interpolates the **factors themselves**:

```
f_d(age) = f_lo(age)·(1-u) + f_hi(age)·u
u = (log10 d - log10 d_lo) / (log10 d_hi - log10 d_lo)
```

The weight `u` is a **log-distance** fraction, because linear distance would
bunch the short events together and starve the long ones. Between 5 km and
10 km:

| Event | km | u |
| --- | ---: | ---: |
| 6 km | 6 | 0.263034 |
| 4 mile | 6.437376 | 0.364545 |
| 8 km | 8 | 0.678072 |
| 5 mile | 8.04672 | 0.686473 |

Between 10 km and the half: 7 mile 0.159599, 12 km 0.244212, 15 km 0.543104,
10 mile 0.637351, 20 km 0.928443. Between the half and the marathon: 25 km
0.244856, 30 km 0.507890.

The published open standards at these distances were *not* re-derived by this
formula — they come from the hand-adjusted record list (§2). So an interpolated
row pairs an interpolated factor with an independently chosen standard. That is
intentional.

Because standards are interpolated in the *workbook* as
`S_d = S_5(1-u) + S_10·u` (see the 2025 Readme), the stored factor of an
interpolated row is implied by `f = S_open / S_age`. This is one reason
`data/mldr_road.json` stores factors and standards as published rather than
recomputing either.

## 5. Rounding and publication

* Factors are rounded to 4 decimal places in the spreadsheets; the published
  file therefore carries 1e-4 granularity, and repeated interpolation cannot
  reveal more.
* Age standards are also published in whole seconds (`AgeStdSec`) and as
  `h:mm:ss` (`AgeStanHMS`).
* Approval: the **USATF MLDR Council** approves each edition (2025-01-10 for the
  current one). WMA approved the 2010 and 2015 editions jointly; since 2020 the
  road tables are an MLDR/USATF product that the wider community consumes.

## 6. Quality control, as practised

Documented in *Evaluating 2025 Standards Against 2020 Rankings*:

1. Plot new single-age bests over the new standard; every dot must be on or
   below the line.
2. Compute `100 × S_age/T` for the age bests — the best performance at each age
   should score as close to 100.0 as possible, never above it. The 2025 target
   was hit exactly at several ages per distance ("100.0 at ages 7, 22, 23 and 64"
   for the female 5 km).
3. Declare outliers explicitly and exclude them with a stated reason (2025:
   female 5 km age 68; female marathon ages 63, 77, 82). The stated policy is
   "we say it is an outlier", not "we claim the course was short".
4. Check the pace-vs-distance plot for bumps, which reveal interpolation errors.
5. Apply the *new* bests to the *old* standards: any value above 100 means the
   old standard was too soft and the new data disagrees with it.

## 7. What it takes to produce the next edition

See the checklist in [09-history.md](09-history.md#checklist-for-the-next-revision).
In short: new single-age bests → refresh open standards → refit ten parameters
everywhere → recompute `u` if the event list changes → regenerate all 22 rows →
re-run the 100.0%-at-every-age test → get MLDR approval → publish the factor
workbook, the standards workbook and the calculator data.
