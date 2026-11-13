"""USATF MLDR road-running age-grading — reference implementation.

    >>> from aggrade import table
    >>> t = table(2025, "M")
    >>> g = t.grade("M", 40, 40 * 60, dist_km=10)
    >>> round(g.percent, 2)
    68.49
"""

from .core import (  # noqa: F401
    CALIBRATION_KM,
    Event,
    Grade,
    Lookup,
    OutOfRange,
    Tables,
    load_tables,
    table,
)
from .ui import (  # noqa: F401
    format_time,
    parse_time,
    ui_percent,
    ui_seconds,
)

__all__ = [
    "CALIBRATION_KM", "Event", "Grade", "Lookup", "OutOfRange", "Tables",
    "load_tables", "table", "format_time", "parse_time", "ui_percent",
    "ui_seconds",
]
