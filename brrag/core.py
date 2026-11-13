"""Reference implementation of USATF MLDR road age-grading (2025 tables).

Mirrors the arithmetic of the published calculator
(https://www.howardgrubb.co.uk/athletics/mldrroad25.html) exactly, including
its rounding and clamping behaviour. See docs/03-grading-algorithm.md.

Public API
----------
load_tables(path)                 -> Tables
Tables.lookup(sex, age, dist_km)  -> Lookup(factor, standard_s)
Tables.grade(sex, age, dist_km, time_s) -> Grade
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

def _default_data() -> Path:
    """Where the tables live.

    An installed package carries its own copy (brrag/data/mldr_road.json); a
    source checkout keeps them in the repo's data/ directory, derived from the
    published calculator page by tools/extract_tables.py. The packaged copy wins
    so a wheel never reads outside itself.
    """
    packaged = Path(__file__).resolve().parent / "data" / "mldr_road.json"
    if packaged.exists():
        return packaged
    return Path(__file__).resolve().parent.parent / "data" / "mldr_road.json"


DEFAULT_DATA = _default_data()

#: Key ("calibration") distances: the only ones actually fitted. Everything
#: else in the published table is logarithmically interpolated from these.
CALIBRATION_KM = (5.0, 10.0, 21.0975, 42.195)


class OutOfRange(ValueError):
    """Raised when the request falls outside what the tables can answer."""


@dataclass(frozen=True)
class Event:
    name: str
    distance_km: float
    standard_s: float
    factors: tuple[float, ...]

    @property
    def is_calibration(self) -> bool:
        return any(math.isclose(self.distance_km, d, rel_tol=0, abs_tol=1e-6)
                   for d in CALIBRATION_KM)


@dataclass(frozen=True)
class Lookup:
    factor: float
    standard_s: float

    @property
    def age_standard_s(self) -> float:
        """Time that scores 100% for this age (the 'age standard')."""
        return self.standard_s / self.factor


@dataclass(frozen=True)
class Grade:
    age_graded_s: float
    percent: float
    factor: float
    standard_s: float
    age_standard_s: float
    predicted_at_standard_s: float  # time that would score 100%


class Tables:
    """One year/authority/sex set of factors."""

    def __init__(self, meta: dict, ages: Iterable[int], events: Iterable[Event]):
        self.meta = meta
        self.ages = list(ages)
        self.events = sorted(events, key=lambda e: e.distance_km)
        self._by_name = {e.name.casefold(): e for e in self.events}
        for ev in self.events:
            if len(ev.factors) != len(self.ages):
                raise ValueError(
                    f"{ev.name}: {len(ev.factors)} factors, {len(self.ages)} ages"
                )

    # -- metadata --------------------------------------------------------
    def __repr__(self) -> str:
        return (f"<Tables {self.meta.get('authority')} {self.meta.get('year')} "
                f"{self.meta.get('sex')} {len(self.events)} events>")

    @property
    def event_names(self) -> list[str]:
        return [e.name for e in self.events]

    def event(self, name: str) -> Event:
        try:
            return self._by_name[name.casefold()]
        except KeyError:
            raise OutOfRange(f"unknown event {name!r}; known: {self.event_names}") from None

    # -- age axis --------------------------------------------------------
    def _bracket_age(self, age: float,
                     policy: str = "ui") -> tuple[int, int, float]:
        """Return (i0, i1, proportion) with the published clamping rules.

        Ages at or below the first table age use the first column; ages at or
        above the last use the last column. Between ages it is linear
        interpolation — with one faithful quirk of the calculator, kept here
        so results match it exactly:

          the page clamps as soon as its search index reaches the last row,
          so any age in (99, 100] is given the age-100 factors instead of
          being interpolated between 99 and 100. The low end (<= 5) has no
          such gap. `policy="linear"` interpolates normally instead.
        """
        ages = self.ages
        n = len(ages)
        if policy == "linear":
            if age <= ages[0]:
                return 0, 0, 0.0
            if age >= ages[-1]:
                return n - 1, n - 1, 0.0
        else:  # "ui": what the JavaScript does
            if age <= ages[0]:
                return 0, 0, 0.0
            if age > ages[-2]:
                return n - 1, n - 1, 0.0
        # first index with ages[i] >= age
        i = 0
        while i < n and ages[i] < age:
            i += 1
        i0, i1 = i - 1, i
        span = ages[i1] - ages[i0]
        prop = 0.0 if span == 0 else (age - ages[i0]) / span
        return i0, i1, prop

    # -- distance axis ---------------------------------------------------
    def _bracket_distance(self, dist_km: float,
                          policy: str = "strict") -> tuple[int, int, float]:
        """Return (e0, e1, proportion) over the *listed* event distances.

        Interpolation is LINEAR IN DISTANCE (not in log-distance) between the
        two nearest published distances — this is what the calculator does.

        Outside the published range the calculator yields no result at all:
        distances below the shortest event (1 mile) and above the longest
        (200 km) both leave its fields blank. `policy` chooses what happens
        instead:

          "strict" (default) — raise OutOfRange, matching the calculator's
                        refusal to answer
          "clamp"       — use the nearest end row (what most ports do)
        """
        events = self.events
        dmin, dmax = events[0].distance_km, events[-1].distance_km
        if dist_km < dmin or dist_km > dmax:
            if policy == "clamp":
                return (0, 0, 0.0) if dist_km < dmin else \
                       (len(events) - 1, len(events) - 1, 0.0)
            raise OutOfRange(
                f"{dist_km} km is outside the published range "
                f"{dmin}-{dmax} km; the calculator returns no result "
                f"(pass policy='clamp' to use the nearest event instead)"
            )
        # last index whose distance <= dist_km
        i = len(events) - 1
        for j, ev in enumerate(events):
            if ev.distance_km > dist_km:
                i = j - 1
                break
        i = max(i, 0)
        j = min(i + 1, len(events) - 1)
        if j == i:
            return i, i, 0.0
        d0, d1 = events[i].distance_km, events[j].distance_km
        prop = (dist_km - d0) / (d1 - d0)
        return i, j, prop

    # -- core lookup -----------------------------------------------------
    def lookup(self, sex: str, age: float, dist_km: float | None = None,
               event: str | None = None, policy: str = "strict",
               age_policy: str = "ui") -> Lookup:
        """Bilinear lookup of (factor, open standard) in age and distance."""
        if event is not None:
            e0 = e1 = self.event(event)
            pd = 0.0
        elif dist_km is not None:
            i0, i1, pd = self._bracket_distance(dist_km, policy=policy)
            e0, e1 = self.events[i0], self.events[i1]
        else:
            raise TypeError("pass either event= or dist_km=")

        ia, ib, pa = self._bracket_age(age, policy=age_policy)

        f00 = e0.factors[ia]
        f01 = e0.factors[ib]
        f10 = e1.factors[ia]
        f11 = e1.factors[ib]
        factor = (1.0 - pd) * (pa * f01 + (1.0 - pa) * f00) + \
                 pd * (pa * f11 + (1.0 - pa) * f10)
        standard = (1.0 - pd) * e0.standard_s + pd * e1.standard_s
        return Lookup(factor=factor, standard_s=standard)

    def grade(self, sex: str, age: float, time_s: float,
              dist_km: float | None = None, event: str | None = None,
              policy: str = "strict", age_policy: str = "ui") -> Grade:
        """Grade a performance. `time_s` in seconds; the only unit that matters."""
        if time_s <= 0:
            raise ValueError("time must be positive")
        lk = self.lookup(sex, age, dist_km=dist_km, event=event, policy=policy,
                         age_policy=age_policy)
        if lk.factor <= 0:
            raise OutOfRange("non-positive age factor; performance not gradable")
        astd = lk.age_standard_s
        return Grade(
            age_graded_s=time_s * lk.factor,
            percent=100.0 * astd / time_s,
            factor=lk.factor,
            standard_s=lk.standard_s,
            age_standard_s=astd,
            predicted_at_standard_s=astd,
        )

    def time_for_percent(self, sex: str, age: float, percent: float,
                         dist_km: float | None = None,
                         event: str | None = None,
                         policy: str = "strict") -> float:
        """Inverse: the time that would score `percent` (the calculator's
        'Result' button)."""
        lk = self.lookup(sex, age, dist_km=dist_km, event=event, policy=policy)
        return lk.age_standard_s / (percent / 100.0)


def load_tables(path: str | Path = DEFAULT_DATA) -> dict[str, Tables]:
    """Load every table in the JSON data file, keyed 'AUTHORITY YEAR SEX'."""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    out: dict[str, Tables] = {}
    for key, t in raw["tables"].items():
        events = [
            Event(name=e["event"], distance_km=e["distance_km"],
                  standard_s=e["open_standard_s"], factors=tuple(e["factors"]))
            for e in t["events"]
        ]
        out[key] = Tables(t, t["ages"], events)
    return out


def table(year: int = 2025, sex: str = "M", authority: str | None = None,
          path: str | Path = DEFAULT_DATA) -> Tables:
    """Convenience accessor: table(2025, "F"), table(2010, "M").

    `authority` defaults to whichever one published that year - USATF MLDR for
    2020 and 2025, WMA for 2010 and 2015 - so a caller needs only the year.
    """
    tables = load_tables(path)
    if authority is not None:
        return tables[f"{authority} {year} {sex.upper()}"]
    suffix = f" {year} {sex.upper()}"
    for key, tbl in tables.items():
        if key.endswith(suffix):
            return tbl
    raise OutOfRange(
        f"no {sex.upper()} table for {year}; known editions: "
        f"{sorted({k.rsplit(' ', 2)[1] for k in tables})}")
