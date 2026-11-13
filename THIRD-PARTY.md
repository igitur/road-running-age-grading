# Third-party components

This project is **MIT** (see [LICENSE](LICENSE)) for its own code and prose. The
components below are included, linked or relied on, and **none of them are
relicensed by that MIT grant** — each keeps its own terms. This file exists so
that a reader of the wheel, the sdist or the Excel bundle can see the whole
picture in one place instead of auditing it.

| Component | Licence | Where it lands | Notes |
|---|---|---|---|
| Age-grading factor tables, all four editions (2010, 2015, 2020, 2025) | **CC0-1.0** | `data/mldr_road.json`, `brrag/data/mldr_road.json`, compiled into `road_running_age_grading.xll` | Upstream <https://github.com/AlanLyttonJones/Age-Grade-Tables> is a CC0 1.0 public-domain dedication, so there is no condition to satisfy — the credit below is scholarly, not a licence term |
| `xll` add-in framework (`xlladdins/xll`) | **MIT** © 2022 xlladdins | fetched at build time, pinned by commit; **not vendored** in this repository | The repository carries only `xll/patches/xll-mingw-portability.patch` (MIT permits modification). The resulting binary embeds the framework, so its notice travels with the Excel bundle |
| GCC runtime — `libstdc++`, `libgcc`, mingw-w64 runtime | **GPLv3 with the GCC Runtime Library Exception**; mingw-w64 runtime is public-domain/ZPL-style | statically linked inside `road_running_age_grading.xll` | The .xll imports only Windows system DLLs (`KERNEL32`, `msvcrt`, `USER32`, `ADVAPI32`, `SHLWAPI`), so these runtimes are inside the file. The Runtime Library Exception exists precisely so such a binary may be distributed under any terms; the project itself stays MIT |
| Howard Grubb's calculator page (`page.html`) | **no licence granted** — byline only | repository, for verification only; **excluded from the sdist** | Used as the test oracle: the published calculator's own JavaScript is the algorithm of record. Not part of the Python package and not redistributed on PyPI |
| `MLDRRoadFactors2025.xlsm` (official factors workbook) | **no licence granted** — `docProps/core.xml` names Howard Grubb | repository, for verification only; **excluded from the sdist** | The *values* extracted from it are covered by the CC0 upstream above; the workbook file itself is not |
| Microsoft `XLCALL.H` / `XLCALL.CPP` (Excel Developer's Toolkit) | Microsoft SDK EULA | compile-time only — **not distributed** | `xll/shim/` is untracked, and no XLCALL file is present in the wheel, the sdist or the Excel bundle |
| `openpyxl`, `oletools`, `pypdf`, `setuptools`, `setuptools-scm` | MIT / BSD / BSD / MIT / MIT | development and build only — **never in the wheel or sdist** | Listed in `requirements-tools.txt`; `brrag` itself has no runtime dependencies |

## Credit

The age factors are not mine. They are compiled by **Alan Jones**
(alanjones@grests.com) with single-age bests by **Tom Bernhard**, approved by the
**USATF Masters Long Distance Running** committee; the calculator they ship with
is **Howard Grubb's** (howardgrubb.co.uk). If you publish a percentage, quote the
table year and credit the tables to their authors rather than to this repository.

The upstream artefacts are committed unmodified with their SHA-256 sums in
[`data/source_sha256.txt`](data/source_sha256.txt), so a silent upstream change is
detectable.
