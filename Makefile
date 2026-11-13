# Age-grading docs + reference implementation.
# `make check` is what CI (or a future table revision) should run.

PY ?= $(shell [ -x .venv/bin/python ] && echo .venv/bin/python || echo python3)
UPSTREAM := https://github.com/AlanLyttonJones/Age-Grade-Tables.git

.PHONY: help all setup fetch unpack data verify curve wiki check check-links xll-test clean

help:
	@echo "setup    create .venv and install tool dependencies"
	@echo "fetch    download the source artefacts (calculator page, xlsm, upstream clone)"
	@echo "unpack   unzip the xlsm (sheet XML + vbaProject.bin) into raw/"
	@echo "data     re-extract factor tables from page.html -> data/mldr_road.json"
	@echo "verify   run checks A/B/C (exact grid, JS oracle, standards cross-check)"
	@echo "curve    reproduce factor curves from the fitted parameters"
	@echo "wiki     render docs/*.md -> wiki/*.html"
	@echo "check    verify + curve + wiki link check   <-- the CI target"
	@echo "check-links  verify every docs/ cross-page link and anchor"
	@echo "xll-test verify the Excel add-in core (needs g++ only)"
	@echo "all      fetch + unpack + data + verify + curve + wiki"

all: fetch unpack data verify curve wiki
	@echo OK

setup:
	uv venv --python 3.12 .venv
	uv pip install --python .venv/bin/python -r requirements-tools.txt

fetch:
	@echo "-> calculator page"
	curl -sS -o page.html https://www.howardgrubb.co.uk/athletics/mldrroad25.html
	@echo "-> factors workbook"
	curl -sS -o MLDRRoadFactors2025.xlsm https://www.howardgrubb.co.uk/athletics/data/MLDRRoadFactors2025.xlsm
	@echo "-> upstream tables repository (needed by check C)"
	test -d repo || git clone --depth 1 $(UPSTREAM) repo
	@echo "-> verifying hashes"; sha256sum -c data/source_sha256.txt

unpack:
	rm -rf raw && mkdir -p raw && cd raw && unzip -o ../MLDRRoadFactors2025.xlsm >/dev/null
	@echo "raw/ holds the sheet XML and xl/vbaProject.bin; dump the macros with:"
	@echo "  .venv/bin/olevba raw/xl/vbaProject.bin"

data:
	$(PY) tools/extract_tables.py page.html data/mldr_road.json

verify:
	$(PY) tools/verify.py --all

curve:
	$(PY) tools/reproduce_curve.py

wiki:
	$(PY) tools/render_wiki.py

check-links:
	$(PY) tools/render_wiki.py --check

# The add-in's portable core and test suite. Building the .xll itself needs
# mingw-w64 and the patched xll library; see xll/README.md.
xll-test:
	$(MAKE) -C xll test

check:
	$(PY) tools/verify.py --all && \
	$(PY) tools/reproduce_curve.py && \
	$(PY) tools/render_wiki.py --check && \
	$(PY) xll/tools/gen_tables.py --check && \
	$(PY) xll/tools/gen_expectations.py --check && \
	$(MAKE) -C xll test

clean:
	rm -rf wiki raw
