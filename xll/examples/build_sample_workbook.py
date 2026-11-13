#!/usr/bin/env python3
"""build_sample_workbook.py — generate the sample workbook for xll_age_grading.xll.

Every expected value in the workbook is computed here from the verified Python
implementation in aggrade/ (itself checked against the published calculator by
tools/verify.py), so no number is hand-typed and the workbook can be rebuilt
after any change to the tables:

    python3 xll/examples/build_sample_workbook.py
    python3 xll/examples/build_sample_workbook.py --check   # fail if stale

The formulas are live: each demo cell calls AG.* as a real XLL formula. Without
the add-in loaded Excel shows #NAME?; that is expected and is explained on the
first sheet.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from aggrade.core import load_tables                      # noqa: E402
from openpyxl import Workbook, load_workbook              # noqa: E402
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side  # noqa: E402
from openpyxl.worksheet.properties import PageSetupProperties  # noqa: E402
from openpyxl.utils import get_column_letter              # noqa: E402
from openpyxl.worksheet.formula import ArrayFormula       # noqa: E402

OUT = Path(__file__).resolve().parent / "age-grading-sample.xlsx"

# ---------------------------------------------------------------------------
# palette and cell styles
# ---------------------------------------------------------------------------
NAVY = "FF1F3864"
PALE_NAVY = "FFD9E1F2"
LIVE = "FFDCE6F1"        # a cell holding a live AG.* formula
EXPECTED = "FFF2F2F2"    # a value computed by the Python implementation
INPUT = "FFFFF8E7"       # a cell you are meant to edit
CHECK = "FFE2EFDA"       # the OK/MISMATCH verdict
GREY = "FF595959"

THIN = Side(style="thin", color="FFBFBFBF")
BOX = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)

F_TITLE = Font(name="Calibri", size=16, bold=True, color=NAVY)
F_H2 = Font(name="Calibri", size=11, bold=True, color=NAVY)
F_HDR = Font(name="Calibri", size=10, bold=True, color="FFFFFFFF")
F_BODY = Font(name="Calibri", size=10)
F_MONO = Font(name="Consolas", size=9)
F_NOTE = Font(name="Calibri", size=9, italic=True, color=GREY)

FILL_HDR = PatternFill("solid", fgColor=NAVY)
FILL_SUB = PatternFill("solid", fgColor=PALE_NAVY)
FILL_LIVE = PatternFill("solid", fgColor=LIVE)
FILL_EXP = PatternFill("solid", fgColor=EXPECTED)
FILL_IN = PatternFill("solid", fgColor=INPUT)
FILL_CHECK = PatternFill("solid", fgColor=CHECK)

TIME_FMT = "[h]:mm:ss"
PCT_FMT = "0.00"
FAC_FMT = "0.0000"

CENTER = Alignment(horizontal="center", vertical="center", wrap_text=True)
LEFT = Alignment(horizontal="left", vertical="center")
LEFT_WRAP = Alignment(horizontal="left", vertical="top", wrap_text=True)
TOP_CENTRE = Alignment(horizontal="center", vertical="top")


# ---------------------------------------------------------------------------
# time helpers: the workbook stores real Excel time values, never strings
# ---------------------------------------------------------------------------
def secs(clock: str) -> float:
    """'40:00', '1:52:30', '2:00:35' -> seconds."""
    parts = [int(p) for p in clock.split(":")]
    while len(parts) < 3:
        parts.insert(0, 0)
    h, m, s = parts
    return h * 3600 + m * 60 + s


def serial(clock: str) -> float:
    """'40:00' -> the Excel time value Excel shows as 0:40:00."""
    return secs(clock) / 86400.0


def clock_of(seconds: float) -> str:
    s = int(round(seconds))
    return f"{s // 3600}:{s % 3600 // 60:02d}:{s % 60:02d}"


T = load_tables()


AUTHORITY = {2025: "USATF MLDR", 2020: "USATF MLDR", 2015: "WMA", 2010: "WMA"}


def tbl(sex: str, year: int = 2025):
    return T[f"{AUTHORITY[year]} {year} {sex}"]


def grade(sex: str, age: float, dist_km: float, time_s: float, year: int = 2025):
    return tbl(sex, year).grade(sex, age, time_s, dist_km=dist_km)


# ---------------------------------------------------------------------------
# the custom tables: a sparse matrix of published 2025 factors, and its long
# form. Both are parsed by the add-in; the expected values here mirror the
# add-in's parsing rules (linear interpolation between supplied ages, ends
# clamped, OpenStd optional).
# ---------------------------------------------------------------------------
CUSTOM_AGES = [45, 50, 55, 60, 65]
CUSTOM_ROWS = [
    ("M", "10kmRoad", "26:24"),
    ("F", "10kmRoad", "28:46"),
    ("M", "Half.Mar", "57:31"),
    ("F", "Half.Mar", "1:02:52"),
    ("M", "Marathon", "2:00:35"),
    ("F", "Marathon", "2:09:56"),
]


def custom_factors(sex: str, event: str) -> list[float]:
    ev = tbl(sex).event(event)
    return [ev.factors[tbl(sex).ages.index(a)] for a in CUSTOM_AGES]


KM = {"10kmRoad": 10.0, "Half.Mar": 21.0975, "Marathon": 42.195}


def custom_grade(sex: str, event: str, age: float, time_s: float) -> float:
    """Grade with the sparse custom table, mimicking ag_core.cpp exactly."""
    ages = CUSTOM_AGES
    v = custom_factors(sex, event)
    f = v[0] if age <= ages[0] else v[-1]
    if ages[0] < age < ages[-1]:
        for i in range(1, len(ages)):
            if age < ages[i]:
                p = (age - ages[i - 1]) / (ages[i] - ages[i - 1])
                f = v[i - 1] * (1 - p) + v[i] * p
                break
    std_clock = next(r[2] for r in CUSTOM_ROWS if r[0] == sex and r[1] == event)
    return 100.0 * (secs(std_clock) / f) / time_s


# ---------------------------------------------------------------------------
# sheet helpers
# ---------------------------------------------------------------------------
def title(ws, text: str, sub: str | None = None) -> int:
    ws["A1"] = text
    ws["A1"].font = F_TITLE
    r = 2
    if sub:
        ws["A2"] = sub
        ws["A2"].font = F_NOTE
        r = 3
    return r + 1


def header_row(ws, row: int, labels: list[str], start_col: int = 1) -> None:
    for j, label in enumerate(labels):
        c = ws.cell(row=row, column=start_col + j, value=label)
        c.font, c.fill, c.alignment, c.border = F_HDR, FILL_HDR, CENTER, BOX
    ws.row_dimensions[row].height = 28


def subhead(ws, row: int, text: str) -> None:
    c = ws.cell(row=row, column=1, value=text)
    c.font = F_H2
    for j in range(1, 9):
        ws.cell(row=row, column=j).fill = FILL_SUB
    c.alignment = LEFT


def widths(ws, spec: dict[str, int]) -> None:
    for col, w in spec.items():
        ws.column_dimensions[col].width = w


def live(ws, ref: str, formula: str, fmt: str | None = None,
         ref_range: str | None = None):
    """A live AG.* formula, optionally as a legacy array formula over `ref_range`."""
    if ref_range:
        ws[ref] = ArrayFormula(ref=ref_range, text=formula)
    else:
        ws[ref] = formula
    block = ws[ref_range] if ref_range else ((ws[ref],),)
    for row in block:
        for c in (row if isinstance(row, tuple) else (row,)):
            c.fill, c.border, c.alignment = FILL_LIVE, BOX, CENTER
            c.font = F_MONO
            if fmt:
                c.number_format = fmt


def expected(ws, ref: str, value, fmt: str | None = None):
    c = ws[ref]
    c.value = value
    c.fill, c.border, c.alignment, c.font = FILL_EXP, BOX, CENTER, F_BODY
    if fmt:
        c.number_format = fmt


def note(ws, ref: str, text: str):
    c = ws[ref]
    c.value = text
    c.font, c.alignment = F_NOTE, LEFT


# ---------------------------------------------------------------------------
# sheet 0 — start here
# ---------------------------------------------------------------------------
def sheet_start(wb: Workbook) -> None:
    ws = wb.worksheets[0]
    ws.title = "Start here"
    ws.sheet_properties.tabColor = NAVY
    ws.sheet_view.showGridLines = False
    widths(ws, {"A": 3, "B": 26, "C": 96})

    r = title(ws, "Age grading in Excel — sample workbook",
              "for xll_age_grading.xll  ·  USATF MLDR 2025 road tables  ·  "
              "every value below is regenerated by build_sample_workbook.py")

    blocks = [
        ("Before you start", [
            "Install the add-in: File > Options > Add-ins > Manage: Excel Add-ins > Go > Browse… "
            "and pick xll_age_grading.xll. If the file came from another machine, right-click it "
            "> Properties > Unblock first.",
            "If every AG. cell shows #NAME?, the add-in is not loaded. Nothing else on that sheet "
            "will be correct until it is.",
            "If a cell shows #NUM!, put =AG.LASTERROR() in the next cell: it explains the failure "
            "in words (which row, which argument, why).",
        ]),
        ("How to read the sheets", [
            "Pale blue cells are live AG.* formulas — they are the point of the exercise.",
            "Grey cells are the expected answer, computed by the Python implementation in this "
            "repository (verified against the published calculator: tools/verify.py).",
            "Green cells say OK or MISMATCH. A MISMATCH is a real disagreement between the add-in "
            "and the reference implementation — send it back as a bug.",
            "Cream cells are inputs. Change them and watch the blue cells follow.",
        ]),
        ("About the array formulas", [
            "The multi-cell demos (spilled columns, AG.BLOCK) are stored as legacy array formulas "
            "(Ctrl+Shift+Enter) over an exact range, so they work in Excel 2010 and later as well "
            "as in Excel 365.",
            "In Excel 365 you can delete one and retype it in a single cell: it spills on its own.",
            "An array formula locks its output range. If a spilled range ever shows #N/A at the "
            "bottom, the range is bigger than the result — resize it.",
        ]),
        ("What is underneath", [
            "Four published editions are compiled into the add-in: 2025, 2020, 2015, 2010. The fifth "
            "argument of any grading function picks one; the default is the newest.",
            "The 2025 tables are Alan Jones's, with single-age bests by Tom Bernhard, approved by "
            "the USATF MLDR Council on 2025-01-10; the calculator they ship with is Howard Grubb's. "
            "Quote the table year alongside any percentage you publish: the tables are refitted "
            "periodically and the same run does not score the same in every edition.",
            "Documentation for the algorithm, the tables and this add-in lives in docs/ and xll/docs/ "
            "in the repository.",
        ]),
    ]

    for heading, lines in blocks:
        ws.cell(row=r, column=2, value=heading).font = F_H2
        r += 1
        for line in lines:
            c = ws.cell(row=r, column=2, value="\u2022")
            c.font, c.alignment = F_BODY, TOP_CENTRE
            tc = ws.cell(row=r, column=3, value=line)
            tc.font, tc.alignment = F_BODY, LEFT_WRAP
            ws.row_dimensions[r].height = 15 * max(1, len(line) // 92 + 1)
            r += 1
        r += 1

    ws.cell(row=r, column=2, value="The sheets").font = F_H2
    r += 1
    header_row(ws, r, ["Sheet", "What it demonstrates"], start_col=2)
    index = [
        ("1 Squad", "Grading a whole squad: one formula per column, and AG.BLOCK spilling five "
                    "columns at once. Club summary formulas on top of the results."),
        ("2 One call", "Every function with scalar arguments: AG.GRADE, AG.GRADEDTIME, AG.FACTOR, "
                       "AG.STANDARD, AG.TIMEFORPCT, plus the diagnostics AG.TABLES, AG.TABLEINFO, "
                       "AG.CACHEINFO, AG.CACHECLEAR, AG.LASTERROR, AG.VERSION."),
        ("3 Editions", "The same run graded on 2025, 2020, 2015 and 2010 — and why a percentage "
                       "without a year is not an answer."),
        ("4 Vector rules", "Broadcast vs vector, the length-mismatch error, blank rows, bad rows, "
                           "age clamping and interpolation, three ways to write a time."),
        ("5 Custom tables", "Ad hoc tables from a range: the matrix layout and the long layout, "
                            "with OpenStd optional, and a sidecar CSV."),
        ("6 Times & formats", "Seconds, Excel time values and [h]:mm:ss; the inverse function; "
                              "round-tripping a percentage."),
        ("7 Reference", "Distances the tables cover, argument rules, and what every error means."),
    ]
    for name, what in index:
        r += 1
        c1 = ws.cell(row=r, column=2, value=name)
        c1.font, c1.alignment, c1.border = F_BODY, LEFT, BOX
        c2 = ws.cell(row=r, column=3, value=what)
        c2.font, c2.alignment, c2.border = F_BODY, LEFT_WRAP, BOX
        ws.row_dimensions[r].height = 15 * max(1, len(what) // 92 + 1)

    r += 3
    note(ws, f"C{r}", "Sample workbook generated by xll/examples/build_sample_workbook.py — "
                      "regenerate it rather than editing values by hand.")
    ws.page_setup.orientation = "landscape"
    ws.page_setup.fitToWidth = 1


# ---------------------------------------------------------------------------
# sheet 1 — the squad
# ---------------------------------------------------------------------------
SQUAD = [
    ("T. Mokoena", "M", 47, 10.0, "39:40"),
    ("A. van Wyk", "F", 34, 10.0, "44:15"),
    ("J. Ndlovu", "M", 61, 21.0975, "1:52:30"),
    ("M. Fortuin", "F", 29, 42.195, "3:28:10"),
    ("P. September", "M", 38, 21.0975, "1:24:55"),
    ("L. Khumalo", "F", 52, 10.0, "51:02"),
    ("D. Malan", "M", 72, 10.0, "57:20"),
    ("S. Adams", "F", 41, 5.0, "22:48"),
    ("N. Botha", "M", 19, 5.0, "15:02"),
    ("R. Isaacs", "M", 55, 42.195, "3:12:40"),
    ("K. Jacobs", "F", 66, 21.0975, "2:28:05"),
    ("H. Smit", "M", 28, 12.0, "46:30"),
]


def sheet_squad(wb: Workbook) -> None:
    ws = wb.create_sheet("1 Squad")
    widths(ws, {"A": 16, "B": 6, "C": 6, "D": 9, "E": 10, "F": 11, "G": 11,
                "H": 11, "I": 13, "J": 10, "K": 13, "L": 2,
                "M": 10, "N": 12, "O": 12, "P": 12, "Q": 10})

    r = title(ws, "Grading a squad",
              "Twelve athletes. Columns F, I, J and K are four separate formulas, each entered "
              "once and spilling down. Columns M-Q are a single AG.BLOCK call. Only column G is "
              "a fixed expected value; the rest are live.")

    header_row(ws, 4, ["Athlete", "Sex", "Age", "Dist km", "Time",
                       "AG.GRADE %", "expected %", "check",
                       "AG.GRADEDTIME", "AG.FACTOR", "AG.STANDARD"], start_col=1)
    header_row(ws, 4, ["factor", "open std", "age std", "graded", "percent"], start_col=13)

    first, last = 5, 4 + len(SQUAD)
    for i, (name, sex, age, dist, t) in enumerate(SQUAD):
        row = first + i
        for col, value, fmt, fill in (
            ("A", name, None, FILL_IN),
            ("B", sex, None, FILL_IN),
            ("C", age, "0", FILL_IN),
            ("D", dist, "0.0000", FILL_IN),
            ("E", serial(t), TIME_FMT, FILL_IN),
        ):
            c = ws[f"{col}{row}"]
            c.value = value
            c.number_format = fmt or "General"
            c.fill, c.border = fill, BOX
            c.font = F_BODY
            c.alignment = LEFT if col == "A" else CENTER
        g = grade(sex, age, dist, secs(t))
        expected(ws, f"G{row}", round(g.percent, 4), PCT_FMT)

    # four separate formulas, each entered once
    live(ws, f"F{first}", f"=AG.GRADE($B${first}:$B${last},$C${first}:$C${last},"
                          f"$D${first}:$D${last},$E${first}:$E${last})",
         PCT_FMT, ref_range=f"F{first}:F{last}")
    live(ws, f"I{first}", f"=AG.GRADEDTIME($B${first}:$B${last},$C${first}:$C${last},"
                          f"$D${first}:$D${last},$E${first}:$E${last})",
         TIME_FMT, ref_range=f"I{first}:I{last}")
    live(ws, f"J{first}", f"=AG.FACTOR($B${first}:$B${last},$C${first}:$C${last},"
                          f"$D${first}:$D${last})",
         FAC_FMT, ref_range=f"J{first}:J{last}")
    live(ws, f"K{first}", f"=AG.STANDARD($B${first}:$B${last},$C${first}:$C${last},"
                          f"$D${first}:$D${last})",
         TIME_FMT, ref_range=f"K{first}:K{last}")
    # one call, five columns
    live(ws, f"M{first}", f"=AG.BLOCK($B${first}:$B${last},$C${first}:$C${last},"
                          f"$D${first}:$D${last},$E${first}:$E${last})",
         None, ref_range=f"M{first}:Q{last}")
    for i in range(len(SQUAD)):
        row = first + i
        ws[f"M{row}"].number_format = FAC_FMT
        for col in "NOP":
            ws[f"{col}{row}"].number_format = TIME_FMT
        ws[f"Q{row}"].number_format = PCT_FMT
        c = ws[f"H{row}"]
        c.value = f'=IF(ABS(F{row}-G{row})<0.01,"OK","MISMATCH")'
        c.fill, c.border, c.alignment, c.font = FILL_CHECK, BOX, CENTER, F_BODY

    # do the two entry styles agree with each other?
    row = last + 1
    ws.cell(row=row, column=1,
            value="AG.BLOCK percent agrees with AG.GRADE column").font = F_H2
    c = ws[f"H{row}"]
    c.value = (f'=IF(SUMPRODUCT(--(ABS(Q{first}:Q{last}-F{first}:F{last})>0.01))=0,'
               f'"OK","MISMATCH")')
    c.fill, c.border, c.alignment, c.font = FILL_CHECK, BOX, CENTER, F_BODY

    row += 1
    ws.cell(row=row, column=1,
            value="AG.BLOCK graded time agrees with AG.GRADEDTIME").font = F_H2
    c = ws[f"H{row}"]
    c.value = (f'=IF(SUMPRODUCT(--(ABS(P{first}:P{last}-I{first}:I{last})*86400>1))=0,'
               f'"OK","MISMATCH")')
    c.fill, c.border, c.alignment, c.font = FILL_CHECK, BOX, CENTER, F_BODY

    # club summary, built only from the live column
    r = row + 2
    subhead(ws, r, "Club summary — these use the live column F, not the expected numbers")
    rows = [
        ("Athletes graded", f"=COUNT(F{first}:F{last})", "0"),
        ("Average age grade", f"=AVERAGE(F{first}:F{last})", PCT_FMT),
        ("Median age grade", f"=MEDIAN(F{first}:F{last})", PCT_FMT),
        ("Best age grade", f"=MAX(F{first}:F{last})", PCT_FMT),
        ("Best athlete", f'=INDEX(A{first}:A{last},MATCH(MAX(F{first}:F{last}),'
                         f'F{first}:F{last},0))', None),
        ("Athletes at 70% or better", f'=COUNTIF(F{first}:F{last},">=70")', "0"),
        ("Athletes below 50%", f'=COUNTIF(F{first}:F{last},"<50")', "0"),
    ]
    for label, formula, fmt in rows:
        r += 1
        ws.cell(row=r, column=1, value=label).font = F_BODY
        c = ws.cell(row=r, column=6, value=formula)
        c.fill, c.border, c.alignment, c.font = FILL_LIVE, BOX, CENTER, F_MONO
        if fmt:
            c.number_format = fmt
        if label == "Best athlete":
            c.alignment = LEFT

    r += 2
    note(ws, f"A{r}", "Sort by column F to rank the club, or by column J to see who ran closest "
                      "to their age standard. Column J is the honest measure of effort across "
                      "different ages; column F is the one to publish.")
    ws.freeze_panes = "A5"
    ws.page_setup.orientation = "landscape"
    ws.page_setup.fitToWidth = 1


# ---------------------------------------------------------------------------
# sheet 2 — every function, one call at a time
# ---------------------------------------------------------------------------
def sheet_functions(wb: Workbook) -> None:
    ws = wb.create_sheet("2 One call")
    widths(ws, {"A": 20, "B": 34, "C": 14, "D": 13, "E": 11, "F": 14, "G": 11,
                "H": 44, "I": 12, "J": 12})
    r = title(ws, "Every function, scalar arguments",
              "One row per call. Column C is live, D is the expected answer, E is the verdict.")

    def note_block(row: int, text: str) -> None:
        """Prose in F:J, so it never squeezes a numeric column."""
        c = ws.cell(row=row, column=6, value=text)
        c.font, c.alignment = F_BODY, LEFT_WRAP
        ws.merge_cells(start_row=row, start_column=6, end_row=row, end_column=10)
        ws.row_dimensions[row].height = 15 * max(1, len(text) // 78 + 1)

    subhead(ws, 4, "The five grading functions")
    header_row(ws, 5, ["Function", "Arguments", "live", "expected", "check"])
    c = ws.cell(row=5, column=6, value="What it means")
    c.font, c.fill, c.alignment, c.border = F_HDR, FILL_HDR, CENTER, BOX
    ws.merge_cells(start_row=5, start_column=6, end_row=5, end_column=10)

    rows = [
        ("AG.GRADE", 'M, 40, 10 km, 40:00', '=AG.GRADE("M",40,10,0.0277777777777778)',
         grade("M", 40, 10.0, 2400).percent, PCT_FMT,
         "The age grade in percent. 100 = the world-standard mark for that exact sex and age."),
        ("AG.GRADE", 'F, 56, 10 km, 50:00', '=AG.GRADE("F",56,10,"50:00")',
         grade("F", 56, 10.0, 3000).percent, PCT_FMT,
         "A time written as text is read as mm:ss - no need to type 0:50:00."),
        ("AG.GRADE", 'M, 75, marathon, 4:30:00', '=AG.GRADE("M",75,42.195,"4:30:00")',
         grade("M", 75, 42.195, 16200).percent, PCT_FMT,
         "Masters score well above 50%: the tables assume a steep decline after 35."),
        ("AG.GRADE", 'F, 26, 5 km, 18:30', '=AG.GRADE("F",26,5,"18:30")',
         grade("F", 26, 5.0, 1110).percent, PCT_FMT,
         "Above 100% is a real answer and is never clamped - a whole age band over 100 means "
         "the table is soft there."),
        ("AG.GRADEDTIME", 'M, 40, 10 km, 40:00', '=AG.GRADEDTIME("M",40,10,"40:00")',
         grade("M", 40, 10.0, 2400).age_graded_s / 86400.0, TIME_FMT,
         "The same run converted to open-class age: time x factor."),
        ("AG.FACTOR", 'F, 56, 10 km', '=AG.FACTOR("F",56,10)',
         grade("F", 56, 10.0, 3000).factor, FAC_FMT,
         "The multiplier from the table. Bigger age = smaller factor = more generous."),
        ("AG.STANDARD", 'M, 40, 10 km', '=AG.STANDARD("M",40,10)',
         tbl("M").event("10kmRoad").standard_s / 86400.0, TIME_FMT,
         "The open standard for the distance (26:24 for a male 10 km). Age is ignored: it is "
         "accepted only so the signature matches its siblings."),
        ("AG.STANDARD", 'F, 40, half marathon', '=AG.STANDARD("F",40,21.0975)',
         tbl("F").event("Half.Mar").standard_s / 86400.0, TIME_FMT,
         'Distance can be given in km or as a name; 21.0975 and "half" are the same thing.'),
        ("AG.TIMEFORPCT", 'M, 40, 10 km, 68.49%', '=AG.TIMEFORPCT("M",40,10,68.49)',
         tbl("M").time_for_percent("M", 40, 68.49, dist_km=10.0) / 86400.0, TIME_FMT,
         "The inverse: the time that would score that percentage. This is the calculator's "
         "Result button."),
        ("AG.TIMEFORPCT", 'F, 52, half, 80%', '=AG.TIMEFORPCT("F",52,21.0975,80)',
         tbl("F").time_for_percent("F", 52, 80, dist_km=21.0975) / 86400.0, TIME_FMT,
         "How you set a club badge: pick the percentage, get the target time per age."),
    ]
    for i, (fn, args, formula, exp, fmt, why) in enumerate(rows):
        row = 6 + i
        for col, value in (("A", fn), ("B", args)):
            c = ws[f"{col}{row}"]
            c.value, c.font, c.alignment, c.border = value, F_MONO, LEFT_WRAP, BOX
        live(ws, f"C{row}", formula, fmt)
        expected(ws, f"D{row}", round(exp, 6), fmt)
        c = ws[f"E{row}"]
        scale = "*86400" if fmt == TIME_FMT else ""
        tol = "1" if fmt == TIME_FMT else "0.01"
        c.value = f'=IF(ABS(C{row}-D{row}){scale}<{tol},"OK","MISMATCH")'
        c.fill, c.border, c.alignment, c.font = FILL_CHECK, BOX, CENTER, F_BODY
        note_block(row, why)

    # ---- diagnostics ----
    r = 6 + len(rows) + 2
    subhead(ws, r, "Diagnostics: which tables are available, and what did the last call complain about")
    header_row(ws, r + 1, ["Function", "Arguments", "live (1-4)", "", "", "", "check"])
    ws.merge_cells(start_row=r + 1, start_column=3, end_row=r + 1, end_column=6)
    c = ws.cell(row=r + 1, column=8, value="What it means")
    c.font, c.fill, c.alignment, c.border = F_HDR, FILL_HDR, CENTER, BOX
    ws.merge_cells(start_row=r + 1, start_column=8, end_row=r + 1, end_column=10)
    c = ws.cell(row=r + 1, column=7, value="check")
    c.font, c.fill, c.alignment, c.border = F_HDR, FILL_HDR, CENTER, BOX

    row = r + 2
    for fn, args, formula, exp, why in (
        ("AG.TABLES", "(none)", "=AG.TABLES()", [2025, 2020, 2015, 2010],
         "The editions compiled into this build, newest first. Any of them can be the fifth "
         "argument of a grading function."),
        ("AG.TABLEINFO", "(default table)", "=AG.TABLEINFO()", [2025, 22, 96, 2],
         "One row: year, distances, ages, sexes."),
        ("AG.TABLEINFO", "2020", "=AG.TABLEINFO(2020)", [2020, 22, 96, 2],
         "The same for the 2020 edition - the tables that were in force then."),
    ):
        for col, value in (("A", fn), ("B", args)):
            c = ws[f"{col}{row}"]
            c.value, c.font, c.border, c.alignment = value, F_MONO, BOX, LEFT
        live(ws, f"C{row}", formula, None, ref_range=f"C{row}:F{row}")
        c = ws[f"G{row}"]
        c.value = (f'=IF(SUMPRODUCT(--(ABS(C{row}:F{row}-C{row + 1}:F{row + 1})>0.0001))=0,'
                   f'"OK","MISMATCH")')
        c.fill, c.border, c.alignment, c.font = FILL_CHECK, BOX, CENTER, F_BODY
        for j, v in enumerate(exp):
            expected(ws, f"{get_column_letter(3 + j)}{row + 1}", v, "0")
        ws[f"A{row + 1}"].value = "expected"
        ws[f"A{row + 1}"].font, ws[f"A{row + 1}"].alignment = F_NOTE, LEFT
        c = ws.cell(row=row, column=8, value=why)
        c.font, c.alignment = F_BODY, LEFT_WRAP
        ws.merge_cells(start_row=row, start_column=8, end_row=row, end_column=10)
        ws.row_dimensions[row].height = 30
        row += 2

    for fn, args, formula, exp_text, why, check in (
        ("AG.LASTERROR", "(none)", "=AG.LASTERROR()",
         "text: 'no error', or the reason for the most recent failure",
         "The explanation for the last failed call - the first thing to reach for when a "
         "column fills with #NUM!. Its value depends on what failed last, so the check only "
         "asks that it is text; sheet 4 shows it next to a known failure.",
         '=IF(ISTEXT({c}),"OK","MISMATCH")'),
        ("AG.VERSION", "(none)", "=AG.VERSION()",
         "aggrade-xll 2025.1 (4 built-in editions)",
         "Add-in version and how many editions are compiled in.",
         '=IF(EXACT({c},D{r}),"OK","MISMATCH")'),
    ):
        for col, value in (("A", fn), ("B", args)):
            c = ws[f"{col}{row}"]
            c.value, c.font, c.border, c.alignment = value, F_MONO, BOX, LEFT
        live(ws, f"C{row}", formula, None)
        expected(ws, f"D{row}", exp_text)
        c = ws[f"E{row}"]
        c.value = check.format(c=f"C{row}", r=row)
        c.fill, c.border, c.alignment, c.font = FILL_CHECK, BOX, CENTER, F_BODY
        note_block(row, why)

    # AG.CACHEINFO live; AG.CACHECLEAR shown but not live, because a live one
    # would empty the cache on every recalculation and defeat the demo.
    for col, value in (("A", "AG.CACHEINFO"), ("B", "(none)")):
        c = ws[f"{col}{row}"]
        c.value, c.font, c.border, c.alignment = value, F_MONO, BOX, LEFT
    live(ws, f"C{row}", "=AG.CACHEINFO()", None, ref_range=f"C{row}:H{row}")
    note_block(row, "Six counters: built-in editions, loaded CSVs, custom ranges held, cache "
                    "hits, misses, capacity. No expected values - they depend on what this "
                    "workbook has done. Recalculate and watch the hit count climb: a range table "
                    "is parsed once, not once per cell.")
    row += 1

    for col, value in (("A", "AG.CACHECLEAR"), ("B", "(none)")):
        c = ws[f"{col}{row}"]
        c.value, c.font, c.border, c.alignment = value, F_MONO, BOX, LEFT
    c = ws[f"C{row}"]
    c.value = "AG.CACHECLEAR()"
    c.font, c.border, c.alignment = F_MONO, BOX, LEFT
    ws[f"D{row}"].value = "returns 1"
    ws[f"D{row}"].font, ws[f"D{row}"].alignment = F_NOTE, LEFT
    note_block(row, "Not live on purpose: it drops cached CSV and custom-range tables, so a live "
                    "copy would empty the cache on every recalculation. Type it when you need it "
                    "- after editing a table CSV. Ad hoc ranges are keyed by a hash of their "
                    "contents and can never go stale, so only CSVs need this.")

    ws.freeze_panes = "A6"
    ws.page_setup.orientation = "landscape"
    ws.page_setup.fitToWidth = 1


# ---------------------------------------------------------------------------
# sheet 3 — editions
# ---------------------------------------------------------------------------
def sheet_editions(wb: Workbook) -> None:
    ws = wb.create_sheet("3 Editions")
    widths(ws, {"A": 12, "B": 17, "C": 12, "D": 13, "E": 12, "F": 58})
    r = title(ws, "Which tables? The year is part of the answer",
              "One athlete — female, 45, half marathon in 1:45:00 — graded on every edition.")

    header_row(ws, 4, ["Edition", "table argument", "live %", "expected %", "vs 2025 (pp)",
                       "Note"])
    editions = [2025, 2020, 2015, 2010]
    base = grade("F", 45, 21.0975, 6300, 2025).percent
    for i, year in enumerate(editions):
        row = 5 + i
        ws[f"A{row}"].value = year
        ws[f"A{row}"].number_format = "0"
        ws[f"A{row}"].font, ws[f"A{row}"].border = F_BODY, BOX
        ws[f"A{row}"].alignment = CENTER
        ws[f"B{row}"].value = f'"{year}"'
        ws[f"B{row}"].font, ws[f"B{row}"].border = F_MONO, BOX
        ws[f"B{row}"].alignment = LEFT
        live(ws, f"C{row}", f'=AG.GRADE("F",45,21.0975,"1:45:00","{year}")', PCT_FMT)
        g = grade("F", 45, 21.0975, 6300, year)
        expected(ws, f"D{row}", round(g.percent, 4), PCT_FMT)
        c = ws[f"E{row}"]
        c.value = f"=C{row}-$C$5"
        c.number_format = "+0.00;-0.00;0.00"
        c.fill, c.border, c.alignment, c.font = FILL_EXP, BOX, CENTER, F_BODY
        notes = {
            2025: "Current edition (approved 2025-01-10). Use this unless you have a reason not to.",
            2020: "What the tables said before the 2025 refit — quote it for races graded at the time.",
            2015: "The WMA-derived tables that preceded the 2020 refit.",
            2010: "The oldest edition compiled in; useful for historical comparisons only.",
        }
        c = ws[f"F{row}"]
        c.value = notes[year]
        c.font, c.alignment, c.border = F_BODY, LEFT_WRAP, BOX

    r = 11
    subhead(ws, r, "The table name can be a number or text")
    header_row(ws, r + 1, ["Call", "live %", "expected %", "check", "Note"])
    live(ws, f"B{r + 2}", '=AG.GRADE("F",45,21.0975,"1:45:00",2020)', PCT_FMT)
    expected(ws, f"C{r + 2}", round(grade("F", 45, 21.0975, 6300, 2020).percent, 4), PCT_FMT)
    c = ws[f"D{r + 2}"]
    c.value = f'=IF(ABS(B{r + 2}-C{r + 2})<0.01,"OK","MISMATCH")'
    c.fill, c.border, c.alignment, c.font = FILL_CHECK, BOX, CENTER, F_BODY
    ws[f"A{r + 2}"].value = '2020 (a number)'
    ws[f"A{r + 2}"].font, ws[f"A{r + 2}"].border = F_MONO, BOX
    ws[f"E{r + 2}"].value = "A numeric table argument is coerced to its name."
    ws[f"E{r + 2}"].font, ws[f"E{r + 2}"].alignment = F_BODY, LEFT_WRAP

    live(ws, f"B{r + 3}", '=AG.GRADE("F",45,21.0975,"1:45:00","latest")', PCT_FMT)
    expected(ws, f"C{r + 3}", round(base, 4), PCT_FMT)
    c = ws[f"D{r + 3}"]
    c.value = f'=IF(ABS(B{r + 3}-C{r + 3})<0.01,"OK","MISMATCH")'
    c.fill, c.border, c.alignment, c.font = FILL_CHECK, BOX, CENTER, F_BODY
    ws[f"A{r + 3}"].value = '"latest"'
    ws[f"A{r + 3}"].font, ws[f"A{r + 3}"].border = F_MONO, BOX
    ws[f"E{r + 3}"].value = "Newest compiled edition — what you want in a template that must not rot."
    ws[f"E{r + 3}"].font, ws[f"E{r + 3}"].alignment = F_BODY, LEFT_WRAP

    live(ws, f"B{r + 4}", '=AG.GRADE("F",45,21.0975,"1:45:00","1999")', PCT_FMT)
    ws[f"A{r + 4}"].value = '"1999"'
    ws[f"A{r + 4}"].font, ws[f"A{r + 4}"].border = F_MONO, BOX
    ws[f"C{r + 4}"].value = "#NUM!"
    ws[f"C{r + 4}"].font, ws[f"C{r + 4}"].alignment = F_BODY, CENTER
    ws[f"E{r + 4}"].value = "An edition that is not compiled in fails the whole call; AG.LASTERROR() names it."
    ws[f"E{r + 4}"].font, ws[f"E{r + 4}"].alignment = F_BODY, LEFT_WRAP

    r += 6
    note(ws, f"A{r}", "The 2025 review re-fitted the male 5 km and 10 km curves, so percentages "
                      "for those distances move the most between editions. Always publish the "
                      "edition year with the percentage — a grade without a year is not an answer.")
    ws.page_setup.orientation = "landscape"
    ws.page_setup.fitToWidth = 1


# ---------------------------------------------------------------------------
# sheet 4 — vector rules and edge cases
# ---------------------------------------------------------------------------
def sheet_vectors(wb: Workbook) -> None:
    ws = wb.create_sheet("4 Vector rules")
    widths(ws, {"A": 34, "B": 30, "C": 13, "D": 13, "E": 12, "F": 54})
    r = title(ws, "Vector rules, edge cases and errors",
              "The rules the add-in enforces on every call: scalars broadcast, vectors must "
              "match, bad rows fail alone.")

    subhead(ws, 4, "Alignment")
    header_row(ws, 5, ["Call", "why", "live", "expected", "check", "Result"])
    rows = [
        ('=AG.FACTOR("M",{40;50;60;70},10)',
         "A scalar sex and a scalar distance broadcast against a column of ages",
         None, "four factors, one per age"),
        ('=AG.GRADE(C9:C12,C9:C12,10,2400)',
         "Every vector the same length: 4 rows in, 4 rows out",
         None, "one grade per row"),
    ]
    # vector demo 1: ages as a column in B
    for i, age in enumerate([40, 50, 60, 70]):
        ws[f"B{6 + i}"].value = age
        ws[f"B{6 + i}"].number_format = "0"
        ws[f"B{6 + i}"].fill, ws[f"B{6 + i}"].border = FILL_IN, BOX
        ws[f"B{6 + i}"].font, ws[f"B{6 + i}"].alignment = F_BODY, CENTER
    ws["A6"].value = '=AG.FACTOR("M",B6:B9,10)'
    ws["A6"].font, ws["A6"].border = F_MONO, BOX
    live(ws, "C6", "=AG.FACTOR(\"M\",B6:B9,10)", FAC_FMT, ref_range="C6:F6")
    for j, age in enumerate([40, 50, 60, 70]):
        expected(ws, f"{get_column_letter(3 + j)}7",
                 round(grade("M", age, 10.0, 2400).factor, 4), FAC_FMT)
    ws["G6"].value = ("Scalar sex and scalar distance broadcast; the four ages each get their own "
                      "factor. Expected values sit below, at C7:F7.")
    ws["G6"].font, ws["G6"].alignment = F_BODY, LEFT_WRAP
    ws["G7"].value = "=IF(SUMPRODUCT(--(ABS(C6:F6-C7:F7)>0.0001))=0,\"OK\",\"MISMATCH\")"
    ws["G7"].fill, ws["G7"].border, ws["G7"].alignment, ws["G7"].font = (
        FILL_CHECK, BOX, CENTER, F_BODY)

    # ---- length mismatch ----
    r = 10
    subhead(ws, r, "The one rule that is not Excel-like: vectors must be the same length")
    ws[f"A{r + 1}"].value = '=AG.GRADE("M",{40;50;60},10,{2400;2500})'
    ws[f"A{r + 1}"].font, ws[f"A{r + 1}"].border = F_MONO, BOX
    live(ws, f"B{r + 1}", '=AG.GRADE("M",{40;50;60},10,{2400;2500})', PCT_FMT)
    ws[f"C{r + 1}"].value = "#NUM!"
    ws[f"C{r + 1}"].font, ws[f"C{r + 1}"].alignment = F_BODY, CENTER
    ws[f"D{r + 1}"].value = '=AG.LASTERROR()'
    ws[f"D{r + 1}"].font, ws[f"D{r + 1}"].border = F_MONO, BOX
    ws[f"D{r + 1}"].fill = FILL_LIVE
    ws[f"E{r + 1}"].value = ("Three ages and two times. The call fails as a whole and AG.LASTERROR() "
                             "names both arguments and both counts — deliberately not Excel-style "
                             "broadcasting, which would pair one athlete's age with another's time.")
    ws[f"E{r + 1}"].font, ws[f"E{r + 1}"].alignment = F_BODY, LEFT_WRAP
    ws.row_dimensions[r + 1].height = 46

    # ---- blank and bad rows ----
    r += 3
    subhead(ws, r, "One bad row does not poison the column")
    header_row(ws, r + 1, ["Sex", "Age", "Dist km", "Time", "live %", "expected %"])
    cases = [
        ("M", 40, 10.0, "40:00", "a normal row"),
        ("M", 40, 10.0, None, "blank time: the row stays empty, no error"),
        ("M", 40, 500.0, "40:00", "distance outside 1 mile - 200 km: this row only fails"),
        ("X", 40, 10.0, "40:00", "unreadable sex: this row only fails"),
        ("M", 40, 10.0, "40:00", "a good row after two bad ones"),
    ]
    first = r + 2
    for i, (sex, age, dist, t, why) in enumerate(cases):
        row = first + i
        for col, value, fmt, fill in (("A", sex, None, FILL_IN), ("B", age, "0", FILL_IN),
                                      ("C", dist, "0.0000", FILL_IN)):
            c = ws[f"{col}{row}"]
            c.value, c.number_format, c.fill, c.border = value, fmt or "General", fill, BOX
            c.font, c.alignment = F_BODY, CENTER
        if t:
            c = ws[f"D{row}"]
            c.value, c.number_format = serial(t), TIME_FMT
        c.fill, c.border, c.font, c.alignment = FILL_IN, BOX, F_BODY, CENTER
        ws[f"G{row}"].value = why
        ws[f"G{row}"].font, ws[f"G{row}"].alignment = F_BODY, LEFT_WRAP
        if t and sex in ("M", "F") and dist <= 200:
            expected(ws, f"F{row}", round(grade(sex, age, dist, secs(t)).percent, 4), PCT_FMT)
        else:
            ws[f"F{row}"].value = "#NUM!" if t else "(empty)"
            ws[f"F{row}"].font, ws[f"F{row}"].alignment = F_BODY, CENTER
    live(ws, f"E{first}",
         f"=AG.GRADE($A${first}:$A${first + 4},$B${first}:$B${first + 4},"
         f"$C${first}:$C${first + 4},$D${first}:$D${first + 4})",
         PCT_FMT, ref_range=f"E{first}:E{first + 4}")

    # ---- age rules ----
    r = first + len(cases) + 2
    subhead(ws, r, "Ages: clamped at the ends, interpolated in between")
    header_row(ws, r + 1, ["Age", "live %", "expected %", "check", "why"])
    age_cases = [
        (3, "Below 5 the age-5 factors are used (clamped, not extrapolated)."),
        (5, "The youngest published age."),
        (40.5, "Fractional ages interpolate — unlike the VBA, which rounded them (age As Integer)."),
        (99.5, "Above 99 the age-100 factors are used: a faithful quirk of the published "
               "calculator, preserved so results match it exactly."),
        (105, "Above 100 the age-100 factors are used."),
    ]
    a0 = r + 2
    for i, (age, why) in enumerate(age_cases):
        row = a0 + i
        c = ws[f"A{row}"]
        c.value, c.number_format, c.fill, c.border = age, "0.0", FILL_IN, BOX
        c.font, c.alignment = F_BODY, CENTER
        live(ws, f"B{row}", f'=AG.GRADE("M",A{row},10,"40:00")', PCT_FMT)
        expected(ws, f"C{row}", round(grade("M", age, 10.0, 2400).percent, 4), PCT_FMT)
        c = ws[f"D{row}"]
        c.value = f'=IF(ABS(B{row}-C{row})<0.01,"OK","MISMATCH")'
        c.fill, c.border, c.alignment, c.font = FILL_CHECK, BOX, CENTER, F_BODY
        ws[f"E{row}"].value = why
        ws[f"E{row}"].font, ws[f"E{row}"].alignment = F_BODY, LEFT_WRAP
        ws.row_dimensions[row].height = 30 if len(why) > 60 else 15

    # ---- time formats ----
    r = a0 + len(age_cases) + 2
    subhead(ws, r, "Three ways to write forty minutes — all the same performance")
    header_row(ws, r + 1, ["Written as", "live %", "expected %", "check", "why"])
    t0 = r + 2
    time_cases = [
        ("Excel time 0:40:00", serial("40:00"), "A time value is stored as a fraction of a day."),
        ('text "40:00"', "40:00", "Text is parsed as mm:ss, or h:mm:ss when there are three parts."),
        ("number 2400", 2400, "A number of 1 or more is read as seconds; below 1 it is a time serial."),
    ]
    for i, (label, value, why) in enumerate(time_cases):
        row = t0 + i
        c = ws[f"A{row}"]
        c.value, c.fill, c.border, c.font, c.alignment = label, FILL_IN, BOX, F_BODY, LEFT
        if isinstance(value, float):
            ws[f"B{row}"].value = value
            ws[f"B{row}"].number_format = TIME_FMT
        else:
            ws[f"B{row}"].value = value
        ws[f"B{row}"].fill, ws[f"B{row}"].border = FILL_IN, BOX
        ws[f"B{row}"].font, ws[f"B{row}"].alignment = F_BODY, CENTER
        live(ws, f"C{row}", f'=AG.GRADE("M",40,10,B{row})', PCT_FMT)
        expected(ws, f"D{row}", round(grade("M", 40, 10.0, 2400).percent, 4), PCT_FMT)
        c = ws[f"E{row}"]
        c.value = f'=IF(ABS(C{row}-D{row})<0.01,"OK","MISMATCH")'
        c.fill, c.border, c.alignment, c.font = FILL_CHECK, BOX, CENTER, F_BODY
        ws[f"F{row}"].value = why
        ws[f"F{row}"].font, ws[f"F{row}"].alignment = F_BODY, LEFT_WRAP

    ws.page_setup.orientation = "landscape"
    ws.page_setup.fitToWidth = 1


# ---------------------------------------------------------------------------
# sheet 5 — custom tables
# ---------------------------------------------------------------------------
def sheet_custom(wb: Workbook) -> None:
    ws = wb.create_sheet("5 Custom tables")
    widths(ws, {"A": 6, "B": 12, "C": 10, "D": 10, "E": 9, "F": 9, "G": 9, "H": 9,
                "I": 9, "J": 12, "K": 12, "L": 12, "M": 12, "N": 12, "O": 12})
    r = title(ws, "Custom tables passed as a range",
              "The fifth argument can be a range instead of an edition name. Two layouts, "
              "auto-detected from the header row.")

    # ---- matrix block ----
    subhead(ws, 4, "Layout A — matrix: one row per (sex, distance), ages across the header")
    header_row(ws, 5, ["Sex", "Event", "OpenStd"] + [str(a) for a in CUSTOM_AGES])
    m0 = 6
    for i, (sex, event, std) in enumerate(CUSTOM_ROWS):
        row = m0 + i
        ws[f"A{row}"].value = sex
        ws[f"A{row}"].font, ws[f"A{row}"].alignment = F_BODY, CENTER
        ws[f"B{row}"].value = event
        ws[f"B{row}"].font, ws[f"B{row}"].alignment = F_MONO, LEFT
        c = ws[f"C{row}"]
        c.value, c.number_format = serial(std), TIME_FMT
        for j, f in enumerate(custom_factors(sex, event)):
            c = ws.cell(row=row, column=4 + j, value=f)
            c.number_format = FAC_FMT
            c.alignment = CENTER
        for col in range(1, 9):
            cell = ws.cell(row=row, column=col)
            cell.border, cell.fill = BOX, FILL_IN
            if cell.font is None or cell.font.size is None:
                cell.font = F_BODY
    m1 = m0 + len(CUSTOM_ROWS) - 1
    rng = f"$A${m0 - 1}:$H${m1}"
    note(ws, f"A{m1 + 1}",
         f"These are the published 2025 factors at five ages, pasted into a table you own. "
         f"OpenStd is a real time value. The add-in reads the range {rng} — header row included.")

    # ---- queries against it ----
    r = m1 + 3
    subhead(ws, r, "Grading against that range")
    header_row(ws, r + 1, ["Sex", "Event", "Age", "Time", "live %", "expected %", "check",
                           "built-in 2025 %", "difference (pp)", "note"])
    q0 = r + 2
    queries = [
        ("M", "10kmRoad", 45, "40:00", "Age 45 is one of the supplied ages, so this must equal "
                                       "the built-in 2025 answer exactly."),
        ("M", "10kmRoad", 52, "40:00", "Age 52 is interpolated between the 50 and 55 factors — "
                                       "the add-in fills sparse ages linearly."),
        ("F", "Half.Mar", 61, "1:55:00", "Any distance row and any sex: rows are independent."),
        ("M", "Marathon", 70, "3:45:00", "Age 70 is above the last supplied age (65), so the "
                                         "65 factor is clamped — the table is not extrapolated."),
    ]
    for i, (sex, event, age, t, why) in enumerate(queries):
        row = q0 + i
        for col, value, fmt in (("A", sex, None), ("B", event, None), ("C", age, "0"),
                                ("D", serial(t), TIME_FMT)):
            c = ws[f"{col}{row}"]
            c.value, c.number_format, c.fill, c.border = value, fmt or "General", FILL_IN, BOX
            c.font = F_MONO if col == "B" else F_BODY
            c.alignment = CENTER if col != "B" else LEFT
        live(ws, f"E{row}", f"=AG.GRADE(A{row},C{row},B{row},D{row},{rng})", PCT_FMT)
        expected(ws, f"F{row}", round(custom_grade(sex, event, age, secs(t)), 4), PCT_FMT)
        c = ws[f"G{row}"]
        c.value = f'=IF(ABS(E{row}-F{row})<0.01,"OK","MISMATCH")'
        c.fill, c.border, c.alignment, c.font = FILL_CHECK, BOX, CENTER, F_BODY
        built_in = grade(sex, age, KM[event], secs(t)).percent
        expected(ws, f"H{row}", round(built_in, 4), PCT_FMT)
        c = ws[f"I{row}"]
        c.value = f"=E{row}-H{row}"
        c.number_format = "+0.00;-0.00;0.00"
        c.fill, c.border, c.alignment, c.font = FILL_EXP, BOX, CENTER, F_BODY
        c = ws[f"J{row}"]
        c.value = why
        c.font, c.alignment, c.border = F_BODY, LEFT_WRAP, BOX
        ws.row_dimensions[row].height = 32

    # ---- long block ----
    r = q0 + len(queries) + 2
    subhead(ws, r, "Layout B — long: one row per (sex, distance, age), for machine-made tables")
    header_row(ws, r + 1, ["Sex", "Event", "Age", "Factor", "OpenStd"])
    l0 = r + 2
    row = l0
    for sex, event, std in CUSTOM_ROWS:
        for age, f in zip(CUSTOM_AGES, custom_factors(sex, event)):
            ws[f"A{row}"].value = sex
            ws[f"B{row}"].value = event
            ws[f"C{row}"].value = age
            ws[f"C{row}"].number_format = "0"
            ws[f"D{row}"].value = f
            ws[f"D{row}"].number_format = FAC_FMT
            ws[f"E{row}"].value = serial(std)
            ws[f"E{row}"].number_format = TIME_FMT
            for col in range(1, 6):
                cell = ws.cell(row=row, column=col)
                cell.fill, cell.border = FILL_IN, BOX
                cell.font, cell.alignment = F_BODY, CENTER
            row += 1
    l1 = row - 1
    long_rng = f"$A${l0 - 1}:$E${l1}"

    r = l1 + 2
    header_row(ws, r, ["Sex", "Event", "Age", "Time", "live % (long)", "expected %", "check",
                       "same as matrix?", "note"])
    row = r + 1
    for sex, event, age, t in (("M", "10kmRoad", 50, "40:00"), ("F", "Marathon", 58, "3:30:00")):
        ws[f"A{row}"].value = sex
        ws[f"B{row}"].value = event
        ws[f"C{row}"].value = age
        ws[f"C{row}"].number_format = "0"
        ws[f"D{row}"].value = serial(t)
        ws[f"D{row}"].number_format = TIME_FMT
        for col in "ABCD":
            ws[f"{col}{row}"].fill, ws[f"{col}{row}"].border = FILL_IN, BOX
            ws[f"{col}{row}"].font, ws[f"{col}{row}"].alignment = F_BODY, CENTER
        live(ws, f"E{row}", f"=AG.GRADE(A{row},C{row},B{row},D{row},{long_rng})", PCT_FMT)
        expected(ws, f"F{row}", round(custom_grade(sex, event, age, secs(t)), 4), PCT_FMT)
        c = ws[f"G{row}"]
        c.value = f'=IF(ABS(E{row}-F{row})<0.01,"OK","MISMATCH")'
        c.fill, c.border, c.alignment, c.font = FILL_CHECK, BOX, CENTER, F_BODY
        c = ws[f"H{row}"]
        c.value = (f'=IF(ABS(E{row}-AG.GRADE(A{row},C{row},B{row},D{row},{rng}))<0.01,'
                   f'"OK","MISMATCH")')
        c.fill, c.border, c.alignment, c.font = FILL_CHECK, BOX, CENTER, F_BODY
        c = ws[f"I{row}"]
        c.value = "The long table must give the same answer as the matrix table."
        c.font, c.alignment = F_BODY, LEFT_WRAP
        row += 1

    r = row + 1
    note(ws, f"A{r}", "OpenStd may be left out entirely when the distance is one the built-in "
                      "tables cover: the add-in then uses its own open standard for that distance. "
                      "A sidecar CSV works the same way — drop it beside the .xll (examples/tables/"
                      "bellville-vets.csv) and pass its name instead of a range.")
    ws.page_setup.orientation = "landscape"
    ws.page_setup.fitToWidth = 1


# ---------------------------------------------------------------------------
# sheet 6 — times and formats
# ---------------------------------------------------------------------------
def sheet_times(wb: Workbook) -> None:
    ws = wb.create_sheet("6 Times & formats")
    widths(ws, {"A": 30, "B": 16, "C": 16, "D": 16, "E": 50})
    r = title(ws, "Times, seconds and Excel time values",
              "Everything inside the add-in is seconds. Excel shows a time as a day fraction. "
              "Both directions are on this sheet.")

    header_row(ws, 4, ["Athlete / call", "stored as", "shown as", "seconds", "note"])
    rows = [
        ("Time cell", serial("39:40"), "0:39:40", 2380,
         "A time value: format [h]:mm:ss so hours do not wrap at 24. Multiply by 86400 for seconds."),
        ("same as seconds", 2380, "2380", 2380,
         "A plain number of 1 or more — accepted directly, no formatting needed."),
    ]
    for i, (label, stored, shown, seconds, why) in enumerate(rows):
        row = 5 + i
        ws[f"A{row}"].value = label
        ws[f"A{row}"].font, ws[f"A{row}"].border, ws[f"A{row}"].alignment = F_BODY, BOX, LEFT
        c = ws[f"B{row}"]
        c.value = stored
        c.number_format = TIME_FMT if stored < 1 else "0"
        c.fill, c.border, c.alignment, c.font = FILL_IN, BOX, CENTER, F_BODY
        c = ws[f"C{row}"]
        c.value = f"=B{row}"
        c.number_format = TIME_FMT
        c.fill, c.border, c.alignment, c.font = FILL_LIVE, BOX, CENTER, F_MONO
        c = ws[f"D{row}"]
        c.value = f"=B{row}*86400"
        c.number_format = "0.0"
        c.fill, c.border, c.alignment, c.font = FILL_LIVE, BOX, CENTER, F_MONO
        ws[f"E{row}"].value = why
        ws[f"E{row}"].font, ws[f"E{row}"].alignment = F_BODY, LEFT_WRAP
        ws.row_dimensions[row].height = 30

    r = 9
    subhead(ws, r, "Round-tripping: grade a run, then ask what time would score that grade")
    header_row(ws, r + 1, ["Step", "live", "expected", "check", "note"])
    row = r + 2
    g = grade("M", 40, 10.0, 2400)
    steps = [
        ("1. percent for 40:00",
         '=AG.GRADE("M",40,10,"40:00")', round(g.percent, 4), PCT_FMT,
         "The grade of the actual run."),
        ("2. time that scores it",
         '=AG.TIMEFORPCT("M",40,10,"&percent&")', 2400 / 86400.0, TIME_FMT,
         "Feeding the percentage back in must return the original time — the inverse is exact."),
        ("3. graded time for 40:00",
         '=AG.GRADEDTIME("M",40,10,"40:00")', g.age_graded_s / 86400.0, TIME_FMT,
         "The same run in open-class terms: 38:32.6."),
        ("4. factor behind it",
         '=AG.FACTOR("M",40,10)', round(g.factor, 4), FAC_FMT,
         "38:32.6 / 40:00 = 0.9636 — the factor is the ratio of the two."),
    ]
    for i, (label, formula, exp, fmt, why) in enumerate(steps):
        row = r + 2 + i
        ws[f"A{row}"].value = label
        ws[f"A{row}"].font, ws[f"A{row}"].border, ws[f"A{row}"].alignment = F_BODY, BOX, LEFT
        if "&percent&" in formula:
            formula = formula.replace('"&percent&"', f"B{r + 2}")
        live(ws, f"B{row}", formula, fmt)
        expected(ws, f"C{row}", round(exp, 6), fmt)
        c = ws[f"D{row}"]
        scale = "*86400" if fmt == TIME_FMT else ""
        tol = "1" if fmt == TIME_FMT else "0.01"
        c.value = f'=IF(ABS(B{row}-C{row}){scale}<{tol},"OK","MISMATCH")'
        c.fill, c.border, c.alignment, c.font = FILL_CHECK, BOX, CENTER, F_BODY
        ws[f"E{row}"].value = why
        ws[f"E{row}"].font, ws[f"E{row}"].alignment = F_BODY, LEFT_WRAP

    r = row + 2
    note(ws, f"A{r}", "Format cells as [h]:mm:ss, not h:mm:ss: with the square brackets Excel shows "
                      "2:10:35 for a marathon instead of 10:35. A grade of 0:38:33 is a duration, "
                      "not a time of day.")
    ws.page_setup.orientation = "landscape"
    ws.page_setup.fitToWidth = 1


# ---------------------------------------------------------------------------
# sheet 7 — reference
# ---------------------------------------------------------------------------
def sheet_reference(wb: Workbook) -> None:
    ws = wb.create_sheet("7 Reference")
    widths(ws, {"A": 14, "B": 10, "C": 10, "D": 52})
    r = title(ws, "Reference", "The distances the tables cover, and the rules every call follows.")

    subhead(ws, 4, "The 22 published distances")
    header_row(ws, 5, ["Event name", "km", "miles", "Notes"])
    t = tbl("M")
    for i, ev in enumerate(t.events):
        row = 6 + i
        ws[f"A{row}"].value = ev.name
        ws[f"A{row}"].font, ws[f"A{row}"].alignment = F_MONO, LEFT
        c = ws[f"B{row}"]
        c.value = ev.distance_km
        c.number_format = "0.0####"
        c.alignment = CENTER
        c = ws[f"C{row}"]
        c.value = f"=B{row}/1.609344"
        c.number_format = "0.000"
        c.alignment = CENTER
        c.fill = FILL_LIVE
        for col in "ABCD":
            ws[f"{col}{row}"].border = BOX
            if col != "A":
                ws[f"{col}{row}"].font = F_BODY
        ev_names = {"1MileRoad": "Any distance may also be given in km and is interpolated "
                                 "between the two nearest rows.",
                    "5kmRoad": "The most-used row in club racing.",
                    "Half.Mar": "21.0975 km exactly; \"half\", \"hm\" and \"half marathon\" all work.",
                    "Marathon": "42.195 km; \"mar\" and \"marathon\" work.",
                    "200kmRoad": "The top of the published range — above this the call fails."}
        if ev.name in ev_names:
            ws[f"D{row}"].value = ev_names[ev.name]
            ws[f"D{row}"].font, ws[f"D{row}"].alignment = F_BODY, LEFT_WRAP

    r = 6 + len(t.events) + 1
    subhead(ws, r, "Argument rules")
    rules = [
        ("sex", 'M, F, Male, Female, Men, Women, 1, 0. Not "both" or "mixed" — those are refused '
                'rather than guessed at.'),
        ("age", "Years on race day, 1-120. Below 5 clamps to 5, above 99 clamps to 100; "
                "fractional ages interpolate."),
        ("distance", "km as a number (10, 12.5) or an event name (\"10k\", \"10kmRoad\", \"half\", "
                     "\"5 Mile\"). Out of range 1.609344-200 km fails."),
        ("time", "Excel time value, text (\"40:00\"), or seconds (2400). Numbers below 1 are time "
                 "serials; 1 or more are seconds."),
        ("percent", "The grade you want, e.g. 75 for 75%."),
        ("table", "Optional: an edition name (2025, 2020, 2015, 2010, latest), a <name>.csv "
                  "sidecar, or a range holding a custom table."),
        ("vectors", "Scalars broadcast. All vectors must be the same length; a mismatch fails the "
                    "whole call and AG.LASTERROR() says which arguments differ."),
        ("blank cells", "A blank time leaves that row empty; a blank age or distance fails that row."),
    ]
    header_row(ws, r + 1, ["Argument", "Accepts", "", ""])
    for i, (arg, rule) in enumerate(rules):
        row = r + 2 + i
        ws[f"A{row}"].value = arg
        ws[f"A{row}"].font, ws[f"A{row}"].alignment = F_MONO, LEFT
        ws[f"A{row}"].border = BOX
        c = ws.cell(row=row, column=2, value=rule)
        ws.merge_cells(start_row=row, start_column=2, end_row=row, end_column=4)
        c.font, c.alignment, c.border = F_BODY, LEFT_WRAP, BOX
        ws.row_dimensions[row].height = 30

    r = r + len(rules) + 3
    subhead(ws, r, "Errors")
    header_row(ws, r + 1, ["You see", "", "", "What it means"])
    errs = [
        ("#NAME?", "The add-in is not loaded, or the workbook was opened on a machine without it."),
        ("#NUM!", "A lookup failed. Put =AG.LASTERROR() in the next cell: it names the row, the "
                  "argument and the reason."),
        ("#N/A at the end of a block", "An array formula's output range is larger than the result. "
                                       "Resize the range, or retype the formula in one cell in "
                                       "Excel 365 and let it spill."),
        ("blank cell", "The row's time was blank. Not an error — partial sheets are allowed."),
        ("0", "Nothing was computed for that row: check that the row is inside the array formula's "
              "range."),
    ]
    for i, (symptom, why) in enumerate(errs):
        row = r + 2 + i
        ws[f"A{row}"].value = symptom
        ws[f"A{row}"].font, ws[f"A{row}"].alignment = F_MONO, LEFT
        ws[f"A{row}"].border = BOX
        c = ws.cell(row=row, column=2, value=why)
        ws.merge_cells(start_row=row, start_column=2, end_row=row, end_column=4)
        c.font, c.alignment, c.border = F_BODY, LEFT_WRAP, BOX
        ws.row_dimensions[row].height = 30

    r = r + len(errs) + 3
    note(ws, f"A{r}", "Tables: Alan Jones, with single-age bests by Tom Bernhard; approved by the "
                      "USATF MLDR Council 2025-01-10. Calculator: Howard Grubb. Cite the tables "
                      "and the edition year when publishing graded results.")
    ws.page_setup.orientation = "landscape"
    ws.page_setup.fitToWidth = 1


# ---------------------------------------------------------------------------
def build(path: Path) -> None:
    wb = Workbook()
    sheet_start(wb)
    sheet_squad(wb)
    sheet_functions(wb)
    sheet_editions(wb)
    sheet_vectors(wb)
    sheet_custom(wb)
    sheet_times(wb)
    sheet_reference(wb)
    for ws in wb.worksheets:
        ws.sheet_view.zoomScale = 90
        # print setup: one page wide, as many pages tall as it needs. Without
        # fitToPage the fitToWidth setting is ignored and the wide description
        # columns land off the page edge.
        ws.sheet_properties.pageSetUpPr = PageSetupProperties(fitToPage=True)
        ws.page_setup.orientation = "landscape"
        ws.page_setup.paperSize = ws.PAPERSIZE_A4
        ws.page_setup.fitToWidth = 1
        ws.page_setup.fitToHeight = 0
        ws.print_options.horizontalCentered = True
    wb.save(path)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="fail if the committed workbook is not what this script builds")
    a = ap.parse_args()

    tmp = OUT.with_suffix(".tmp.xlsx")
    build(tmp)

    if a.check:
        import zipfile

        # docProps/core.xml carries the build timestamp, so it differs on every
        # run and is not part of what "up to date" means here.
        skipped = {"docProps/core.xml"}

        def dump(p):
            with zipfile.ZipFile(p) as z:
                return {n: z.read(n) for n in sorted(z.namelist()) if n not in skipped}
        stale = dump(tmp) != dump(OUT) if OUT.exists() else True
        tmp.unlink(missing_ok=True)
        if stale:
            print(f"stale: {OUT} — rerun without --check", file=sys.stderr)
            return 1
        print(f"up to date: {OUT.name}")
        return 0

    tmp.replace(OUT)
    print(f"wrote {OUT} ({OUT.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
