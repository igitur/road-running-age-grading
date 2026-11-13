// xll_age_grading.cpp — the Excel add-in proper.
//
// This is the only file that knows about Excel. It converts XLOPER12 arguments
// into ag::Value (plain cells), calls the portable API in ag_api.h, and converts
// the result back into an FPX so Excel 365 spills it as a dynamic array.
//
// Everything that could be wrong is decided in the portable layer, which the
// native test suite exercises (xll/test). What is left here is mechanical
// marshalling; it cannot be run without Excel, so it is kept small and boring.
//
// Naming: the library strips the leading '_' from the procedure name, so
// "_xll_ag_grade" is resolved by Excel as the exported symbol "xll_ag_grade",
// which xll_age_grading.def must export.
#include <xll/xll.h>

#include <limits>
#include <mutex>
#include <string>
#include <vector>

#include "ag_api.h"

using namespace xll;

namespace {

// ---------------------------------------------------------------------------
// one-time setup: where to look for extra table CSVs
// ---------------------------------------------------------------------------
std::string module_directory() {
    HMODULE hmod = nullptr;
    if (!GetModuleHandleExW(
            GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS |
                GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
            reinterpret_cast<LPCWSTR>(&module_directory), &hmod)) {
        return {};
    }
    wchar_t path[MAX_PATH] = {0};
    const DWORD n = GetModuleFileNameW(hmod, path, MAX_PATH);
    if (n == 0 || n >= MAX_PATH) return {};
    std::wstring ws(path, n);
    const std::size_t slash = ws.find_last_of(L"\\/");
    if (slash == std::wstring::npos) return {};
    return utf8::wcstostring(ws.substr(0, slash).c_str());
}

void ensure_init() {
    static std::once_flag once;
    std::call_once(once, [] {
        std::vector<std::string> dirs;
        const std::string here = module_directory();
        if (!here.empty()) {
            dirs.push_back(here);                      // next to the .xll
            dirs.push_back(here + "\\tables");         // a tables subfolder
        }
        // %APPDATA%\aggrade\tables — survives replacing the .xll
        wchar_t buf[MAX_PATH] = {0};
        const DWORD n = GetEnvironmentVariableW(L"APPDATA", buf, MAX_PATH);
        if (n > 0 && n < MAX_PATH) {
            const std::string appdata = utf8::wcstostring(buf);
            dirs.push_back(appdata + "\\aggrade");
            dirs.push_back(appdata + "\\aggrade\\tables");
        }
        ag::init(dirs);
    });
}

// ---------------------------------------------------------------------------
// XLOPER12 -> ag::Cell / ag::Value
// ---------------------------------------------------------------------------
ag::Cell cell_of(const XLOPER12& x) {
    ag::Cell c;
    const WORD t = static_cast<WORD>(x.xltype & ~(xlbitXLFree | xlbitDLLFree));
    switch (t) {
        case xltypeNum: {
            c.kind = ag::Cell::Kind::Num;
            c.num = x.val.num;
            break;
        }
        case xltypeStr: {
            c.kind = ag::Cell::Kind::Text;
            // XLOPER12 strings are length-prefixed wide characters
            c.text = utf8::wcstostring(x.val.str + 1, static_cast<int>(x.val.str[0]));
            break;
        }
        case xltypeBool: {
            c.kind = ag::Cell::Kind::Bool;
            c.num = x.val.xbool ? 1.0 : 0.0;
            break;
        }
        case xltypeErr: {
            c.kind = ag::Cell::Kind::Err;
            c.err = static_cast<int>(x.val.err);
            break;
        }
        default: {
            c.kind = ag::Cell::Kind::Blank;   // missing, nil, reference, ...
            break;
        }
    }
    return c;
}

ag::Value to_value(const OPER* p) {
    if (p == nullptr) return ag::Value::of_cell(ag::Cell{});
    if (p->is_multi()) {
        const std::size_t rows = p->rows();
        const std::size_t cols = p->columns();
        ag::Matrix m(rows, cols);
        for (std::size_t i = 0; i < rows; ++i) {
            for (std::size_t j = 0; j < cols; ++j) {
                m.at(i, j) = cell_of(p->val.array.lparray[i * cols + j]);
            }
        }
        return ag::Value::of_matrix(std::move(m));
    }
    return ag::Value::of_cell(cell_of(*p));
}

// ---------------------------------------------------------------------------
// ag::Out -> FPX (dynamic array; Excel 365 spills it)
// ---------------------------------------------------------------------------
_FP12* to_fpx(const ag::Out& o) {
    thread_local FPX out;
    if (o.is_text) {                       // text results come back as "P"
        out.resize(1, 1);
        out[0] = std::numeric_limits<double>::quiet_NaN();
        return out.get();
    }
    out.resize(static_cast<int>(o.rows), static_cast<int>(o.cols));
    for (std::size_t i = 0; i < o.rows; ++i) {
        for (std::size_t j = 0; j < o.cols; ++j) {
            out(static_cast<int>(i), static_cast<int>(j)) = o.v[i * o.cols + j];
        }
    }
    return out.get();
}

// Text results (diagnostics only) reuse one buffer; Excel copies the value out
// of the returned XLOPER and does not take ownership unless xlbitDLLFree is set,
// which we deliberately do not set.
LPOPER text_result(const std::string& s) {
    static OPER buffer;
    buffer = OPER(s.c_str());
    return &buffer;
}

// ---------------------------------------------------------------------------
// argument descriptions, shared by all the grading entry points
// ---------------------------------------------------------------------------
Arg arg_sex() {
    return Arg(XLL_LPOPER, "sex", "M or F (also Male/Female, Men/Women, 1/0). "
                                  "A single cell or a column of the same length "
                                  "as the other arguments.");
}
Arg arg_age() {
    return Arg(XLL_LPOPER, "age", "Age on race day in years, 1-120. A column of "
                                  "ages for a whole squad, or one cell to apply "
                                  "to every row.");
}
Arg arg_distance() {
    return Arg(XLL_LPOPER, "distance",
               "Distance in km (10) or an event name (\"10k\", \"10kmRoad\", "
               "\"half\", \"marathon\", \"5 Mile\"). A column, or one cell.");
}
Arg arg_time() {
    return Arg(XLL_LPOPER, "time", "The performance: an Excel time value "
                                   "(0:40:00), the text \"40:00\", or seconds "
                                   "(2400). A column, or one cell.");
}
Arg arg_table() {
    return Arg(XLL_LPOPER, "table",
               "Optional. A table name (2025, 2020, 2015, 2010, latest, or a "
               "<name>.csv you dropped in the add-in folder), or a range "
               "holding a custom table. Default: the newest edition.",
               "\"2025\"");
}

const char* kCategory = "Age grading";

}  // namespace

// ===========================================================================
// AG.GRADE — the age-grade percentage
// ===========================================================================
static AddIn xai_ag_grade(
    Function(XLL_FPX, "_xll_ag_grade", "AG.GRADE")
        .Arguments({arg_sex(), arg_age(), arg_distance(), arg_time(), arg_table()})
        .FunctionHelp(
            "Age grade: the performance as a percentage of the world-standard "
            "mark for that exact sex and age (2025 USATF MLDR road tables). "
            "100 = as good as the age standard; above 100 is a genuine outlier. "
            "Pass whole columns to grade a squad in one formula.")
        .Category(kCategory));
extern "C" _FP12* WINAPI xll_ag_grade(const OPER* sex, const OPER* age,
                                      const OPER* distance, const OPER* time,
                                      const OPER* table) {
#pragma XLLEXPORT
    ensure_init();
    try {
        return to_fpx(ag::grade(to_value(sex), to_value(age), to_value(distance),
                                to_value(time), to_value(table)));
    } catch (...) {
        return to_fpx(ag::Out::scalar(std::numeric_limits<double>::quiet_NaN()));
    }
}

// ===========================================================================
// AG.GRADEDTIME
// ===========================================================================
static AddIn xai_ag_gradedtime(
    Function(XLL_FPX, "_xll_ag_gradedtime", "AG.GRADEDTIME")
        .Arguments({arg_sex(), arg_age(), arg_distance(), arg_time(), arg_table()})
        .FunctionHelp(
            "Age-graded time: the performance converted to open-class age "
            "(time x factor). Returned as an Excel time value, so format the "
            "column as [h]:mm:ss to see it; multiply by 86400 for seconds.")
        .Category(kCategory));
extern "C" _FP12* WINAPI xll_ag_gradedtime(const OPER* sex, const OPER* age,
                                           const OPER* distance, const OPER* time,
                                           const OPER* table) {
#pragma XLLEXPORT
    ensure_init();
    try {
        return to_fpx(ag::graded_time(to_value(sex), to_value(age),
                                      to_value(distance), to_value(time),
                                      to_value(table)));
    } catch (...) {
        return to_fpx(ag::Out::scalar(std::numeric_limits<double>::quiet_NaN()));
    }
}

// ===========================================================================
// AG.FACTOR
// ===========================================================================
static AddIn xai_ag_factor(
    Function(XLL_FPX, "_xll_ag_factor", "AG.FACTOR")
        .Arguments({arg_sex(), arg_age(), arg_distance(), arg_table()})
        .FunctionHelp(
            "The age factor itself (0 < factor <= 1): the multiplier the tables "
            "apply to a time at that age and distance.")
        .Category(kCategory));
extern "C" _FP12* WINAPI xll_ag_factor(const OPER* sex, const OPER* age,
                                       const OPER* distance, const OPER* table) {
#pragma XLLEXPORT
    ensure_init();
    try {
        return to_fpx(ag::factor_of(to_value(sex), to_value(age),
                                    to_value(distance), to_value(table)));
    } catch (...) {
        return to_fpx(ag::Out::scalar(std::numeric_limits<double>::quiet_NaN()));
    }
}

// ===========================================================================
// AG.STANDARD
// ===========================================================================
static AddIn xai_ag_standard(
    Function(XLL_FPX, "_xll_ag_standard", "AG.STANDARD")
        .Arguments({arg_sex(), arg_age(), arg_distance(), arg_table()})
        .FunctionHelp(
            "The open standard for the distance (the world-class mark with no "
            "age adjustment), as an Excel time value.")
        .Category(kCategory));
extern "C" _FP12* WINAPI xll_ag_standard(const OPER* sex, const OPER* age,
                                         const OPER* distance, const OPER* table) {
#pragma XLLEXPORT
    ensure_init();
    try {
        return to_fpx(ag::standard_of(to_value(sex), to_value(age),
                                      to_value(distance), to_value(table)));
    } catch (...) {
        return to_fpx(ag::Out::scalar(std::numeric_limits<double>::quiet_NaN()));
    }
}

// ===========================================================================
// AG.TIMEFORPCT — the calculator's "Result" button
// ===========================================================================
static AddIn xai_ag_timeforpct(
    Function(XLL_FPX, "_xll_ag_timeforpct", "AG.TIMEFORPCT")
        .Arguments({arg_sex(), arg_age(), arg_distance(),
                    Arg(XLL_LPOPER, "percent",
                        "The age grade you want to hit, e.g. 75 for 75%."),
                    arg_table()})
        .FunctionHelp(
            "Inverse grading: the time that would score the given age grade at "
            "that age and distance. Returned as an Excel time value.")
        .Category(kCategory));
extern "C" _FP12* WINAPI xll_ag_timeforpct(const OPER* sex, const OPER* age,
                                           const OPER* distance,
                                           const OPER* percent, const OPER* table) {
#pragma XLLEXPORT
    ensure_init();
    try {
        return to_fpx(ag::time_for_pct(to_value(sex), to_value(age),
                                       to_value(distance), to_value(percent),
                                       to_value(table)));
    } catch (...) {
        return to_fpx(ag::Out::scalar(std::numeric_limits<double>::quiet_NaN()));
    }
}

// ===========================================================================
// AG.BLOCK — everything in one spill: n x 5
// ===========================================================================
static AddIn xai_ag_block(
    Function(XLL_FPX, "_xll_ag_block", "AG.BLOCK")
        .Arguments({arg_sex(), arg_age(), arg_distance(), arg_time(), arg_table()})
        .FunctionHelp(
            "Grade a whole squad and spill five columns at once: factor, open "
            "standard, age standard, age-graded time (all Excel time values), "
            "then the age grade percentage. Put the five headers in the row "
            "above before entering it.")
        .Category(kCategory));
extern "C" _FP12* WINAPI xll_ag_block(const OPER* sex, const OPER* age,
                                      const OPER* distance, const OPER* time,
                                      const OPER* table) {
#pragma XLLEXPORT
    ensure_init();
    try {
        return to_fpx(ag::block(to_value(sex), to_value(age), to_value(distance),
                                to_value(time), to_value(table)));
    } catch (...) {
        return to_fpx(ag::Out::scalar(std::numeric_limits<double>::quiet_NaN()));
    }
}

// ===========================================================================
// diagnostics
// ===========================================================================
static AddIn xai_ag_tables(
    Function(XLL_FPX, "_xll_ag_tables", "AG.TABLES")
        .Arguments({})
        .FunctionHelp("List the edition years this add-in can grade with, newest "
                      "first. Use one as the fifth argument to AG.GRADE.")
        .Category(kCategory));
extern "C" _FP12* WINAPI xll_ag_tables(void) {
#pragma XLLEXPORT
    ensure_init();
    return to_fpx(ag::tables());
}

static AddIn xai_ag_tableinfo(
    Function(XLL_FPX, "_xll_ag_tableinfo", "AG.TABLEINFO")
        .Arguments({arg_table()})
        .FunctionHelp(
            "Describe a table: year, number of distances, number of ages, and "
            "how many sexes it carries.")
        .Category(kCategory));
extern "C" _FP12* WINAPI xll_ag_tableinfo(const OPER* table) {
#pragma XLLEXPORT
    ensure_init();
    return to_fpx(ag::table_info(to_value(table)));
}

static AddIn xai_ag_cacheinfo(
    Function(XLL_FPX, "_xll_ag_cacheinfo", "AG.CACHEINFO")
        .Arguments({})
        .FunctionHelp(
            "Cache counters: built-in editions, loaded CSV tables, custom ranges "
            "held, cache hits, cache misses, maximum custom ranges held.")
        .Category(kCategory));
extern "C" _FP12* WINAPI xll_ag_cacheinfo(void) {
#pragma XLLEXPORT
    ensure_init();
    return to_fpx(ag::cache_info());
}

static AddIn xai_ag_cacheclear(
    Function(XLL_FPX, "_xll_ag_cacheclear", "AG.CACHECLEAR")
        .Arguments({})
        .FunctionHelp("Drop cached CSV and custom-range tables, then return 1. "
                      "Use it after editing a table CSV.")
        .Category(kCategory));
extern "C" _FP12* WINAPI xll_ag_cacheclear(void) {
#pragma XLLEXPORT
    ensure_init();
    return to_fpx(ag::cache_clear());
}

static AddIn xai_ag_lasterror(
    Function(XLL_LPOPER, "_xll_ag_lasterror", "AG.LASTERROR")
        .Arguments({})
        .FunctionHelp(
            "Why the last age-grading call failed. A column of #NUM! values is "
            "much easier to diagnose with this in the next cell.")
        .Category(kCategory));
extern "C" LPOPER WINAPI xll_ag_lasterror(void) {
#pragma XLLEXPORT
    ensure_init();
    return text_result(ag::last_error().empty() ? "no error" : ag::last_error());
}

static AddIn xai_ag_version(
    Function(XLL_LPOPER, "_xll_ag_version", "AG.VERSION")
        .Arguments({})
        .FunctionHelp("Add-in version and the number of built-in editions.")
        .Category(kCategory));
extern "C" LPOPER WINAPI xll_ag_version(void) {
#pragma XLLEXPORT
    ensure_init();
    return text_result(ag::version_string());
}

// Report the Excel C API version (12 = Excel 2007 and later).
extern "C" int WINAPI XLCallVer(void) { return 0x0c00; }
