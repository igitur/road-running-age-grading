# 07 — Implementing it

You need three things: a factor table per (sex, distance), the open standard per
distance, and the two-axis lookup from [03-algorithm.md](03-algorithm.md). No
external data source, no model, no network.

## Data format

`data/mldr_road.json` is the whole dataset. One object per table, keyed
`"<authority> <year> <sex>"`:

```json
{
  "source": "https://www.howardgrubb.co.uk/athletics/mldrroad25.html",
  "tables": {
    "USATF MLDR 2025 M": {
      "authority": "USATF MLDR", "year": 2025, "sex": "M",
      "vari": "MLDR_25_M_facs",
      "ages": [5, 6, 7, "... 100"],
      "events": [
        {"event": "5kmRoad", "distance_km": 5.0,
         "open_standard_s": 769.0,
         "factors": [0.608, 0.6664, "... 96 values"]}
      ]
    }
  }
}
```

Invariants worth asserting on load:

* `len(ages) == 96` and `ages == list(range(5, 101))`
* `len(factors) == len(ages)` for every event
* `events` sorted by `distance_km`, all distances distinct
* every factor in `(0, 1]`, every standard `> 0`
* the standard of the first event (1 mile) is the smallest — sanity check that
  the file has not been scrambled

`brrag/core.py:Tables.__init__` checks the length invariant and nothing else;
add the rest if you are loading untrusted files.

Four editions are included (2025, 2020, 2015, 2010) because the calculator page
carries all four, which makes it cheap to compare a historical result. Only
2025 is documented here; the older sets have 20–21 events and different
standards.

## Python API

```python
from brrag import table, format_time, parse_time, ui_percent

t = table(2025, "M")                      # Tables object
g = t.grade("M", 40, parse_time("40:00"), dist_km=10)

g.factor              # 0.96360...
g.standard_s          # 1584.0        open standard
g.age_standard_s      # 1643.8...     100% time for this age
g.age_graded_s        # 2313.6...     time x factor
g.percent             # 68.49...      (unrounded)

ui_percent(2400, g.age_standard_s)    # 68.49  — exactly what the page shows
```

`t.grade()` accepts either `event="10kmRoad"` (exact row) or `dist_km=10` (the
two-axis lookup). `t.lookup()` returns just `(factor, standard)`.
`t.time_for_percent()` is the calculator's *Result* button.

Two keyword policies exist so that "faithful to the calculator" is a choice
rather than an accident:

| keyword | values | default | meaning |
| --- | --- | --- | --- |
| `policy` | `"strict"` \| `"clamp"` | `strict` | out-of-range distances raise vs use the nearest row |
| `age_policy` | `"ui"` \| `"linear"` | `ui` | reproduce the 99–100 clamp, or interpolate normally |

## CLI

```console
$ brrag 40:00 --age 40 --sex M --distance 10k
$ brrag 2:30:00 --age 60 --sex M --event Marathon --json
$ brrag 3:15:00 --age 52 --sex F --distance 42.195 --show-standard
$ brrag --list-events --sex F
```

Distances accept `mile, 5k, 6k, 4mi, 8k, 5mi, 10k, 7mi, 12k, 15k, 10mi, 20k,
half/hm, 25k, 30k, marathon, 50k, 50mi, 100k, 150k, 100mi, 200k` or any number
of kilometres. `--json` emits the full record; `--ui-parity` reproduces the web
page's displayed percentage.

## Porting to another language

Order of work, with the traps in the order you will hit them:

1. **Load the table.** Get factors as a rectangular array, indexed
   `[event][age_index]`. Watch out for the female workbook's duplicated `Age`
   column if you parse Excel instead of the JSON.
2. **Sort events by distance.** The published spreadsheets happen to be sorted;
   do not rely on it.
3. **Age bracket.** Clamp to `[5, 100]`; interpolate linearly between integer
   ages; reproduce the `(99,100]` clamp only if you need digit-parity with the
   web page.
4. **Distance bracket.** Find the last event with `distance ≤ request`; take the
   next one; **linear in distance**. Decide explicitly what you do outside
   `[1 mile, 200 km]` — refuse (calculator), clamp (many ports), or extrapolate
   (VBA).
5. **Bilinear mix the four factors**, then divide the *interpolated* standard by
   the result.
6. **Round only at the display layer**, half-up, and never before dividing.
7. **Test against the published cells** and against one known percentage:
   male 40, 10 km, 40:00 → **68.49%**.

### Reference snippets

Julia:

```julia
function grade(tab, age, dist, time_s)
    ia, ib, pa = bracket_age(tab.ages, age)
    i0, i1, pd = bracket_dist(tab.dist, dist)
    f(i, a) = tab.facs[i, a]
    f0 = (1-pa)*f(i0,ia) + pa*f(i0,ib)
    f1 = (1-pa)*f(i1,ia) + pa*f(i1,ib)
    fac = (1-pd)*f0 + pd*f1
    sopen = (1-pd)*tab.standard[i0] + pd*tab.standard[i1]
    (; factor=fac, age_standard=sopen/fac, graded=time_s*fac,
       percent=100*sopen/(time_s*fac))
end
```

SQL (if the table is in a database, one row per event/age):

```sql
-- factor for an integer age and an exact distance, no interpolation
SELECT f.factor, e.open_standard_s,
       e.open_standard_s / f.factor          AS age_standard_s
FROM   age_factors f
JOIN   events e USING (event, sex)
WHERE  f.sex = 'M' AND f.age = 40 AND f.event = '10kmRoad';
```

For fractional ages or arbitrary distances, interpolate in the application
layer: SQL window functions make a poor home for the bracketing logic.

## What not to do

* **Do not recompute the tables** from the curve parameters at runtime. The
  parameters reproduce a curve, but the published table is the authority, and
  the shipped parameters are one revision behind for the male 5 km/10 km
  ([05-provenance.md](05-provenance.md#c-male-working-file-vs-published-tables)).
* **Do not interpolate standards instead of factors** — different answer, no
  authority ([03-algorithm.md](03-algorithm.md#why-not-interpolate-standards)).
* **Do not interpolate distances in log space at runtime.** The tables were
  built that way; the lookup is linear in distance between the rows you have.
* **Do not smooth or refit the published factors.** They are a fit already;
  the bumps you think you see are the sports.
* **Do not store a percentage without the year.** 68.49% is a 2025 statement.

## Reproducing the data pipeline

```console
$ curl -sO https://www.howardgrubb.co.uk/athletics/mldrroad25.html
$ .venv/bin/python tools/extract_tables.py mldrroad25.html data/mldr_road.json
$ .venv/bin/python tools/verify.py --all
```

`extract_tables.py` scrapes the `facrow(...)` literals out of the page, asserts
that each event's factor count equals the published age count, and fails loudly
otherwise. If the page's markup changes, that assertion is what will tell you.
