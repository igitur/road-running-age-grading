"""Formatting helpers that reproduce the published calculator's display maths.

The calculator rounds the age standard to a string *before* dividing it into
the result, so the percentage it shows carries a rounding artefact:

    astd_shown = hms_string(std / factor)     # 0/1/2 decimals by magnitude
    percent    = 100 * seconds(astd_shown) / result

Use these helpers when you need byte-for-byte parity with the web UI. For
analysis, prefer the unrounded values on Grade.
"""

from __future__ import annotations

import math

__all__ = ["ui_seconds", "ui_percent", "parse_time", "format_time"]


def ui_seconds(secs: float) -> float:
    """Round like the page's hms_string(): 2 dp under a minute, 1 dp under an
    hour, whole seconds from an hour up. Rounds half away from zero."""
    ndec = 1
    if secs >= 3600:
        ndec = 0
    if secs < 60:
        ndec = 2
    p = 10 ** ndec
    return math.floor(secs * p + 0.5) / p


def ui_percent(time_s: float, age_standard_s: float) -> float:
    """The grade, out of 1, exactly as the calculator displays it (2 dp).

    The page shows 68.49 %; this returns 0.6849 so it matches
    `Grade.percent` and Excel's percent number format. Multiply by 100 to
    print a percentage.
    """
    raw = ui_seconds(age_standard_s) / time_s
    return math.floor(raw * 10000 + 0.5) / 10000


def parse_time(text: str) -> float:
    """Parse 'h:mm:ss[.dd]' / 'mm:ss[.dd]' / raw seconds into seconds.

    Follows the calculator: one colon means mm:ss, two mean h:mm:ss, no colon
    means seconds. Also accepts ';' as a separator (the page does).
    """
    s = text.strip().replace(";", ":")
    if not s:
        raise ValueError("empty time")
    parts = s.split(":")
    if len(parts) > 3:
        raise ValueError(f"unparseable time: {text!r}")
    total = 0.0
    for part in parts:
        total = total * 60 + float(part)
    return total


def format_time(secs: float, decimals: int | None = None) -> str:
    """Format seconds as h:mm:ss[.d] (mm:ss[.d] under an hour)."""
    if secs < 0:
        raise ValueError("negative time")
    if decimals is None:
        decimals = 0 if secs >= 3600 else 1
    total_units = int(round(secs * 10 ** decimals))
    scale = 10 ** decimals
    whole, frac = divmod(total_units, scale)
    hours, rem = divmod(whole, 3600)
    minutes, seconds = divmod(rem, 60)
    if decimals:
        out = f"{seconds:02d}.{frac:0{decimals}d}"
    else:
        out = f"{seconds:02d}"
    out = f"{minutes:02d}:{out}" if (hours or minutes) else out
    return f"{hours}:{out}" if hours else out
