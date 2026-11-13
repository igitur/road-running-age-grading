#!/usr/bin/env python3
"""build_sample_workbook.py — generate the sample workbook for road_running_age_grading.xll.

Every expected value in the workbook is computed here from the verified Python
implementation in brrag/ (itself checked against the published calculator by
tools/verify.py), so no number is hand-typed and the workbook can be rebuilt
after any change to the tables:

    python3 xll/examples/build_sample_workbook.py
    python3 xll/examples/build_sample_workbook.py --check   # fail if stale

The formulas are live: each demo cell calls RRAG.* as a real XLL formula. Without
the add-in loaded Excel shows #NAME?; that is expected and is explained on the
first sheet.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from brrag.cli import parse_distance as label_km        # noqa: E402
from brrag.core import load_tables                      # noqa: E402
from openpyxl import Workbook, load_workbook              # noqa: E402
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side  # noqa: E402
from openpyxl.worksheet.properties import PageSetupProperties  # noqa: E402
from openpyxl.utils import get_column_letter              # noqa: E402
from openpyxl.utils.cell import range_boundaries          # noqa: E402
from openpyxl.worksheet.formula import ArrayFormula       # noqa: E402

OUT = Path(__file__).resolve().parent / "age-grading-sample.xlsx"

# ---------------------------------------------------------------------------
# palette and cell styles
# ---------------------------------------------------------------------------
NAVY = "FF1F3864"
PALE_NAVY = "FFD9E1F2"
LIVE = "FFDCE6F1"        # a cell holding a live RRAG.* formula
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
PCT_FMT = "00.00%"      # the value is a fraction: 0.6849 shows as 68.49%
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
    ("M", "10 k", "26:24"),
    ("F", "10 k", "28:46"),
    ("M", "half marathon", "57:31"),
    ("F", "half marathon", "1:02:52"),
    ("M", "marathon", "2:00:35"),
    ("F", "marathon", "2:09:56"),
]


def custom_factors(sex: str, km: float) -> list[float]:
    """The published factors behind a row of the custom table.

    Looked up by distance, not by name: the workbook writes the table's Distance
    cells in the add-in's grammar ("10 k"), while the Python data API knows the
    published row labels ("10kmRoad"). Distance is the thing they share.
    """
    t = tbl(sex)
    ev = next(e for e in t.events if abs(e.distance_km - km) < 1e-9)
    return [ev.factors[t.ages.index(a)] for a in CUSTOM_AGES]



def custom_grade(sex: str, km: float, age: float, time_s: float) -> float:
    """Grade with the sparse custom table, mimicking ag_core.cpp exactly.

    Returns a fraction (0.7127), matching RRAG.GRADE and Grade.percent.
    """
    ages = CUSTOM_AGES
    v = custom_factors(sex, km)
    f = v[0] if age <= ages[0] else v[-1]
    if ages[0] < age < ages[-1]:
        for i in range(1, len(ages)):
            if age < ages[i]:
                p = (age - ages[i - 1]) / (ages[i] - ages[i - 1])
                f = v[i - 1] * (1 - p) + v[i] * p
                break
    std_clock = next(r[2] for r in CUSTOM_ROWS
                     if r[0] == sex and abs(label_km(r[1]) - km) < 1e-9)
    return (secs(std_clock) / f) / time_s        # a fraction: 0.7127


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


# (sheet, anchor, area, shape). A function that returns a column needs a column
# of room: a horizontal reservation for a vertical result is #SPILL! in Excel,
# because the first cell below the anchor is already occupied.
# every live RRAG.* formula, and every reserved spill area
_LIVE: set[tuple[str, str]] = set()
_SPILLS: list[tuple[str, str, str, tuple[int, int] | None]] = []


def live(ws, ref: str, formula: str, fmt: str | None = None,
         ref_range: str | None = None, shape: tuple[int, int] | None = None):
    """A live RRAG.* formula.

    Written as a plain formula, never a legacy Ctrl+Shift+Enter array formula:
    Excel's dynamic arrays spill the result on their own, so `ref_range` only
    says how much area to pre-format. Nothing is written into the cells the
    spill will cover — a spilled value lands on an empty cell.

    `shape` is (rows, columns) of the result, and validate() checks the reserved
    area against it. Getting that wrong is invisible in the generator and fatal
    in Excel.
    """
    # A dynamic array formula is stored as a one-cell array formula (ref = the
    # anchor itself) carrying the XLDAPR cell metadata added in postprocess().
    # Excel shows the same tag without that metadata as a legacy Ctrl+Shift+
    # Enter formula (curly braces, no spilling) and rewrites a bare formula to
    # "=@RRAG.GRADE(...)" - implicit intersection - which spills nothing.
    ws[ref] = ArrayFormula(ref=ref, text=formula)
    _LIVE.add((ws.title, ref))
    if ref_range:
        _SPILLS.append((ws.title, ref, ref_range, shape))
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


def show_call(ws, ref: str, text: str) -> None:
    """Write a formula as text so the reader can see what was called.

    Assigning a string that starts with "=" makes openpyxl write a formula, so a
    label like =RRAG.FACTOR("M",B6:B9,10) would actually run - and with the add-in
    loaded it would spill over the rows below it.

    Storing it as a string is not enough on its own: Excel and LibreOffice
    re-interpret a *string* cell whose text starts with "=" as a formula when they
    open the file. The marker that stops that is the quote prefix - the same flag
    Excel sets when you type a leading apostrophe, which is why the apostrophe
    does not appear in the cell but does in the formula bar.
    """
    c = ws[ref]
    c.value = text
    c.data_type = "s"
    c.quotePrefix = True
    c.font, c.border, c.alignment = F_MONO, BOX, LEFT


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
              "for road_running_age_grading.xll  ·  USATF MLDR 2025 road tables  ·  "
              "every value below is regenerated by build_sample_workbook.py")

    blocks = [
        ("Before you start", [
            "Install the add-in: File > Options > Add-ins > Manage: Excel Add-ins > Go > Browse… "
            "and pick road_running_age_grading.xll. If the file came from another machine, right-click it "
            "> Properties > Unblock first.",
            "If every RRAG.* cell shows #NAME?, the add-in is not loaded. Nothing else on that sheet "
            "will be correct until it is.",
            "If a cell shows #NUM!, put =RRAG.LASTERROR() in the next cell: it explains the failure "
            "in words (which row, which argument, why).",
        ]),
        ("How to read the sheets", [
            "Pale blue cells are live RRAG.* formulas — they are the point of the exercise.",
            "Grey cells are the expected answer, computed by the Python implementation in this "
            "repository (verified against the published calculator: tools/verify.py).",
            "Green cells say OK or MISMATCH. A MISMATCH is a real disagreement between the add-in "
            "and the reference implementation — send it back as a bug.",
            "Cream cells are inputs. Change them and watch the blue cells follow.",
        ]),
        ("About the array formulas", [
            "The multi-cell demos are Excel 365 dynamic array formulas: one formula in the top-left "
            "cell that spills down or across. No Ctrl+Shift+Enter, no curly braces.",
            "All 49 live RRAG.* cells are stored the way Excel itself stores a dynamic array: a "
            "one-cell array formula carrying dynamic-array metadata (xl/metadata.xml). Without "
            "that mark Excel reads such a cell as a legacy Ctrl+Shift+Enter formula and shows it "
            "as {=RRAG.GRADE(...)}; with it there are no braces and multi-value results spill.",
            "A vector in gives a vector out, so leave room: RRAG.FACTOR on a column of ages fills "
            "a column, and RRAG.TABLES always returns one edition per row. A spill that runs into a "
            "used cell is #SPILL! — nothing is transposed automatically.",
            "Dynamic arrays need Excel 365 or Excel 2021. In Excel 2019 and older the spill simply "
            "will not happen and you will see one value; sheet 2, One call, shows every function "
            "returning a single value if you need that.",
        ]),
        ("About calculation mode", [
            "The workbook is saved as Automatic and asks Excel for a full recalculation on load "
            "(calcPr calcMode=\"auto\" fullCalcOnLoad=\"1\" forceFullCalc=\"1\"), so the values "
            "are right the moment it opens.",
            "If Excel still shows Manual in Formulas > Calculation Options, that is the Excel "
            "session rather than this file: Excel applies the calculation mode of the FIRST "
            "workbook you open to every workbook opened after it, whatever each file says. Close "
            "all workbooks and open this one, or set File > Options > Formulas > Workbook "
            "Calculation to Automatic.",
            "The forced recalculation on load means the numbers are correct even in a Manual "
            "session; what stops working is recalculation after you type a new input.",
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
        ("Functions", "All twelve functions: arguments, what each returns, the shape it returns it "
                      "in, and which sheet shows it working. Read this second."),
        ("1 Squad", "Grading a whole squad: one formula per column, and RRAG.BLOCK spilling five "
                    "columns at once. Club summary formulas on top of the results."),
        ("2 One call", "Every function with scalar arguments: RRAG.GRADE, RRAG.GRADEDTIME, RRAG.FACTOR, "
                       "RRAG.STANDARD, RRAG.TIMEFORPCT, plus the diagnostics RRAG.TABLES, RRAG.TABLEINFO, "
                       "RRAG.CACHEINFO, RRAG.CACHECLEAR, RRAG.LASTERROR, RRAG.VERSION."),
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
              "once and spilling down. Columns M-Q are a single RRAG.BLOCK call. Only column G is "
              "a fixed expected value; the rest are live.")

    header_row(ws, 4, ["Athlete", "Sex", "Age", "Dist km", "Time",
                       "RRAG.GRADE %", "expected %", "check",
                       "RRAG.GRADEDTIME", "RRAG.FACTOR", "RRAG.STANDARD"], start_col=1)
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
    live(ws, f"F{first}", f"=RRAG.GRADE($B${first}:$B${last},$C${first}:$C${last},"
                          f"$D${first}:$D${last},$E${first}:$E${last})",
         PCT_FMT, ref_range=f"F{first}:F{last}", shape=(last - first + 1, 1))
    live(ws, f"I{first}", f"=RRAG.GRADEDTIME($B${first}:$B${last},$C${first}:$C${last},"
                          f"$D${first}:$D${last},$E${first}:$E${last})",
         TIME_FMT, ref_range=f"I{first}:I{last}", shape=(last - first + 1, 1))
    live(ws, f"J{first}", f"=RRAG.FACTOR($B${first}:$B${last},$C${first}:$C${last},"
                          f"$D${first}:$D${last})",
         FAC_FMT, ref_range=f"J{first}:J{last}", shape=(last - first + 1, 1))
    live(ws, f"K{first}", f"=RRAG.STANDARD($B${first}:$B${last},$C${first}:$C${last},"
                          f"$D${first}:$D${last})",
         TIME_FMT, ref_range=f"K{first}:K{last}", shape=(last - first + 1, 1))
    # one call, five columns
    live(ws, f"M{first}", f"=RRAG.BLOCK($B${first}:$B${last},$C${first}:$C${last},"
                          f"$D${first}:$D${last},$E${first}:$E${last})",
         None, ref_range=f"M{first}:Q{last}", shape=(last - first + 1, 5))
    for i in range(len(SQUAD)):
        row = first + i
        ws[f"M{row}"].number_format = FAC_FMT
        for col in "NOP":
            ws[f"{col}{row}"].number_format = TIME_FMT
        ws[f"Q{row}"].number_format = PCT_FMT
        c = ws[f"H{row}"]
        c.value = f'=IF(ABS(F{row}-G{row})<0.0001,"OK","MISMATCH")'
        c.fill, c.border, c.alignment, c.font = FILL_CHECK, BOX, CENTER, F_BODY

    # do the two entry styles agree with each other?
    row = last + 1
    ws.cell(row=row, column=1,
            value="RRAG.BLOCK percent agrees with RRAG.GRADE column").font = F_H2
    c = ws[f"H{row}"]
    c.value = (f'=IF(SUMPRODUCT(--(ABS(Q{first}:Q{last}-F{first}:F{last})>0.0001))=0,'
               f'"OK","MISMATCH")')
    c.fill, c.border, c.alignment, c.font = FILL_CHECK, BOX, CENTER, F_BODY

    row += 1
    ws.cell(row=row, column=1,
            value="RRAG.BLOCK graded time agrees with RRAG.GRADEDTIME").font = F_H2
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
def sheet_one_call(wb: Workbook) -> None:
    ws = wb.create_sheet("2 One call")
    widths(ws, {"A": 20, "B": 34, "C": 14, "D": 13, "E": 11, "F": 14, "G": 11,
                "H": 44, "I": 14, "J": 14, "K": 14, "L": 14, "M": 14})
    r = title(ws, "Every function, scalar arguments",
              "One row per call. Column C is live, D is the expected answer, E is the verdict.")

    def note_block(row: int, text: str, first_col: int = 6, last_col: int = 10,
                   wrap: int = 78) -> None:
        """Prose in a merged span of its own. Never merge over an array
        formula's output range: Excel reports that as corrupt and repairs the
        file ("Removed Records: Cell information")."""
        c = ws.cell(row=row, column=first_col, value=text)
        c.font, c.alignment = F_BODY, LEFT_WRAP
        ws.merge_cells(start_row=row, start_column=first_col, end_row=row,
                       end_column=last_col)
        ws.row_dimensions[row].height = 15 * max(1, len(text) // wrap + 1)

    subhead(ws, 4, "The five grading functions")
    header_row(ws, 5, ["Function", "Arguments", "live", "expected", "check"])
    c = ws.cell(row=5, column=6, value="What it means")
    c.font, c.fill, c.alignment, c.border = F_HDR, FILL_HDR, CENTER, BOX
    ws.merge_cells(start_row=5, start_column=6, end_row=5, end_column=10)

    rows = [
        ("RRAG.GRADE", 'M, 40, 10 km, 40:00', '=RRAG.GRADE("M",40,10,0.0277777777777778)',
         grade("M", 40, 10.0, 2400).percent, PCT_FMT,
         "The age grade in percent. 100 = the world-standard mark for that exact sex and age."),
        ("RRAG.GRADE", 'F, 56, 10 km, 50:00', '=RRAG.GRADE("F",56,10,"50:00")',
         grade("F", 56, 10.0, 3000).percent, PCT_FMT,
         "A time written as text is read as mm:ss - no need to type 0:50:00."),
        ("RRAG.GRADE", 'M, 75, marathon, 4:30:00', '=RRAG.GRADE("M",75,42.195,"4:30:00")',
         grade("M", 75, 42.195, 16200).percent, PCT_FMT,
         "Masters score well above 50%: the tables assume a steep decline after 35."),
        ("RRAG.GRADE", 'F, 26, 5 km, 18:30', '=RRAG.GRADE("F",26,5,"18:30")',
         grade("F", 26, 5.0, 1110).percent, PCT_FMT,
         "Above 100% is a real answer and is never clamped - a whole age band over 100 means "
         "the table is soft there."),
        ("RRAG.GRADEDTIME", 'M, 40, 10 km, 40:00', '=RRAG.GRADEDTIME("M",40,10,"40:00")',
         grade("M", 40, 10.0, 2400).age_graded_s / 86400.0, TIME_FMT,
         "The same run converted to open-class age: time x factor."),
        ("RRAG.FACTOR", 'F, 56, 10 km', '=RRAG.FACTOR("F",56,10)',
         grade("F", 56, 10.0, 3000).factor, FAC_FMT,
         "The multiplier from the table. Bigger age = smaller factor = more generous."),
        ("RRAG.STANDARD", 'M, 40, 10 km', '=RRAG.STANDARD("M",40,10)',
         tbl("M").event("10kmRoad").standard_s / 86400.0, TIME_FMT,
         "The open standard for the distance (26:24 for a male 10 km). Age is ignored: it is "
         "accepted only so the signature matches its siblings."),
        ("RRAG.STANDARD", 'F, 40, half marathon', '=RRAG.STANDARD("F",40,21.0975)',
         tbl("F").event("Half.Mar").standard_s / 86400.0, TIME_FMT,
         'Distance can be given in km or as a name; 21.0975 and "half" are the same thing.'),
        ("RRAG.TIMEFORPCT", 'M, 40, 10 km, 0.6849', '=RRAG.TIMEFORPCT("M",40,10,0.6849)',
         tbl("M").time_for_percent("M", 40, 0.6849, dist_km=10.0) / 86400.0, TIME_FMT,
         "The inverse: the time that would score that percentage. This is the calculator's "
         "Result button."),
        ("RRAG.TIMEFORPCT", 'F, 52, half, 0.80', '=RRAG.TIMEFORPCT("F",52,21.0975,0.8)',
         tbl("F").time_for_percent("F", 52, 0.8, dist_km=21.0975) / 86400.0, TIME_FMT,
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
    # Every list-returning function here is wrapped in TRANSPOSE so it spills
    # DOWN a column: a row-per-function table cannot hold a horizontal result
    # without running into the next function's row. RRAG.TABLES is already a
    # column; TABLEINFO (1x4) and CACHEINFO (1x6) come back as rows.
    r = 6 + len(rows) + 2
    subhead(ws, r, "Diagnostics: what is loaded, and what the last call complained about")
    header_row(ws, r + 1, ["Function", "Arguments", "live (a column)", "expected", "check",
                           "What it means"])

    def column(ws, row: int, fn: str, args: str, formula: str, expect: list,
               why: str, *, check: bool = True) -> int:
        """One function per block, returning a column of len(expect) values."""
        n = len(expect) if expect else 6
        for col, value in (("A", fn), ("B", args)):
            c = ws[f"{col}{row}"]
            c.value, c.font, c.border, c.alignment = value, F_MONO, BOX, LEFT
        live(ws, f"C{row}", formula, None, ref_range=f"C{row}:C{row + n - 1}", shape=(n, 1))
        for j, v in enumerate(expect or []):
            expected(ws, f"D{row + j}", v, "0")
        if expect and check:
            c = ws[f"E{row}"]
            c.value = (f'=IF(COUNTA(C{row}:C{row + n - 1})=0,"",IFERROR(IF(SUMPRODUCT('
                       f'--(ABS(C{row}:C{row + n - 1}-D{row}:D{row + n - 1})>0.0001))=0,'
                       f'"OK","MISMATCH"),""))')
            c.fill, c.border, c.alignment, c.font = FILL_CHECK, BOX, CENTER, F_BODY
        c = ws.cell(row=row, column=6, value=why)
        c.font, c.alignment = F_BODY, LEFT_WRAP
        ws.merge_cells(start_row=row, start_column=6, end_row=row, end_column=10)
        ws.row_dimensions[row].height = 44
        return row + max(n, 2) + 1

    row = r + 2
    row = column(ws, row, "RRAG.TABLES", "(none)", "=RRAG.TABLES()", [2025, 2020, 2015, 2010],
                 "The editions compiled into this build, newest first. Any of them can be the "
                 "fifth argument of a grading function. Already a column: one edition per row.")
    def tableinfo(year: int) -> list:
        """What RRAG.TABLEINFO reports, read from the data rather than typed.

        Deriving this matters: the editions do not have the same shape. 2025 has
        22 distances, 2020 has 21 (no 7 Mile), 2015 and 2010 have 20 - so a
        hand-written 22 makes the 2020 row cry MISMATCH against a correct 21.
        """
        t = tbl("M", year)
        return [year, len(t.events), len(t.ages), 2]

    row = column(ws, row, "RRAG.TABLEINFO", "(default table)", "=TRANSPOSE(RRAG.TABLEINFO())",
                 tableinfo(2025),
                 "Year, distances, ages, sexes. The function returns a 1x4 row, so it is wrapped "
                 "in TRANSPOSE to stand up as a column - the labels are in the reference sheet.")
    row = column(ws, row, "RRAG.TABLEINFO", "2020", "=TRANSPOSE(RRAG.TABLEINFO(2020))",
                 tableinfo(2020),
                 "The same for the 2020 edition - the tables that were in force then. Note the "
                 "distance count: the editions differ in shape, and 2020 has one fewer row "
                 "than 2025.")
    row = column(ws, row, "RRAG.CACHEINFO", "(none)", "=TRANSPOSE(RRAG.CACHEINFO())", None,
                 "Six counters: built-in editions, loaded CSVs, custom ranges held, cache hits, "
                 "misses, capacity. No expected values - they depend on what this workbook has "
                 "done. Recalculate and watch the hit count climb: a range table is parsed once, "
                 "not once per cell.", check=False)

    for fn, args, formula, exp_text, why, chk in (
        ("RRAG.LASTERROR", "(none)", "=RRAG.LASTERROR()",
         "text: 'no error', or the reason for the most recent failure",
         "The explanation for the last failed call - the first thing to reach for when a "
         "column fills with #NUM!. Its value depends on what failed last, so the check only "
         "asks that it is text; sheet 4 shows it next to a known failure.",
         '=IF(ISERR({c}),"",IF(ISTEXT({c}),"OK","MISMATCH"))'),
        ("RRAG.VERSION", "(none)", "=RRAG.VERSION()",
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
        c.value = chk.format(c=f"C{row}", r=row)
        c.fill, c.border, c.alignment, c.font = FILL_CHECK, BOX, CENTER, F_BODY
        note_block(row, why)
        row += 1

    # RRAG.CACHECLEAR shown but not live: a live one would empty the cache on
    # every recalculation and defeat the demo.
    for col, value in (("A", "RRAG.CACHECLEAR"), ("B", "(none)")):
        c = ws[f"{col}{row}"]
        c.value, c.font, c.border, c.alignment = value, F_MONO, BOX, LEFT
    c = ws[f"C{row}"]
    c.value = "RRAG.CACHECLEAR()"
    c.font, c.border, c.alignment = F_MONO, BOX, LEFT
    ws[f"D{row}"].value = "returns 1"
    ws[f"D{row}"].font, ws[f"D{row}"].alignment = F_NOTE, LEFT
    note_block(row, "Not live on purpose: it drops cached CSV and custom-range tables, so a live "
                    "copy would empty the cache on every recalculation. Type it when you need it "
                    "- after editing a table CSV. Ad hoc ranges are keyed by a hash of their "
                    "contents and can never go stale, so only CSVs need this.")
    row += 2

    # ---- calculation mode, as Excel itself reports it ----
    subhead(ws, row, "Calculation mode: what the file asks for, and what Excel is actually doing")
    row += 1
    header_row(ws, row, ["Check", "live", "What it means"])
    row += 1
    c = ws[f"B{row}"]
    c.value = '=INFO("RECALC")'          # native function, so a plain formula
    c.font, c.border = F_MONO, BOX
    c.fill, c.alignment = FILL_LIVE, LEFT
    c = ws[f"A{row}"]
    c.value, c.font, c.border, c.alignment = '=INFO("RECALC")', F_MONO, BOX, LEFT
    c.data_type, c.quotePrefix = "s", True
    c = ws.cell(row=row, column=3,
                value="Excel's own answer for this session. The workbook is saved with "
                      "calcPr calcMode=\"auto\" fullCalcOnLoad=\"1\" forceFullCalc=\"1\", so a "
                      "session that starts with this file reports Automatic. Excel gives every "
                      "workbook in a session the mode of the FIRST one opened and ignores what the "
                      "later files ask for, so Manual here means this session started manual - "
                      "Personal.xlsb, a startup template, or another workbook. Close all workbooks "
                      "and open this one, or set File > Options > Formulas > Workbook Calculation.")
    c.font, c.alignment = F_BODY, LEFT_WRAP
    ws.merge_cells(start_row=row, start_column=3, end_row=row, end_column=10)
    ws.row_dimensions[row].height = 88

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
        live(ws, f"C{row}", f'=RRAG.GRADE("F",45,21.0975,"1:45:00","{year}")', PCT_FMT)
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
    live(ws, f"B{r + 2}", '=RRAG.GRADE("F",45,21.0975,"1:45:00",2020)', PCT_FMT)
    expected(ws, f"C{r + 2}", round(grade("F", 45, 21.0975, 6300, 2020).percent, 4), PCT_FMT)
    c = ws[f"D{r + 2}"]
    c.value = f'=IF(ABS(B{r + 2}-C{r + 2})<0.0001,"OK","MISMATCH")'
    c.fill, c.border, c.alignment, c.font = FILL_CHECK, BOX, CENTER, F_BODY
    ws[f"A{r + 2}"].value = '2020 (a number)'
    ws[f"A{r + 2}"].font, ws[f"A{r + 2}"].border = F_MONO, BOX
    ws[f"E{r + 2}"].value = "A numeric table argument is coerced to its name."
    ws[f"E{r + 2}"].font, ws[f"E{r + 2}"].alignment = F_BODY, LEFT_WRAP

    live(ws, f"B{r + 3}", '=RRAG.GRADE("F",45,21.0975,"1:45:00","latest")', PCT_FMT)
    expected(ws, f"C{r + 3}", round(base, 4), PCT_FMT)
    c = ws[f"D{r + 3}"]
    c.value = f'=IF(ABS(B{r + 3}-C{r + 3})<0.0001,"OK","MISMATCH")'
    c.fill, c.border, c.alignment, c.font = FILL_CHECK, BOX, CENTER, F_BODY
    ws[f"A{r + 3}"].value = '"latest"'
    ws[f"A{r + 3}"].font, ws[f"A{r + 3}"].border = F_MONO, BOX
    ws[f"E{r + 3}"].value = "Newest compiled edition — what you want in a template that must not rot."
    ws[f"E{r + 3}"].font, ws[f"E{r + 3}"].alignment = F_BODY, LEFT_WRAP

    live(ws, f"B{r + 4}", '=RRAG.GRADE("F",45,21.0975,"1:45:00","1999")', PCT_FMT)
    ws[f"A{r + 4}"].value = '"1999"'
    ws[f"A{r + 4}"].font, ws[f"A{r + 4}"].border = F_MONO, BOX
    ws[f"C{r + 4}"].value = "#NUM!"
    ws[f"C{r + 4}"].font, ws[f"C{r + 4}"].alignment = F_BODY, CENTER
    ws[f"E{r + 4}"].value = "An edition that is not compiled in fails the whole call; RRAG.LASTERROR() names it."
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

    subhead(ws, 4, "Alignment: a vertical vector in, a vertical vector out")
    header_row(ws, 5, ["Call", "age in", "live factor", "expected", "check", "Note"])
    for i, age in enumerate([40, 50, 60, 70]):
        c = ws[f"B{6 + i}"]
        c.value, c.number_format = age, "0"
        c.fill, c.border, c.font, c.alignment = FILL_IN, BOX, F_BODY, CENTER
    show_call(ws, "A6", '=RRAG.FACTOR("M",B6:B9,10)')
    # four ages down -> four factors down. Reserving a row here instead would put
    # the spill on top of row 7 and Excel would refuse it with #SPILL!.
    live(ws, "C6", '=RRAG.FACTOR("M",B6:B9,10)', FAC_FMT, ref_range="C6:C9", shape=(4, 1))
    for i, age in enumerate([40, 50, 60, 70]):
        row = 6 + i
        expected(ws, f"D{row}", round(grade("M", age, 10.0, 2400).factor, 4), FAC_FMT)
        c = ws[f"E{row}"]
        # plain verdict: guard_verdicts() adds the blank/error shield itself
        c.value = f'=IF(ABS(C{row}-D{row})<0.0001,"OK","MISMATCH")' 
        c.fill, c.border, c.alignment, c.font = FILL_CHECK, BOX, CENTER, F_BODY
    c = ws["F6"]
    c.value = ("A scalar sex and a scalar distance broadcast against the column of ages in "
               "B6:B9. The result keeps the shape of the vector you pass, so it fills C6:C9.")
    c.font, c.alignment = F_BODY, LEFT_WRAP
    ws.merge_cells("F6:F9")

    # ---- the same call with the ages across ---------------------------------
    subhead(ws, 11, "The result follows the shape of the vector: the same call, sideways")
    show_call(ws, "A12", '=RRAG.FACTOR("M",B12:E12,10)')
    for j, age in enumerate([40, 50, 60, 70]):
        c = ws.cell(row=12, column=2 + j, value=age)
        c.number_format, c.fill, c.border = "0", FILL_IN, BOX
        c.font, c.alignment = F_BODY, CENTER
    live(ws, "B13", '=RRAG.FACTOR("M",B12:E12,10)', FAC_FMT, ref_range="B13:E13", shape=(1, 4))
    for j, age in enumerate([40, 50, 60, 70]):
        expected(ws, f"{get_column_letter(2 + j)}14",
                 round(grade("M", age, 10.0, 2400).factor, 4), FAC_FMT)
    c = ws["F13"]
    c.value = ('=IF(SUMPRODUCT(--(ABS(B13:E13-B14:E14)>0.0001))=0,"OK","MISMATCH")')
    c.fill, c.border, c.alignment, c.font = FILL_CHECK, BOX, CENTER, F_BODY
    note(ws, "A15", "Identical arguments with the ages across instead of down: four factors across. "
                    "Nothing is transposed for you and nothing needs to be — put =TRANSPOSE() round "
                    "the call only if you want the other orientation.")
    c = ws["A14"]
    c.value = "expected"
    c.font, c.alignment = F_NOTE, LEFT
    c = ws["A13"]
    c.value = "live"
    c.font, c.alignment = F_NOTE, LEFT

    # ---- length mismatch ----
    r = 17
    subhead(ws, r, "The one rule that is not Excel-like: vectors must be the same length")
    show_call(ws, f"A{r + 1}", '=RRAG.GRADE("M",{40;50;60},10,{2400;2500})')
    live(ws, f"B{r + 1}", '=RRAG.GRADE("M",{40;50;60},10,{2400;2500})', PCT_FMT)
    ws[f"C{r + 1}"].value = "#NUM!"
    ws[f"C{r + 1}"].font, ws[f"C{r + 1}"].alignment = F_BODY, CENTER
    live(ws, f"D{r + 1}", "=RRAG.LASTERROR()")
    ws[f"E{r + 1}"].value = ("Three ages and two times. The call fails as a whole and RRAG.LASTERROR() "
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
         f"=RRAG.GRADE($A${first}:$A${first + 4},$B${first}:$B${first + 4},"
         f"$C${first}:$C${first + 4},$D${first}:$D${first + 4})",
         PCT_FMT, ref_range=f"E{first}:E{first + 4}", shape=(5, 1))

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
        live(ws, f"B{row}", f'=RRAG.GRADE("M",A{row},10,"40:00")', PCT_FMT)
        expected(ws, f"C{row}", round(grade("M", age, 10.0, 2400).percent, 4), PCT_FMT)
        c = ws[f"D{row}"]
        c.value = f'=IF(ABS(B{row}-C{row})<0.0001,"OK","MISMATCH")'
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
        live(ws, f"C{row}", f'=RRAG.GRADE("M",40,10,B{row})', PCT_FMT)
        expected(ws, f"D{row}", round(grade("M", 40, 10.0, 2400).percent, 4), PCT_FMT)
        c = ws[f"E{row}"]
        c.value = f'=IF(ABS(C{row}-D{row})<0.0001,"OK","MISMATCH")'
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
    header_row(ws, 5, ["Sex", "Distance", "OpenStd"] + [str(a) for a in CUSTOM_AGES])
    m0 = 6
    for i, (sex, event, std) in enumerate(CUSTOM_ROWS):
        row = m0 + i
        ws[f"A{row}"].value = sex
        ws[f"A{row}"].font, ws[f"A{row}"].alignment = F_BODY, CENTER
        ws[f"B{row}"].value = event
        ws[f"B{row}"].font, ws[f"B{row}"].alignment = F_MONO, LEFT
        c = ws[f"C{row}"]
        c.value, c.number_format = serial(std), TIME_FMT
        for j, f in enumerate(custom_factors(sex, label_km(event))):
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
    header_row(ws, r + 1, ["Sex", "Distance", "Age", "Time", "live %", "expected %", "check",
                           "built-in 2025 %", "difference (pp)", "note"])
    q0 = r + 2
    queries = [
        ("M", "10 k", 45, "40:00", "Age 45 is one of the supplied ages, so this must equal "
                                   "the built-in 2025 answer exactly."),
        ("M", "10 km", 52, "40:00", "Spelled differently, and interpolated: 52 sits between the "
                                    "50 and 55 factors, which the add-in fills linearly."),
        ("F", "half marathon", 61, "1:55:00", "Any distance row and any sex: rows are independent."),
        ("M", "marathon", 70, "3:45:00", "Age 70 is above the last supplied age (65), so the "
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
        live(ws, f"E{row}", f"=RRAG.GRADE(A{row},C{row},B{row},D{row},{rng})", PCT_FMT)
        expected(ws, f"F{row}", round(custom_grade(sex, label_km(event), age, secs(t)), 4), PCT_FMT)
        c = ws[f"G{row}"]
        c.value = f'=IF(ABS(E{row}-F{row})<0.0001,"OK","MISMATCH")'
        c.fill, c.border, c.alignment, c.font = FILL_CHECK, BOX, CENTER, F_BODY
        built_in = grade(sex, age, label_km(event), secs(t)).percent
        expected(ws, f"H{row}", round(built_in, 4), PCT_FMT)
        c = ws[f"I{row}"]
        c.value = f"=(E{row}-H{row})*100"
        c.number_format = "+0.00;-0.00;0.00"
        c.fill, c.border, c.alignment, c.font = FILL_EXP, BOX, CENTER, F_BODY
        c = ws[f"J{row}"]
        c.value = why
        c.font, c.alignment, c.border = F_BODY, LEFT_WRAP, BOX
        ws.row_dimensions[row].height = 32

    # ---- long block ----
    r = q0 + len(queries) + 2
    subhead(ws, r, "Layout B — long: one row per (sex, distance, age), for machine-made tables")
    header_row(ws, r + 1, ["Sex", "Distance", "Age", "Factor", "OpenStd"])
    l0 = r + 2
    row = l0
    for sex, event, std in CUSTOM_ROWS:
        for age, f in zip(CUSTOM_AGES, custom_factors(sex, label_km(event))):
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
    header_row(ws, r, ["Sex", "Distance", "Age", "Time", "live % (long)", "expected %", "check",
                       "same as matrix?", "note"])
    row = r + 1
    for sex, event, age, t in (("M", "10 k", 50, "40:00"), ("F", "marathon", 58, "3:30:00")):
        ws[f"A{row}"].value = sex
        ws[f"B{row}"].value = event
        ws[f"C{row}"].value = age
        ws[f"C{row}"].number_format = "0"
        ws[f"D{row}"].value = serial(t)
        ws[f"D{row}"].number_format = TIME_FMT
        for col in "ABCD":
            ws[f"{col}{row}"].fill, ws[f"{col}{row}"].border = FILL_IN, BOX
            ws[f"{col}{row}"].font, ws[f"{col}{row}"].alignment = F_BODY, CENTER
        live(ws, f"E{row}", f"=RRAG.GRADE(A{row},C{row},B{row},D{row},{long_rng})", PCT_FMT)
        expected(ws, f"F{row}", round(custom_grade(sex, label_km(event), age, secs(t)), 4), PCT_FMT)
        c = ws[f"G{row}"]
        c.value = f'=IF(ABS(E{row}-F{row})<0.0001,"OK","MISMATCH")'
        c.fill, c.border, c.alignment, c.font = FILL_CHECK, BOX, CENTER, F_BODY
        c = ws[f"H{row}"]
        c.value = (f'=IF(ABS(E{row}-RRAG.GRADE(A{row},C{row},B{row},D{row},{rng}))<0.0001,'
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
    # Three rows, because there are two input kinds and one trap. The trap is the
    # row that used to be here mislabelled: a plain number wearing a time format
    # shows 57120:00:00 (Excel reads 2380 as DAYS) while the add-in still receives
    # the number 2380 and grades 2380 seconds.
    rows = [
        ("Time cell (a day fraction)", serial("39:40"), TIME_FMT, TIME_FMT, "*86400",
         "0.0275 of a day. Format [h]:mm:ss so hours do not wrap at 24, and multiply by 86400 "
         "to get the seconds the add-in works in."),
        ("Seconds as a plain number", 2380, "0", "0", "",
         "1 or more is taken as seconds. No time format, no x86400 - the number already is the "
         "answer, and the add-in reads it directly."),
        ("...the same number, time-formatted", 2380, "0", TIME_FMT, "",
         "Look: Excel shows 57120:00:00, because a bare number in a time format is a number of "
         "DAYS. Formatting changes what you see, not what is stored - the add-in still receives "
         "2380 and grades 2380 s. This is why the seconds column here is not x 86400."),
    ]
    for i, (label, stored, in_fmt, show_fmt, scale, why) in enumerate(rows):
        row = 5 + i
        ws[f"A{row}"].value = label
        ws[f"A{row}"].font, ws[f"A{row}"].border, ws[f"A{row}"].alignment = F_BODY, BOX, LEFT
        c = ws[f"B{row}"]
        c.value = stored
        c.number_format = in_fmt
        c.fill, c.border, c.alignment, c.font = FILL_IN, BOX, CENTER, F_BODY
        c = ws[f"C{row}"]
        c.value = f"=B{row}"
        c.number_format = show_fmt
        c.fill, c.border, c.alignment, c.font = FILL_LIVE, BOX, CENTER, F_MONO
        c = ws[f"D{row}"]
        c.value = f"=B{row}{scale}"
        c.number_format = "0.0"
        c.fill, c.border, c.alignment, c.font = FILL_LIVE, BOX, CENTER, F_MONO
        ws[f"E{row}"].value = why
        ws[f"E{row}"].font, ws[f"E{row}"].alignment = F_BODY, LEFT_WRAP
        ws.row_dimensions[row].height = 58 if i == 2 else 30

    # what the add-in actually makes of each of those three cells
    subhead(ws, 9, "What the add-in does with each of them")
    header_row(ws, 10, ["Call", "live graded time", "expected", "check", "note"])
    for i, why in enumerate([
        "A day fraction below 1: read as an Excel time value.",
        "A number of 1 or more: read as seconds. Same 2380 s as the row above.",
        "A bare number in a time format: still the number 2380, so still 2380 s. The display is a "
        "red herring, not a different input.",
    ]):
        row = 11 + i
        src = 5 + i
        show_call(ws, f"A{row}", f'=RRAG.GRADE("M",40,10,B{src},"40:00")')
        live(ws, f"B{row}", f'=RRAG.GRADE("M",40,10,B{src},"40:00")', PCT_FMT)
        expected(ws, f"C{row}", round(grade("M", 40, 10.0, 2380).percent, 4), PCT_FMT)
        c = ws[f"D{row}"]
        c.value = f'=IF(ABS(B{row}-C{row})<0.0001,"OK","MISMATCH")'
        c.fill, c.border, c.alignment, c.font = FILL_CHECK, BOX, CENTER, F_BODY
        ws[f"E{row}"].value = why
        ws[f"E{row}"].font, ws[f"E{row}"].alignment = F_BODY, LEFT_WRAP
        ws.row_dimensions[row].height = 30

    r = 16
    subhead(ws, r, "Round-tripping: grade a run, then ask what time would score that grade")
    header_row(ws, r + 1, ["Step", "live", "expected", "check", "note"])
    row = r + 2
    g = grade("M", 40, 10.0, 2400)
    steps = [
        ("1. percent for 40:00",
         '=RRAG.GRADE("M",40,10,"40:00")', round(g.percent, 4), PCT_FMT,
         "The grade of the actual run."),
        ("2. time that scores it",
         '=RRAG.TIMEFORPCT("M",40,10,"&percent&")', 2400 / 86400.0, TIME_FMT,
         "Feeding the percentage back in returns the original time to within 0.02 s: the "
         "percentage carries four decimals, and that is the limit of the round trip."),
        ("3. graded time for 40:00",
         '=RRAG.GRADEDTIME("M",40,10,"40:00")', g.age_graded_s / 86400.0, TIME_FMT,
         "The same run in open-class terms: 38:32.6."),
        ("4. factor behind it",
         '=RRAG.FACTOR("M",40,10)', round(g.factor, 4), FAC_FMT,
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
# sheet 7 — function reference
#
# One row per function, and the list is checked against the add-in's own
# registrations at build time (see check_function_docs), so the page cannot drift
# from the binary that ships beside it.
# ---------------------------------------------------------------------------
FUNCTIONS = [
    ("RRAG.GRADE", "(sex, age, distance, time, [table])",
     "The age grade in percent: 100 x the open standard / (time x factor).",
     "Number, 2 dp. 100 = the world-standard mark for that exact sex and age; above 100 "
     "is a genuine outlier, not an error.",
     "1x1 with scalar arguments; a column in gives a column out.",
     "1 Squad, 2 One call, 4 Vector rules"),
    ("RRAG.GRADEDTIME", "(sex, age, distance, time, [table])",
     "The run converted to open-class age: time x factor.",
     "Excel time value - format the column [h]:mm:ss, or multiply by 86400 for seconds.",
     "Same shape as the inputs.",
     "1 Squad, 6 Times & formats"),
    ("RRAG.FACTOR", "(sex, age, distance, [table])",
     "The multiplier itself, straight from the table.",
     "Number 0 < f <= 1, 4 dp. Older age or longer distance means a smaller factor.",
     "Same shape as the inputs.",
     "1 Squad, 4 Vector rules"),
    ("RRAG.STANDARD", "(sex, age, distance, [table])",
     "The open standard for the distance: the world-class mark with no age adjustment.",
     "Excel time value. Age is accepted and ignored, purely so the signature matches its "
     "siblings.",
     "Same shape as the inputs.",
     "1 Squad, 2 One call"),
    ("RRAG.TIMEFORPCT", "(sex, age, distance, percent, [table])",
     "The inverse: the time that would score the percentage you ask for.",
     "Excel time value. This is the published calculator's Result button.",
     "Same shape as the inputs.",
     "2 One call, 6 Times & formats"),
    ("RRAG.BLOCK", "(sex, age, distance, time, [table])",
     "All five numbers for a squad in one call: factor, open standard, age standard, "
     "age-graded time, age grade.",
     "Five columns per input row, in that order. Row labels come from your own columns.",
     "n x 5 - reserve five columns.",
     "1 Squad"),
    ("RRAG.TABLES", "()",
     "Which editions this build can grade with.",
     "A column of years, newest first; pass one as the fifth argument of any grading "
     "function.",
     "n x 1 - it returns a COLUMN, so leave rows below it free.",
     "2 One call"),
    ("RRAG.TABLEINFO", "([table])",
     "Describe a table: year, how many distances, how many ages, how many sexes.",
     "A 1x4 row of numbers. TRANSPOSE() it if you want it standing up.",
     "1 x 4.",
     "2 One call"),
    ("RRAG.CACHEINFO", "()",
     "The cache counters: built-in editions, loaded CSVs, custom ranges held, hits, "
     "misses, capacity.",
     "A 1x6 row of numbers - no expected values anywhere, they depend on what the "
     "session has done.",
     "1 x 6.",
     "2 One call"),
    ("RRAG.CACHECLEAR", "()",
     "Drop cached CSV and custom-range tables, after editing a table file.",
     "1. Ad hoc ranges are keyed by a hash of their contents, so they cannot go stale; "
     "only CSVs need this.",
     "1 x 1.",
     "2 One call (shown, not live)"),
    ("RRAG.LASTERROR", "()",
     "The reason the most recent call failed, in words.",
     "Text: 'no error', or which argument and which row refused. The first thing to "
     "reach for when a column fills with #NUM!.",
     "1 x 1.",
     "2 One call, 4 Vector rules"),
    ("RRAG.VERSION", "()",
     "What is loaded, and how many editions are compiled in.",
     "Text, e.g. 'aggrade-xll 2025.1 (4 built-in editions)'.",
     "1 x 1.",
     "2 One call"),
]

ARGUMENTS = [
    ("sex", "M, F, Male, Female, Men, Women, 1, 0. Whole words only: 'both' and 'mixed' are "
            "refused rather than guessed at."),
    ("age", "Age on race day, in years. 5-100 is the published grid; below 5 clamps to 5 and "
            "above 99 clamps to 100 (a quirk of the published calculator, reproduced on "
            "purpose). Fractional ages interpolate."),
    ("distance", "A number of km, or a number with a unit: 10k, 10 km, 10 kilometres, 6.2 "
                 "miles, half marathon, marathon. Case, whitespace and hyphens are ignored. "
                 "Outside 1.609344-200 km there is no answer."),
    ("time", "An Excel time value, text like \"40:00\", or a number of seconds. Numbers below 1 "
             "are read as day fractions (Excel time), 1 or more as seconds. Blank rows stay "
             "blank rather than erroring."),
    ("percent", "The age grade you want, as a fraction: 0.75 for 75 %, not 75. A cell "
                "formatted 00.00% shows it as 75.00%."),
    ("table", "Optional. Omit for the newest edition, or pass 2025, 2020, 2015, 2010, "
              "'latest', a <name>.csv in the add-in's folder, or a range holding a custom "
              "table."),
]


def check_function_docs() -> None:
    """The reference sheet must describe exactly what the add-in registers."""
    src = Path(__file__).resolve().parent.parent / "src" / "road_running_age_grading.cpp"
    # two return types: the numeric ones are FPX, the text ones LPOPER
    registered = re.findall(r'Function\(XLL_[A-Z]+, "_xll_rrag_[a-z]+", "(RRAG\.[A-Z]+)"\)',
                            src.read_text())
    documented = [name for name, *_ in FUNCTIONS]
    if sorted(registered) != sorted(documented):
        raise SystemExit(
            "function reference is out of date with the add-in:\n"
            f"  registered but undocumented: {sorted(set(registered) - set(documented))}\n"
            f"  documented but not registered: {sorted(set(documented) - set(registered))}")


def sheet_function_reference(wb: Workbook) -> None:
    ws = wb.create_sheet("Functions")
    widths(ws, {"A": 20, "B": 30, "C": 46, "D": 46, "E": 24, "F": 24})
    r = title(ws, "Every function, and what it gives you back",
              "Twelve worksheet functions in the Road Running category. Type =RRAG. and "
              "Excel lists them with their arguments.")

    check_function_docs()

    note(ws, "A4", "The six grading functions and the five diagnostics: the grading ones take "
                   "sex, age and distance first, and each returns a number, a row or a column. "
                   "Shape matters - a vector argument produces a vector result, so leave the "
                   "cells it will fill free.")
    ws.row_dimensions[4].height = 30

    subhead(ws, 6, "The twelve functions")
    header_row(ws, 7, ["Function", "Arguments", "What it does", "What you get back",
                       "Shape", "Shown live on"])
    for i, (name, args, what, ret, shape, seen) in enumerate(FUNCTIONS):
        row = 8 + i
        c = ws[f"A{row}"]
        c.value, c.font, c.alignment, c.border = name, F_MONO, LEFT_WRAP, BOX
        c.fill = FILL_SUB
        for col, text in (("B", args), ("C", what), ("D", ret), ("E", shape), ("F", seen)):
            c = ws[f"{col}{row}"]
            c.value = text
            c.font = F_MONO if col == "B" else F_BODY
            c.alignment, c.border = LEFT_WRAP, BOX
        ws.row_dimensions[row].height = 15 * max(2, len(ret) // 50 + 1, len(what) // 50 + 1)

    r = 8 + len(FUNCTIONS) + 1
    subhead(ws, r, "The arguments, once")
    header_row(ws, r + 1, ["Argument", "What it accepts"])
    ws.merge_cells(start_row=r + 1, start_column=2, end_row=r + 1, end_column=4)
    for i, (arg, accept) in enumerate(ARGUMENTS):
        row = r + 2 + i
        c = ws[f"A{row}"]
        c.value, c.font, c.alignment, c.border = arg, F_MONO, LEFT_WRAP, BOX
        c.fill = FILL_SUB
        c = ws.cell(row=row, column=2, value=accept)
        c.font, c.alignment, c.border = F_BODY, LEFT_WRAP, BOX
        ws.merge_cells(start_row=row, start_column=2, end_row=row, end_column=4)
        ws.row_dimensions[row].height = 15 * max(1, len(accept) // 96 + 1)

    r = r + 2 + len(ARGUMENTS) + 1
    subhead(ws, r, "Conventions that hold everywhere")
    for line in [
        "Percentages are fractions: 0.6849, not 68.49, so Excel's 00.00% format shows them as "
        "68.49%. Times are Excel time values, so "
        "format them [h]:mm:ss - without the brackets hours wrap at 24 and a marathon reads "
        "as 02:11:00.",
        "Errors are per row. One unreadable row gives #NUM! in that row only; the rest of the "
        "column still grades. RRAG.LASTERROR() says why.",
        "Nothing is snapped to a neighbour. A distance outside the published range, an "
        "unknown edition or a misspelt unit fails the call rather than returning a plausible "
        "wrong number.",
        "The optional table argument changes the edition, never the arithmetic: 68.49% is a "
        "2025 statement, and the same run scores differently under 2020. Publish the year "
        "with the percentage.",
    ]:
        c = ws.cell(row=r + 1, column=1, value="\u2022")
        c.font, c.alignment = F_BODY, TOP_CENTRE
        c = ws.cell(row=r + 1, column=2, value=line)
        c.font, c.alignment = F_BODY, LEFT_WRAP
        ws.merge_cells(start_row=r + 1, start_column=2, end_row=r + 1, end_column=6)
        ws.row_dimensions[r + 1].height = 15 * max(1, len(line) // 110 + 1)
        r += 1

    ws.page_setup.orientation = "landscape"
    ws.page_setup.fitToWidth = 1


# ---------------------------------------------------------------------------
# sheet 8 — reference
# ---------------------------------------------------------------------------
def sheet_reference(wb: Workbook) -> None:
    ws = wb.create_sheet("7 Reference")
    widths(ws, {"A": 14, "B": 10, "C": 10, "D": 52})
    r = title(ws, "Reference", "The distances the tables cover, and the rules every call follows.")

    subhead(ws, 4, "The 22 published distances")
    header_row(ws, 5, ["Published row", "km", "miles", "Notes"])
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
        ev_names = {"1MileRoad": "Type it as 1 mile, 1 m or 1.609344 km. Nothing below this "
                                 "can be graded.",
                    "5kmRoad": "The most-used row in club racing: type 5k or 5 kilometres.",
                    "Half.Mar": "21.0975 km: type half marathon, half-marathon or 21.0975.",
                    "Marathon": "42.195 km: type marathon.",
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
        ("distance", "A number with a unit — 10k, 10 km, 10 kilometre(s), 6.2 miles, 6.2 m — "
                     "or half marathon / marathon, or a bare number of km (10, 12.5). Case, "
                     "spaces and hyphens are ignored: \"10 K M\" and \"HALF-MARATHON\" work. "
                     "Out of range 1.609344-200 km fails."),
        ("time", "Excel time value, text (\"40:00\"), or seconds (2400). Numbers below 1 are time "
                 "serials; 1 or more are seconds."),
        ("percent", "The grade you want, e.g. 75 for 75%."),
        ("table", "Optional: an edition name (2025, 2020, 2015, 2010, latest), a <name>.csv "
                  "sidecar, or a range holding a custom table."),
        ("vectors", "Scalars broadcast. All vectors must be the same length; a mismatch fails the "
                    "whole call and RRAG.LASTERROR() says which arguments differ."),
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
        ("#NUM!", "A lookup failed. Put =RRAG.LASTERROR() in the next cell: it names the row, the "
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
# structural validation
#
# Excel silently "repairs" a workbook that violates its own rules, which is how
# a file arrives with "Removed Records: Cell information" and no clue where. The
# rules that actually bite with openpyxl:
#
#   * an array formula's range may not overlap a merged range (Excel drops the
#     offending cell records);
#   * two merged ranges may not overlap, and a merge may not repeat;
#   * a merge must be anchored on a cell that holds a value.
#
# These are cheap to check, so they are checked on every build and in --check.
# ---------------------------------------------------------------------------
def cell_refs(ref: str) -> set[str]:
    from openpyxl.utils.cell import range_boundaries
    c1, r1, c2, r2 = range_boundaries(ref)
    out = set()
    for r in range(r1, r2 + 1):
        for c in range(c1, c2 + 1):
            out.add(f"{get_column_letter(c)}{r}")
    return out


# The sheets the workbook must contain, in order. A builder function that is
# shadowed (two defs with one name) or never called silently drops a sheet, and
# the workbook still builds - so compare the manifest.
EXPECTED_SHEETS = ["Start here", "Functions", "1 Squad", "2 One call", "3 Editions",
                   "4 Vector rules", "5 Custom tables", "6 Times & formats",
                   "7 Reference"]


def validate(wb) -> list[str]:
    problems: list[str] = []
    if wb.sheetnames != EXPECTED_SHEETS:
        problems.append(f"sheet manifest mismatch: built {wb.sheetnames}, "
                        f"expected {EXPECTED_SHEETS}")
    # A percentage is stored as a fraction. A static 71.27 in a 00.00% cell
    # renders as 7127.00%, which is exactly how the custom-tables sheet shipped
    # a column of MISMATCHes. Nothing else in this workbook puts a number above
    # 10 in a percent-formatted cell, so assert it.
    for ws in wb.worksheets:
        for row in ws.iter_rows():
            for c in row:
                if c.number_format == PCT_FMT and isinstance(c.value, (int, float)) \
                        and abs(c.value) > 10:
                    problems.append(
                        f"{ws.title}!{c.coordinate}: {c.value} in a {PCT_FMT} cell "
                        f"(a percentage is stored as a fraction)")

    for ws in wb.worksheets:
        merges = []
        for rng in ws.merged_cells.ranges:
            ref = str(rng)
            merges.append(ref)
            anchor = ws.cell(row=rng.min_row, column=rng.min_col).value
            if anchor is None or (isinstance(anchor, str) and not anchor.strip()):
                problems.append(f"{ws.title}: merged range {ref} has no value in its anchor cell")
        # overlapping or duplicate merges
        seen: dict[str, str] = {}
        for ref in merges:
            for cell in cell_refs(ref):
                if cell in seen:
                    problems.append(f"{ws.title}: {ref} overlaps {seen[cell]} at {cell}")
                    break
                seen[cell] = ref
        # a dynamic array cannot spill onto a cell that already holds a value
        # (Excel shows #SPILL!), so every cell in an intended spill area except
        # its anchor must be empty
        for sheet, anchor, area, shape in _SPILLS:
            if sheet != ws.title:
                continue
            min_c, min_r, max_c, max_r = range_boundaries(area)
            if f"{get_column_letter(min_c)}{min_r}" != anchor:
                problems.append(f"{ws.title}: spill area {area} does not start at {anchor}")
            if shape and (max_r - min_r + 1, max_c - min_c + 1) != tuple(shape):
                problems.append(
                    f"{ws.title}: {anchor} reserves {max_r - min_r + 1}x{max_c - min_c + 1} "
                    f"({area}) but the function returns {shape[0]}x{shape[1]} "
                    f"-> #SPILL! or a truncated result")
            for cell in sorted(cell_refs(area) - {anchor}):
                v = ws[cell].value
                if v is not None and not (isinstance(v, str) and not v.strip()):
                    problems.append(f"{ws.title}: {anchor} spills over {cell}, "
                                    f"which holds {v!r} -> #SPILL! in Excel")

        # text that looks like a formula must carry the quote prefix, or Excel
        # converts it back into a formula when the file opens
        for row in ws.iter_rows():
            for c in row:
                if c.data_type == "s" and isinstance(c.value, str) and c.value.startswith("="):
                    if not c.quotePrefix:
                        problems.append(
                            f"{ws.title}!{c.coordinate}: text starts with \"=\" but has no "
                            f"quotePrefix - Excel will turn it into a formula")

        # an RRAG.* formula outside live() is a label that will actually run
        for row in ws.iter_rows():
            for c in row:
                if c.data_type != "f" or not isinstance(c.value, str):
                    continue
                if re.match(r"^\s*=?\s*AG\.", c.value) and (ws.title, c.coordinate) not in _LIVE:
                    problems.append(
                        f"{ws.title}!{c.coordinate}: runs {c.value[:40]} but is not a live "
                        f"cell - use show_call() for a label")

        # array formulas must not touch a merge
        for row in ws.iter_rows():
            for c in row:
                v = c.value
                if isinstance(v, ArrayFormula):
                    if f"{get_column_letter(c.column)}{c.row}" != v.ref.split(":")[0]:
                        problems.append(f"{ws.title}!{c.coordinate}: array formula anchored "
                                        f"away from the top-left of {v.ref}")
                    for cell in cell_refs(v.ref):
                        if cell in seen:
                            problems.append(f"{ws.title}: array formula {v.ref} overlaps "
                                            f"merged range {seen[cell]} at {cell}")
                            break
    return problems



def guard_verdicts(wb) -> None:
    """Keep every OK/MISMATCH cell silent until there is something to compare.

    Without this, a squad sheet opened before the add-in is loaded shows a wall
    of MISMATCH: the live cells are blank, so `ABS(blank - expected)` is simply
    a large number. A blank is not a disagreement, and an error is not one
    either - the error is already visible in the live cell.
    """
    import re
    for ws in wb.worksheets:
        for row in ws.iter_rows():
            for c in row:
                v = c.value
                if not isinstance(v, str) or not v.startswith("=") or '"MISMATCH"' not in v:
                    continue
                if "COUNTA(" in v:
                    # Some blocks write their own blank guard. Wrapping again
                    # nests the same test and doubles the formula's length for
                    # nothing, so treat an existing guard as done.
                    continue
                inner = v[1:]
                m = re.search(r"ABS\(([^()-]+?)-", v)
                if m and re.match(r"^[A-Z]+\d+(:[A-Z]+\d+)?$", m.group(1)):
                    c.value = f'=IF(COUNTA({m.group(1)})=0,"",IFERROR({inner},""))'
                else:
                    c.value = f'=IFERROR({inner},"")'



# ---------------------------------------------------------------------------
# dynamic-array metadata
#
# openpyxl has no concept of Excel's dynamic arrays. What Excel writes for one
# is: the cell as a one-cell array formula, marked `cm="1"`, plus a metadata
# part declaring XLDAPR with fDynamic="1". Without the mark Excel treats the
# formula as pre-365 and inserts an implicit-intersection "@", so nothing
# spills. The three parts below are copied verbatim from a workbook Excel saved
# itself (a dynamic array cell there reads:
#   <c r="B12" cm="1" s="7"><f t="array" ref="B12">...</f></c>).
# ---------------------------------------------------------------------------
METADATA_XML = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<metadata xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
    ' xmlns:xda="http://schemas.microsoft.com/office/spreadsheetml/2017/dynamicarray">'
    '<metadataTypes count="1">'
    '<metadataType name="XLDAPR" minSupportedVersion="120000" copy="1" pasteAll="1"'
    ' pasteValues="1" merge="1" splitFirst="1" rowColShift="1" clearFormats="1"'
    ' clearComments="1" assign="1" coerce="1" cellMeta="1"/>'
    '</metadataTypes>'
    '<futureMetadata name="XLDAPR" count="1"><bk><extLst>'
    '<ext uri="{bdbb8cdc-fa1e-496e-a857-3c3f30c029c3}">'
    '<xda:dynamicArrayProperties fDynamic="1" fCollapsed="0"/>'
    '</ext></extLst></bk></futureMetadata>'
    '<cellMetadata count="1"><bk><rc t="1" v="0"/></bk></cellMetadata>'
    '</metadata>'
)
METADATA_CT = ('<Override PartName="/xl/metadata.xml" ContentType="application/'
               'vnd.openxmlformats-officedocument.spreadsheetml.sheetMetadata+xml"/>')
METADATA_REL = ('<Relationship Id="rId{id}" Type="http://schemas.openxmlformats.org/'
                'officeDocument/2006/relationships/sheetMetadata" '
                'Target="metadata.xml"/>')


def postprocess(path: Path) -> None:
    """Add the metadata part and mark every array cell `cm="1"`.

    Every live RRAG.* cell is stored as a one-cell array formula, because that is
    how an array-returning function has to be persisted. Without the XLDAPR mark
    Excel reads that as a legacy Ctrl+Shift+Enter formula and shows it as
    {=RRAG.GRADE(...)} - braces and no spilling. With the mark it is a dynamic
    array: no braces, and it spills when there is more than one value. So the
    mark goes on every such cell, scalar results included, exactly as Excel does
    when it saves a call to an array-returning function.
    """
    import re
    import zipfile

    cell_re = re.compile(r'<c r="([A-Z]+\d+)"([^>]*)>(.*?)</c>', re.S)
    with zipfile.ZipFile(path) as z:
        order = re.findall(r'<sheet name="([^"]+)"',
                           z.read("xl/workbook.xml").decode("utf-8"))
        types = z.read("[Content_Types].xml").decode("utf-8")
        rels = z.read("xl/_rels/workbook.xml.rels").decode("utf-8")
        parts = {n: z.read(n) for n in z.namelist()}

    if "metadata.xml" not in types:
        types = types.replace("</Types>", METADATA_CT + "</Types>")
    if "sheetMetadata" not in rels:
        # Excel numbers its relationships rId1..rIdN; a non-numeric id is legal
        # XML but not what Excel writes, and this file has been repaired once
        # already, so match the convention exactly.
        used = [int(n) for n in re.findall(r'Id="rId(\d+)"', rels)]
        rel = METADATA_REL.format(id=max(used) + 1 if used else 1)
        rels = rels.replace("</Relationships>", rel + "</Relationships>")

    marked = 0
    for i, _title in enumerate(order):
        part = f"xl/worksheets/sheet{i + 1}.xml"
        if part not in parts:
            continue
        xml = parts[part].decode("utf-8")

        def fix(m):
            ref, attrs, inner = m.group(1), m.group(2), m.group(3)
            if '<f t="array"' not in inner:
                return m.group(0)                      # not an array cell
            if f'<f t="array" ref="{ref}">' not in inner:
                raise SystemExit(
                    f"postprocess: {part} {ref} is a legacy multi-cell CSE formula "
                    f"- the workbook must use dynamic arrays only")
            if "cm=" in attrs:
                return m.group(0)                      # already marked
            nonlocal marked
            marked += 1
            return f'<c r="{ref}" cm="1"{attrs}>{inner}</c>'

        parts[part] = cell_re.sub(fix, xml).encode("utf-8")

    if marked == 0:
        raise SystemExit("postprocess: no array cells found - wrong sheet mapping?")

    parts["[Content_Types].xml"] = types.encode("utf-8")
    parts["xl/_rels/workbook.xml.rels"] = rels.encode("utf-8")
    parts["xl/metadata.xml"] = METADATA_XML.encode("utf-8")

    # rewrite deterministically: fixed order and timestamps, so --check can
    # compare byte for byte
    tmp = path.with_suffix(".meta.tmp")
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
        for name in sorted(parts):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o600 << 16
            z.writestr(info, parts[name])
    tmp.replace(path)
    print(f"      marked {marked} array cells for dynamic-array behaviour")


# ---------------------------------------------------------------------------
def build(path: Path) -> None:
    wb = Workbook()
    sheet_start(wb)
    sheet_function_reference(wb)   # read second, before any sheet that uses a function
    sheet_squad(wb)
    sheet_one_call(wb)
    sheet_editions(wb)
    sheet_vectors(wb)
    sheet_custom(wb)
    sheet_times(wb)
    sheet_reference(wb)
    guard_verdicts(wb)

    # There are no cached results in this file - every value comes from the
    # add-in - so Excel must recalculate on open.
    wb.calculation.calcMode = "auto"          # not manual, not autoNoTable
    wb.calculation.fullCalcOnLoad = True
    wb.calculation.forceFullCalc = True
    # and do not save stale values from a manual session
    wb.calculation.calcOnSave = True

    problems = validate(wb)
    if problems:
        raise SystemExit("refusing to write a structurally invalid workbook:\n  "
                         + "\n  ".join(problems))
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
    postprocess(path)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="fail if the committed workbook is not what this script builds")
    a = ap.parse_args()

    tmp = OUT.with_suffix(".tmp.xlsx")
    build(tmp)

    if a.check:
        committed = load_workbook(OUT) if OUT.exists() else None
        if committed is not None:
            problems = validate(committed)
            if problems:
                for pb in problems:
                    print(f"  INVALID  {pb}", file=sys.stderr)
                print(f"{OUT.name}: structurally invalid", file=sys.stderr)
                tmp.unlink(missing_ok=True)
                return 1
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
