# What had to be patched in the xll framework

The [xll](https://github.com/xlladdins/xll) library is the practical way to build
a native Excel add-in without owning Visual Studio, but **it is MSVC-only as
published**. Seven files need changing before GCC will build them — three rely on
preprocessor extensions that standard C++ forbids (`##` pasting that does not
form a token), one calls a libstdc++ `initializer_list` constructor that is
private, two are places where MSVC is laxer than the standard (a repeated
typedef, a shadowed template parameter), and one is missing two includes MSVC
gets transitively — and one source file relies on pragma-based exports that mingw
ignores altogether. A further five shims live outside the library.

Everything below is mechanical and remains valid C++ for MSVC, so the patch can
be carried indefinitely. The complete change is
[`../patches/xll-mingw-portability.patch`](../patches/xll-mingw-portability.patch):
**7 files, 46 lines, 8 distinct fixes.**

| # | File | Class | What GCC says without the fix |
| --- | --- | --- | --- |
| 1 | `xll/traits.h:17,75` | compile | `pasting "." and "num" does not give a valid preprocessing token` |
| 2 | `xll/xloper.h:320` | compile | `pasting "operator" and "==" does not give a valid preprocessing token` |
| 3 | `xll/sref.h:24` | compile | (same class; surfaced next) |
| 4 | `xll/oper.h:38` | compile | `redeclaration of 'typedef typename xll::traits<X>::xint xll::XOPER<X>::xint'` |
| 5 | `xll/handle.h:76,82,88` | compile | `declaration of template parameter 'T' shadows template parameter` |
| 6 | `xll/xloper.h:258` | compile | `'int64_t' does not name a type` |
| 7 | `xll/args.h:116` | compile | `initializer_list(const_iterator, size_type) is private within this context` |
| 8 | `xll/error.cpp:87,102` | **export**, not compile | compiles fine; the add-in then refuses to load in Excel |

Plus, outside the library: three header symlinks, four `-D` defines, one file
compiled as C, one compatibility source file, one project-side `.def`, and two
symbols the project must define itself. Those are in
[the second half of this page](#not-patches-build-level-shims).

---

## How this was established

Not by reading the code and guessing. The method was: clone upstream, compile
this add-in's glue against it, fix **one** thing, recompile, record the next
error — so the error text quoted for each patch is the error that patch removes,
in the order GCC actually reports them.

```console
$ git clone --depth 1 https://github.com/xlladdins/xll /tmp/xll-pristine
$ cd age-grading/xll
$ x86_64-w64-mingw32-g++ -std=c++20 -D_M_X64 -DXLL_VERSION=12 \
    -DUNICODE -D_UNICODE -Dpascal=__stdcall -D_cdecl=__cdecl \
    -I shim -I /tmp/xll-pristine -I src \
    -c src/road_running_age_grading.cpp -o /dev/null
```

The transcript, patches applied cumulatively (nothing else changed):

```
step 0  pristine library
        pasting "." and "num" does not give a valid preprocessing token
        pasting "." and "xbool" does not give a valid preprocessing token
step 1  after traits.h (no ## token pasting)
        pasting "operator" and "==" does not give a valid preprocessing token
step 2  after xloper.h (no ## in XLOPER_CMP)
        pasting "operator" and "==" does not give a valid preprocessing token
step 3  after sref.h (no ## in REF_CTW)
        'int64_t' does not name a type
        'union operator<=><xloper>(...)::id' has no member named 'i'
step 4  after oper.h (duplicate xint typedef removed)
        'int64_t' does not name a type
step 5  after handle.h (shadowed template parameter renamed)
        'int64_t' does not name a type
step 6  after xloper.h (cstdint, limits included)
        'constexpr std::initializer_list<_E>::initializer_list(const_iterator,
            size_type)' is private within this context
step 7  after args.h (no initializer_list pointer-pair ctor)
        compiles clean
```

Steps 2 and 4–5 show no *new* error because patches 2, 4 and 5 each remove a
blocker that GCC had not reached yet — the preceding error aborted the
translation unit first. Their reality was confirmed separately by reverting each
one against the otherwise-patched tree:

```console
$ git checkout -- xll/oper.h        # then compile
  oper.h:38: error: redeclaration of 'typedef ... xint xll::XOPER<X>::xint'
$ git checkout -- xll/handle.h      # then compile
  handle.h:76: error: declaration of template parameter 'T' shadows template parameter
  handle.h:82: error: declaration of template parameter 'T' shadows template parameter
  handle.h:88: error: declaration of template parameter 'T' shadows template parameter
```

Upstream state the patch was made against: commit `481178b` ("trim cusip",
2023-11-27), which is still `HEAD` of `xlladdins/xll` master.

---

## The patches, one by one

### 1. `traits.h` — `##` token pasting that MSVC allows

```diff
-#define XLL_TYPE_TRAITS(a,b,c,d,e) typedef decltype(XLOPER::val.##b) x##c;
+#define XLL_TYPE_TRAITS(a,b,c,d,e) typedef decltype(XLOPER::val.b) x##c;
...
-#define XLL_TYPE_TRAITS(a,b,c,d,e) typedef decltype(XLOPER12::val. ## b) x##c;
+#define XLL_TYPE_TRAITS(a,b,c,d,e) typedef decltype(XLOPER12::val.b) x##c;
```

This macro builds the member typedefs (`xnum`, `xstr`, `xbool`, …) from the type
table in `defines.h`, so it is instantiated dozens of times; without the fix the
compiler emits one error per member. MSVC's preprocessor accepts a `##`
result that is not a single preprocessing token (`.` + identifier); the standard
does not, and GCC refuses. Since `b` is already pasted against a literal `.`, the
`##` is simply deleted — the grep-visible text and the resulting token are the
same on both compilers.

Same file, cosmetic: a commented-out `//typedef INT32 xint;` line is deleted.

### 2 and 3. `xloper.h:320` and `sref.h:24` — the same trick around `operator`

```diff
-#define XLOPER_CMP(op) \
-	inline bool operator##op(const XLOPER& x, const XLOPER& y) { ... }
+#define XLOPER_CMP(op) \
+	inline bool operator op(const XLOPER& x, const XLOPER& y) { ... }
```

and the identical construct in `REF_CTW(op)` in `sref.h`. `operator ## ==` asks
the preprocessor to paste `operator` and `==` into one token, which does not
exist; GCC is right to complain. `operator op` (with a space) is a valid
declaration and expands identically.

### 4. `oper.h:38` — a duplicated member typedef

```diff
 	typedef typename traits<X>::xint xint;
 	typedef typename traits<X>::xrw xrw;
 	typedef typename traits<X>::xcol xcol;
-	typedef typename traits<X>::xint xint;
 	typedef typename traits<X>::xref xref;
```

MSVC tolerates the repeat; GCC reports a redeclaration. Do **not** try to fix it
by hand-writing `xint` into `traits<XLOPER>`: it is generated from the
`XLL_TYPE_SCALAR` table (`X(Int, w, int, …)` → `decltype(val.w)`), which is
`short` for `XLOPER` and `int` for `XLOPER12`.

### 5. `handle.h:76,82,88` — a shadowed template parameter

```diff
-		template<class T>
-		bool operator()(const std::unique_ptr<T>& a, const T* b) const
+		template<class U>
+		bool operator()(const std::unique_ptr<U>& a, const U* b) const
```

`unique_ptrcmp`'s outer class is `template<class T>`; the member templates
redeclare `T`, which GCC rejects outright. Renaming the inner parameter to `U`
changes nothing semantically.

### 6. `xloper.h` — `<cstdint>`, and `<limits>` for safety

```diff
 #pragma once
+#include <cstdint>
 #include <compare>
 #include <concepts>
+#include <limits>
```

`xloper.h:258` declares `int64_t i;` inside the `<=>` comparator's union; MSVC
reaches `<cstdint>` transitively through `windows.h`, mingw does not, so
`int64_t` is undeclared and the union member errors cascade
(`'union operator<=><xloper>(…)::id' has no member named 'i'`).

`<limits>` is precautionary: `handle.h` and `oper.h` use `std::numeric_limits`,
and reverting only that include still compiles this add-in
(`0` errors), so it is added to stop the next TU from finding the gap.

### 7. `args.h:116` — `std::initializer_list` built from a pointer pair

```diff
 Args& Arguments(const std::vector<Arg>& args)
 {
-	return Arguments(std::initializer_list<Arg>(&args[0], &args[0] + args.size()));
+	const char* comma = "";
+	for (const auto& arg : args) {
+		key("typeText") &= arg.type;
+		key("argumentType").push_back(OPER(arg.type));
+		key("argumentName").push_back(OPER(arg.name));
+		key("argumentHelp").push_back(OPER(arg.help));
+		key("argumentDefault").push_back(OPER(arg.init));
+		key("argumentText") &= comma;
+		key("argumentText") &= arg.name;
+		comma = ", ";
+	}
+	return *this;
 }
```

The two-iterator `initializer_list` constructor is **private** in libstdc++;
MSVC exposes it. The replacement is not a rewrite — it is the body of the
`Arguments(const std::initializer_list<Arg>&)` overload nine lines above, which
is why the function signatures and the Function Wizard text come out unchanged.
This is the one patch where a mistake would be subtle rather than loud (a missing
`argumentDefault` would silently break optional arguments), so it is worth
eyeballing against the sibling overload in the patch.

### 8. `error.cpp` — compiles fine, then stops the add-in from loading

```diff
-	Function(XLL_WORD, "xll_alert_level_", "XLL.ALERT.LEVEL")
+	Function(XLL_WORD, "_xll_alert_level_", "XLL.ALERT.LEVEL")
...
-DWORD WINAPI xll_alert_level_(LPOPER plevel)
+extern "C" DWORD WINAPI xll_alert_level_(LPOPER plevel)
```

Two separate problems, neither of them visible to the compiler:

1. The function has no `extern "C"`, so its symbol is C++-mangled. On MSVC that
   is handled by the linker pragmas in `exports.h`; mingw ignores
   `#pragma comment(linker, "/export:…")` entirely, so nothing is exported under
   the name Excel will look up.
2. The procedure name needs the leading `_` that the library's `Register()`
   strips, so that what Excel receives (`xll_alert_level_`) matches a symbol that
   can actually be exported from a `.def` file.

Why this is fatal rather than cosmetic — from the library's own `auto.cpp`:

```cpp
for (auto& [key, arg] : AddIn::Map) {
    ensure(Register(arg));        // throws if xlfRegister fails
}
...
catch (const std::exception& ex) { XLL_ERROR(ex.what()); return FALSE; }
```

`xlAutoOpen` returns **FALSE** if any single registration fails, and Excel then
refuses to load the add-in. The framework registers its own `XLL.ALERT.LEVEL`
diagnostic function from `error.cpp`, so an unexported `xll_alert_level_` is not
a missing extra — it is a dead add-in, with no error visible to the user beyond
"the add-in could not be loaded".

**The patch alone is not sufficient.** `extern "C"` makes the symbol
exportable; it does not export it. The project must name it in its `.def`:

```
    xll_alert_level_
```

`make verify` now checks this class of mistake: it parses `road_running_age_grading.def`
and fails if any listed symbol is absent from the built PE export table — a check
that did not exist when the first build of this add-in was made, and that build
was missing exactly this symbol. Had that binary reached Excel it would have
loaded nothing at all.

Contrast with the constants in the same file: `XLL_CONST` declares its functions
`extern "C" __declspec(dllexport)`, and **mingw honours `__declspec(dllexport)`**
— that is why `xll_XLL_ALERT_ERROR`, `xll_XLL_ALERT_INFO` and
`xll_XLL_ALERT_WARNING` need no `.def` entry. Only `xll_alert_level_`, which
relies on `#pragma XLLEXPORT`, does.

---

## Not patches: build-level shims

These are as necessary as the source patches and, being outside the library,
cannot live in the patch file. All are in `xll/Makefile`.

### Case-sensitive includes (Linux filesystems only)

The library includes `<Windows.h>`, `<WinBase.h>`, `"Shlwapi.h"` and
`"xlcall.h"`; mingw ships `windows.h`, `winbase.h`, `shlwapi.h` and the vendored
file is `XLCALL.H`. Without a shim:

```
xll/utf8.h:11:10: fatal error: Windows.h: No such file or directory
```

`make shim` creates four symlinks in `shim/`, which must come **first** in the
include path. On Windows this is unnecessary (case-insensitive filesystem) and
MSVC needs none of it.

### MSVC-only macros as command-line defines

| Define | Without it |
| --- | --- |
| `-D_M_X64` | `defines.h` takes the 32-bit `_name@n` decoration branch on an x64 build |
| `-DUNICODE -D_UNICODE` | `splitpath.h` includes `<tchar.h>` before `defines.h` sets `_UNICODE`; the include guards then freeze `TCHAR` as narrow *for the whole TU*, surfacing as nonsense `basic_string<char>::append(wchar_t*)` errors |
| `-Dpascal=__stdcall` | `XLCALL.H` prototypes do not compile |
| `-D_cdecl=__cdecl` | same, for C++ TUs only (GCC defines `_cdecl` builtin in C mode) |
| `-Wno-unknown-pragmas` | noise from `#pragma region` and `#pragma comment(linker,…)` |

### `defines.c` must be compiled as C

It uses C99 designated initialisers (`[xlerrNull] = …`), which g++ rejects. The
`gcc` driver is used for that one file; the g++ driver would treat `.c` as C++.

### `excel4_compat.cpp` — the pre-2007 API

`xll/XLCALL.CPP` implements only `Excel12`/`Excel12v`. `Excel4v` is referenced by
`traits<XLOPER>::Excelv`, which gets instantiated through `XOPER<XLOPER>` even in
an Excel-12 add-in, and on MSVC it is satisfied by the vendored `XLCALL32.LIB` —
an MSVC-format import library mingw cannot link. `excel4_compat.cpp` (217 lines)
implements `Excel4`/`Excel4v` by converting to and from `XLOPER12` and calling
`Excel12v`, following the canonical Microsoft SDK conversion. It is the only
piece of the build that reimplements library behaviour rather than making it
compile.

### Two symbols the project must supply

- `XLCallVer()` — declared and called by the library, defined by nobody. The
  add-in returns `0x0c00`.
- Exports via `.def` instead of `#pragma comment(linker, "/export:…")`, which
  mingw ignores. Hence `road_running_age_grading.def` and the leading `_` in every
  procedure name (`"_xll_rrag_grade"` → Excel resolves `xll_rrag_grade`).

---

## Reproducing all of it

```console
$ ./tools/apply-xll-patches.sh          # clones upstream if needed, applies, idempotent
$ make clean && make verify             # builds the .xll and audits .def vs exports
```

Verified concretely:

| Check | Result |
| --- | --- |
| `git apply` onto a fresh `--depth 1` clone of upstream `481178b` | applies cleanly, all 7 files |
| patched clone vs the tree this repo builds against | **byte-identical** (`diff -r`: no output) |
| `make xll XLL_DIR=<fresh clone>` | builds; `.xll` identical size (1 336 832 bytes) |
| `make verify` on that build | all `.def` symbols exported; imports only KERNEL32/USER32/ADVAPI32/SHLWAPI/msvcrt |
| re-running the script on a patched tree | `already patched`, no change |

If upstream ever moves, `git apply --check` fails loudly and the script says so
rather than half-patching a tree:

```
cannot apply .../xll-mingw-portability.patch to ~/code/xll
upstream may have changed; regenerate the patch against the new HEAD
```

## Maintenance notes

- The patches are all syntax-level or defensive: none changes behaviour, and all
  remain valid MSVC C++. A fork carrying them builds on both toolchains.
- The `error.cpp` hunk is the one to keep even if it looks pointless: without it
  the add-in silently fails to load. Any future removal must keep
  `xll_alert_level_` exported.
- `tools/apply-xll-patches.sh`, the `shim` target and the `.def`-completeness
  check in `make verify` exist so this page has no unstated manual steps.
- What remains unverified: the add-in actually loading in Excel. Everything above
  is static evidence — compiler diagnostics, a patched-tree diff, a PE export
  audit — because there is no Excel on this machine. The `xlAutoOpen`-returns-
  FALSE finding is a good argument for testing the load on a Windows box before
  trusting any of it.
