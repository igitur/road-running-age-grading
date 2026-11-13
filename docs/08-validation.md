# 08 — Validation

Three independent checks, because each one catches a different class of mistake.
Run them all with:

```console
$ .venv/bin/python tools/verify.py --all
A. exact-event grid: 4224 lookups, 0 mismatches
B. JS oracle: 1412 requests, 0 mismatches, worst percent delta 0.000000 pp
C. standards file: 4224 cells, 0 mismatches, 18 known anomalies
RESULT: PASS
```

## A — exact-event grid (catches data errors)

For every one of the **22 events × 96 ages × 2 sexes = 4 224 cells**, ask the
implementation for the factor at exactly that age and event, and require it to
equal the stored cell **to within 1e-12**.

This is a tautology test *if* the lookup is correct, which is the point: it
fails immediately if the bracket logic returns a neighbouring column, if the
JSON was transposed, if a factor list is one short, or if the sex tables were
crossed.

It also re-checks that the open standard returned for an exact event equals the
event's stored standard.

## B — JavaScript oracle (catches algorithmic divergence)

The strongest check available: rather than compare against our reading of the
calculator, **run the calculator's own code**.

`tools/js_oracle.js` fetches the archived `page.html`, extracts the `<script>`
block that defines `MLDR_25_M_facs`, and evaluates it inside a Node `vm` context
with a stubbed DOM: a `form` object whose fields are `{value}`, a fake
`<select>` for the event dropdown (seeded from the page's real `<option>` list),
and an `Option` constructor. It then drives the page's own functions in the same
order a user would — `setFactors() → setEvent()/setMileage() → setAge() →
calc_fwd()` — and reads back `afac`, `ostd`, `astd`, `ageresult`, `aplp`.

The harness therefore tests the real thing, including its rounding and its
quirks. 1 412 requests are issued:

* **1 012 grid requests** — both sexes × all 22 events × 23 ages spanning the
  whole range (5, 6, 9, 17, 19, 20, 27, 28, 30, 34, 35, 40, 50, 55, 60, 65, 70,
  75, 80, 85, 90, 95, 100) with pseudo-random times.
* **400 random requests** — mixed sexes, distances uniform in `[1.7, 210]` km
  (deliberately including outside the published range), ages either integer or
  one decimal place (so fractional interpolation is exercised), times 5 min to
  8 h.

Comparison rules:

* **Factor**: both sides rounded to 4 dp with round-half-up before comparing.
  (Python's `round()` is banker's rounding and disagrees on ties — that cost us
  a false positive during development and is why `verify.py` uses
  `floor(x*1e4+0.5)/1e4`.)
* **Percentage**: our value must pass through the same display rounding the UI
  applies (`ui_percent`), then match to 0.005 pp. Measured worst delta: **0**
  — bit-identical after display rounding.
* **Refusals must agree**: where the calculator returns blank (distance outside
  the published range) we require our implementation to raise `OutOfRange`.
  Getting this wrong is how the `> 200 km` off-by-one was found.

## C — standards cross-check (catches artefact drift)

Independent of the calculator: take the **published standards spreadsheets**
(`MaleRoadStd2025.xlsx` / `FemaleRoadStd2025.xlsx`), and for all 4 224 cells
verify

```
round(S_open / factor)  ==  published age standard in seconds
```

The published standards are whole seconds, so ±0.5 s is the tolerance.

**18 cells are expected to fail** and are reported as `KNOWN ANOMALY` instead of
aborting the run — they are documented upstream defects, not our bugs:

* the stale age-5 row present for 17 events
  ([05-provenance.md](05-provenance.md#a-agestdsec-has-a-stale-age-5-row-17-events));
* the female 10 km age-100 cell that used the 7-mile factor
  ([05-provenance.md](05-provenance.md#b-female-agestdsec-10-km-age-100-is-wrong)).

If a future run reports a *different* number of anomalies, something has changed
upstream and the docs need re-reading before the code does.

## D — the curve model (catches a wrong methodology story)

Separate tool, different question: does the *documented generating function*
really produce the published numbers?

```console
$ .venv/bin/python tools/reproduce_curve.py
worst absolute error across the curves that match exactly: 0.0001
```

Nine of the ten fitted curves (5 distances × 2 sexes, minus one) reproduce their
4-dp factors exactly from the ten published parameters. The exception is the
female mile, ages 31–34, where the spreadsheet's own formula blocks leave a flat
1.0 that the curve does not produce (max gap 0.0039, documented in
[04-methodology.md](04-methodology.md#worked-reproduction)).

Without this check, the methodology page could describe a plausible model that
happens to be wrong, and every number derived from the tables would still look
fine.

## What is *not* verified

* **The tables are not checked against reality.** We verify transcription and
  arithmetic, not whether Alan Jones's fit is a fair model of ageing. That is a
  sports-science question, argued in the upstream PDFs.
* **The 2020/2015/2010 tables** are extracted and available but not validated
  beyond the extraction assertion. Only 2025 is documented.
* **The VBA workbook's functions** are read and described, not executed (no
  Excel here). Its behaviour is quoted from the extracted source in
  `raw/xl/vbaProject.bin`.
* **Fractional-age behaviour of the VBA** (`age As Integer`) is stated from the
  signature, not observed.

## Reproduce from scratch

```console
$ uv venv --python 3.12 .venv && uv pip install --python .venv/bin/python openpyxl oletools
$ curl -s -o page.html https://www.howardgrubb.co.uk/athletics/mldrroad25.html
$ curl -s -o MLDRRoadFactors2025.xlsm https://www.howardgrubb.co.uk/athletics/data/MLDRRoadFactors2025.xlsm
$ git clone --depth 1 https://github.com/AlanLyttonJones/Age-Grade-Tables.git repo
$ .venv/bin/python tools/extract_tables.py page.html data/mldr_road.json
$ .venv/bin/python tools/verify.py --all
$ .venv/bin/python tools/reproduce_curve.py
$ sha256sum -c data/source_sha256.txt   # run from the repo root
```
