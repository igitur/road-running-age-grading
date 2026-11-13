"""BRRAG — Botha's Road Running Age Grading: USATF MLDR road tables.

Reference implementation of the published calculator's arithmetic.

    >>> from brrag import table
    >>> t = table(2025, "M")
    >>> g = t.grade("M", 40, 40 * 60, dist_km=10)
    >>> round(g.percent, 2)
    68.49
"""

try:  # from the installed metadata; set by the git tag at build time
    from importlib.metadata import PackageNotFoundError, version as _dist_version
    try:
        __version__ = _dist_version("brrag")
    except PackageNotFoundError:      # running from an unbuilt source tree
        __version__ = "0.0.0+unknown"
except ImportError:                    # pragma: no cover - Python < 3.8
    __version__ = "0.0.0+unknown"

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
    "__version__", "CALIBRATION_KM", "Event", "Grade", "Lookup", "OutOfRange", "Tables",
    "load_tables", "table", "format_time", "parse_time", "ui_percent",
    "ui_seconds",
]
