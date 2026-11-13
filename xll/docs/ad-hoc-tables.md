# Custom tables: formats, and the alternatives I rejected

Age-grading tables are refitted every few years and clubs sometimes want their
own handicap (a harsher table for a veterans' trophy, an experimental one for a
trial). So the fifth argument of every grading function accepts a **range** in
place of an edition name:

```
=RRAG.GRADE($B$2:$B$181, $C$2:$C$181, $D$2:$D$181, $E$2:$E$181, $M$2:$X$40)
```

That range is a whole table. This page defines what it may look like, and why
the two accepted layouts beat the alternatives.

## The two accepted layouts

Both are auto-detected from the header row: you do not tell the add-in which one
you are using.

### Layout A — matrix (recommended)

One row per (sex, distance). Ages run across the header.

| Sex | Distance | OpenStd | 5 | 6 | … | 100 |
| --- | --- | --- | --- | --- | --- | --- |
| M | 10 k | 26:24 | 0.5073 | 0.5678 | … | 0.2121 |
| F | 10 k | 28:46 | 0.6850 | 0.7183 | … | 0.1477 |
| M | marathon | 2:00:35 | 0.4414 | 0.5080 | … | 0.1919 |
| F | marathon | 2:09:56 | 0.5405 | 0.5874 | … | 0.0625 |

44 data rows for a full 22-distance, two-sex table; 99 columns. It is the same
shape as the published `Age Factors` sheet, so **a table can be copied out of
the official workbook with two edits**: add a `Sex` column (the official file
keeps the sexes on separate sheets) and paste the open standards alongside.

Minimal version — only the ages you care about:

| Sex | Distance | OpenStd | 30 | 40 | 50 |
| --- | --- | --- | --- | --- | --- |
| M | 10 k | 26:24 | 1 | 0.9 | 0.8 |
| F | 10 k | 28:46 | 1 | 0.85 | 0.75 |

Gaps are interpolated linearly and the ends are clamped, so `age 35` gets 0.95
and `age 12` gets the age-30 factor (1.0).

### Layout B — long

One row per (sex, distance, age). Reads like a database table and is what a
`pandas.melt` or an unpivot produces.

| Sex | Distance | Age | Factor | OpenStd |
| --- | --- | --- | --- | --- |
| M | 10 k | 30 | 1 | 26:24 |
| M | 10 k | 40 | 0.9 | 26:24 |
| M | 10 k | 50 | 0.8 | 26:24 |
| F | 10 k | 30 | 1 | 28:46 |
| F | 10 k | 40 | 0.85 | 28:46 |

Detected by the presence of both an `Age` and a `Factor` column.

## Rules both layouts follow

| Rule | Why |
| --- | --- |
| Header names are case- and space-insensitive: `Sex`/`Gender`, `Distance`/`Event`/`Km`/`Dist`, `OpenStd`/`Standard`/`Std`/`Open` | nobody should have to guess |
| `OpenStd` is **optional**. Omitted → the built-in 2025 standard for that exact distance is used | the common case is "same distance, my factors" |
| `OpenStd` accepts a time value, `"26:24"` or seconds | same rules as every other time argument |
| A blank `Sex` cell inherits the row above | lets you write `M` once per block |
| Ages may be any subset of 1–120, in any header order, unevenly spaced | club tables rarely have all 96 |
| Missing ages inside the row are interpolated; ends are clamped | makes short tables usable |
| Ages are interpolated right up to the table's own last supplied age — a table of 45…65 interpolates 61, it does not jump to 65 | the published editions' (99, 100] quirk is an artefact of a grid ending at 100 and would be nonsense here |
| Factors must be in `(0, 1]` | a factor above 1 would mean "faster than the world record for your age" |
| A blank row between blocks is ignored | pasted tables often have them |
| One sex only is fine — the other sex then errors rather than silently grading wrongly | half a table is legitimate |
| Failures name the row: `row 12, age 40: factor must be in (0, 1]` | diagnosable in a 99-column table |

Distance cells use the same grammar as the function's distance argument —
`10 k`, `10 kilometres`, `6.2 miles`, `half marathon`, `marathon`, or a plain
number of km (`21.1`). Two different spellings of the same distance are the same
row: rows are keyed by distance, not by text, so `10k` in the table and `10 km`
in the formula find each other.

## The alternatives, and why not

### C. One cell holding JSON or CSV

`=RRAG.GRADE(…, "{""M"":{""10km"":{…}}}")`

- Only pro: one cell to copy.
- Rejected: unreadable and uneditable in Excel, impossible to spot-check, hits
  the 32 767-character cell limit at about 400 factors, and every edit is a
  string-surgery exercise. A table is data; let it look like data.

### D. The official workbook layout, unchanged

Two sheets, one per sex, no `Sex` column, ages as columns, open standards in a
`Parameters` sheet elsewhere.

- Pro: literally the published file, no preparation.
- Rejected: the sex is implied by *which sheet* you point at, so the argument
  becomes a sex-specific table — but the add-in already has a sex column in the
  data. You would have to pass different ranges to different rows, which no
  single spilled formula can do. Requiring one extra column is a smaller price
  than a per-row range.
- Compromise: the matrix layout is the official layout plus a `Sex` column, so
  "copy, insert a column, fill it down" is the whole migration.

### E. Distance in the header, ages down the side

Transposed: `Distance` across the top, `Age` down the left.

- Rejected: 22 distance columns is wide but fine, except that each sex then
  needs its own block *and* the open standard has nowhere natural to live. Also
  the transpose of a familiar shape buys nothing.

### F. A named Excel Table (ListObject) with structured references

`=RRAG.GRADE(…, Table_Handicap)`

- This already works: a named table resolves to a range like any other, so
  `Table_Handicap` and `$M$2:$X$40` are interchangeable. Nothing extra to
  implement; mention it in user docs as the tidy way to manage a long-lived
  table.

### G. A database / SQLite / the Windows registry

- Rejected: 4 000 numbers is not a data-management problem. Adding a storage
  engine to an add-in that ships as one file contradicts the reason it ships as
  one file.

### H. A macro/array literal pasted into a cell

- Rejected: borderline malware shape, no diffing, no review.

## Recommendation

1. **Steal the official workbook** when you want a real table: copy the
   `Age Factors` sheet, insert a `Sex` column, fill it, paste the open standards
   in front. Save as `<name>.csv` beside the `.xll` and refer to it by name —
   it is then available to every workbook on the machine and cached for the
   session.
2. **Use the minimal matrix** for a club handicap: three or four ages per
   distance is enough, and the interpolation fills in the rest.
3. **Long format** only when the table comes out of a script.

## Worked example, end to end

A club decides its veterans' trophy should be judged on a **stricter** table: it
assumes age costs 5% more than the published tables do, so it keeps the 2025
factors everywhere except 10 km for over-45s, where it multiplies them by 1.05
(a bigger factor means a smaller age standard, so the same run scores lower).

`tables\bellville-vets.csv`:

```csv
Sex,Distance,OpenStd,45,50,55,60,65,70
M,10 k,26:24,0.9724,0.933,0.8937,0.8543,0.8149,0.7755
F,10 k,28:46,0.9742,0.9263,0.8741,0.8219,0.7698,0.7176
```

```
=RRAG.GRADE($B$2:$B$181, $C$2:$C$181, "10k", $E$2:$E$181, "bellville-vets")
```

A 55-year-old man running 45:00 scores `100 × (1584/0.8937) / 2700 = 65.6%` on
this table, against `68.9%` on the published one — the trophy is harder to win,
which is the point. (Both figures computed: `brrag 45:00 --age 55 --sex M
--distance 10k` gives the second.)

The same mechanism points the other way if a club wants its own standard: put a
slower time in `OpenStd` (a club record rather than the world record) and every
percentage rises accordingly.

## Keeping a custom table honest

A custom table is not age grading as published, and shouldn't be reported as if
it were:

- Say which table produced a percentage, exactly as you would say which year.
- `RRAG.TABLEINFO(range)` returns the geometry (distances, ages, sexes) of a range
  — a cheap check that you pointed at the right block.
- The built-in editions remain the reference. If a club table and 2025 disagree
  in the first decimal for a mid-pack runner, that is a bug in the club table.
