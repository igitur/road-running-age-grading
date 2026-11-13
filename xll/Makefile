# Makefile for the age-grading Excel add-in.
#
# Builds a 64-bit .xll with mingw-w64 on Linux (no Windows machine needed) and
# runs the same core sources as a native test binary.
#
#   make            native tests, then the .xll
#   make test       native tests only
#   make xll        the add-in only
#   make verify     inspect the .xll export/import tables
#   make tables     regenerate src/ag_tables_generated.h from ../data
#   make expectations  regenerate test/expected.h from the Python implementation
#   make clean
#
# Requirements: sudo apt install gcc-mingw-w64-x86-64 g++-mingw-w64-x86-64
# The xll library must be checked out at $(XLL_DIR); see README.md.

NAME      := xll_age_grading
XLL_DIR   ?= $(HOME)/code/xll
XLL       := x86_64-w64-mingw32-g++
XLLCC     := x86_64-w64-mingw32-gcc
CXX       ?= g++

SRC       := src/ag_core.cpp src/ag_api.cpp
HDR       := src/ag_core.h src/ag_api.h src/ag_tables_generated.h

INC       := -I shim -I $(XLL_DIR) -I src
XLLFLAGS  := -std=c++20 -O2 -D_M_X64 -DXLL_VERSION=12 -DUNICODE -D_UNICODE \
             -Dpascal=__stdcall -D_cdecl=__cdecl $(INC) \
             -Wno-unknown-pragmas -Wno-unused-parameter -Wno-attributes
CFLAGS    := -std=gnu17 -O2 -D_M_X64 -DXLL_VERSION=12 -DUNICODE -D_UNICODE \
             -Dpascal=__stdcall $(INC) -Wno-unknown-pragmas
NFLAGS    := -std=c++17 -O2 -Wall -Wextra -Wno-unused-parameter -I src -I test

# The library sources every XLL needs, plus the Excel4 compatibility shim
# (mingw cannot link XLCALL32.LIB, so excel4_compat.cpp supplies Excel4/Excel4v).
LIBOBJS   := auto.o dllmain.o error.o XLCALL.o defines.o excel4_compat.o
OBJS      := age_grading.o ag_core.o ag_api.o $(LIBOBJS)

.PHONY: all test xll verify tables expectations clean shim

all: test xll verify

# ---------------------------------------------------------------- native ----
test: $(SRC) test/test_main.cpp $(HDR) test/expected.h
	$(CXX) $(NFLAGS) $(SRC) test/test_main.cpp -o $(NAME)_test
	./$(NAME)_test

# ------------------------------------------------------------------- xll ----
xll: $(NAME).xll

$(NAME).xll: $(OBJS) $(NAME).def
	$(XLL) -shared -o $@ $(OBJS) $(NAME).def \
	    -Wl,-s -lshlwapi -ladvapi32 -static-libgcc -static-libstdc++

age_grading.o: src/xll_age_grading.cpp $(HDR)
	$(XLL) $(XLLFLAGS) -c $< -o $@
ag_core.o: src/ag_core.cpp $(HDR)
	$(XLL) $(XLLFLAGS) -c $< -o $@
ag_api.o: src/ag_api.cpp $(HDR)
	$(XLL) $(XLLFLAGS) -c $< -o $@
auto.o: $(XLL_DIR)/xll/auto.cpp
	$(XLL) $(XLLFLAGS) -c $< -o $@
dllmain.o: $(XLL_DIR)/xll/dllmain.cpp
	$(XLL) $(XLLFLAGS) -c $< -o $@
error.o: $(XLL_DIR)/xll/error.cpp
	$(XLL) $(XLLFLAGS) -c $< -o $@
XLCALL.o: $(XLL_DIR)/xll/XLCALL.CPP
	$(XLL) $(XLLFLAGS) -c $< -o $@
# defines.c MUST be compiled as C by the gcc driver
defines.o: $(XLL_DIR)/xll/defines.c
	$(XLLCC) $(CFLAGS) -c $< -o $@
excel4_compat.o: excel4_compat.cpp
	$(XLL) $(XLLFLAGS) -c $< -o $@

# ---------------------------------------------------------------- verify ----
verify: $(NAME).xll
	@echo "--- exports (all xll_ag_* plus the Excel entry points) ---"
	@x86_64-w64-mingw32-objdump -p $(NAME).xll | awk '/Export Tables/,0' \
	  | grep -oE 'xll_ag_[a-z]+|xlAuto[A-Za-z0-9]+|XLCallVer|xll_alert_level_' | sort -u
	@echo "--- every symbol named in $(NAME).def must actually be exported ---"
	@x86_64-w64-mingw32-objdump -p $(NAME).xll \
	  | sed -n '/Ordinal\/Name Pointer/,/^$$/p' | awk '{print $$NF}' > .exports.tmp
	@missing=0; for sym in $$(grep -E '^ +[A-Za-z_]' $(NAME).def | tr -d '\r' | awk '{print $$1}'); do \
	  grep -qx "$$sym" .exports.tmp || { echo "  MISSING EXPORT: $$sym"; missing=1; }; \
	done; rm -f .exports.tmp; \
	if [ $$missing -eq 0 ]; then echo "  all .def symbols exported"; else exit 1; fi
	@echo "--- imports (must be system DLLs only) ---"
	@x86_64-w64-mingw32-objdump -p $(NAME).xll | awk '/DLL Name/{print $$3}' | sort -u

# ------------------------------------------------------- generated sources --
tables: src/ag_tables_generated.h

src/ag_tables_generated.h: ../data/mldr_road.json tools/gen_tables.py
	python3 tools/gen_tables.py

expectations: test/expected.h

test/expected.h: ../aggrade/core.py tools/gen_expectations.py
	python3 tools/gen_expectations.py

# The shim dir fixes the library's capitalised includes (Windows.h, WinBase.h,
# Shlwapi.h, xlcall.h) which are lowercase in mingw-w64 on a case-sensitive FS.
shim:
	@mkdir -p shim
	@for h in Windows.h WinBase.h Shlwapi.h; do \
	  l=$$(echo $$h | tr 'A-Z' 'a-z'); \
	  [ -e shim/$$h ] || ln -sf /usr/x86_64-w64-mingw32/include/$$l shim/$$h; \
	done
	@[ -e shim/xlcall.h ] || ln -sf $(XLL_DIR)/xll/XLCALL.H shim/xlcall.h

clean:
	rm -f *.o $(NAME).xll $(NAME)_test
	rm -rf xll_test_tmp
