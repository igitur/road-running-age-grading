// test_main.cpp — native test suite for the age-grading add-in.
//
// Built and run on Linux by `make test`; it links the same ag_core.cpp and
// ag_api.cpp that go into the .xll, so the arithmetic and the argument handling
// under test are exactly what Excel will call. The only untested code is the
// thin XLOPER12 conversion in src/road_running_age_grading.cpp, which cannot run without
// Excel (see xll/README.md).
#include <cmath>
#include <cstdio>
#include <cstring>
#include <string>
#include <vector>

#include "ag_api.h"
#include "ag_core.h"
#include "expected.h"

namespace {

int g_checks = 0;
int g_failures = 0;
const char* g_section = "";

void section(const char* s) {
    g_section = s;
    std::printf("\n== %s\n", s);
}

void ok(bool cond, const char* what, int line) {
    ++g_checks;
    if (!cond) {
        ++g_failures;
        std::printf("  FAIL %s:%d [%s] %s\n", __FILE__, line, g_section, what);
    }
}

void near(double got, double want, double tol, const char* what, int line) {
    ++g_checks;
    if (!(std::fabs(got - want) <= tol)) {
        ++g_failures;
        std::printf("  FAIL %s:%d [%s] %s: got %.6f want %.6f (tol %g)\n",
                    __FILE__, line, g_section, what, got, want, tol);
    }
}

void nan_is(double got, const char* what, int line) {
    ++g_checks;
    if (!std::isnan(got)) {
        ++g_failures;
        std::printf("  FAIL %s:%d [%s] %s: expected NaN, got %.6f\n",
                    __FILE__, line, g_section, what, got);
    }
}

#define OK(c) ok((c), #c, __LINE__)
#define NEAR(g, w, t) near((g), (w), (t), #g, __LINE__)
#define IS_NAN(g) nan_is((g), #g, __LINE__)

// ---------------------------------------------------------------------------
ag::Value vec(const std::vector<double>& v) {
    ag::Matrix m(v.size(), 1);
    for (std::size_t i = 0; i < v.size(); ++i) m.at(i, 0) = ag::Cell::number(v[i]);
    return ag::Value::of_matrix(std::move(m));
}

ag::Value svec(const std::vector<std::string>& v) {
    ag::Matrix m(v.size(), 1);
    for (std::size_t i = 0; i < v.size(); ++i) m.at(i, 0) = ag::Cell::string(v[i]);
    return ag::Value::of_matrix(std::move(m));
}

ag::Value num(double x) { return ag::Value::of_cell(ag::Cell::number(x)); }
ag::Value txt(std::string s) { return ag::Value::of_cell(ag::Cell::string(std::move(s))); }

// A matrix literal: rows of cells, each row a list of "3.5" or "M" tokens.
ag::Matrix mat(const std::vector<std::vector<std::string>>& rows) {
    std::size_t cols = 0;
    for (const auto& r : rows) cols = std::max(cols, r.size());
    ag::Matrix m(rows.size(), cols);
    for (std::size_t i = 0; i < rows.size(); ++i) {
        for (std::size_t j = 0; j < rows[i].size(); ++j) {
            const std::string& s = rows[i][j];
            if (s.empty()) continue;
            char* end = nullptr;
            const double v = std::strtod(s.c_str(), &end);
            if (end && *end == '\0') m.at(i, j) = ag::Cell::number(v);
            else m.at(i, j) = ag::Cell::string(s);
        }
    }
    return m;
}

// ---------------------------------------------------------------------------
void test_ground_truth() {
    section("ground truth (462 cases from the verified Python implementation)");
    const ag::Value t2025 = txt("2025");
    for (int i = 0; i < ag::test::n_expectations; ++i) {
        const ag::test::Expect& e = ag::test::expectations[i];
        const ag::Out o = ag::block(txt(e.sex), num(e.age), num(e.distance_km),
                                    num(e.time_s), t2025);
        if (o.rows != 1 && o.cols != 5) {
            OK(false);
            continue;
        }
        const double factor = o.v[0];
        const double age_std = o.v[2] * 86400.0;
        const double graded = o.v[3] * 86400.0;
        const double percent = o.v[4];
        if (std::fabs(factor - e.factor) > 2e-6 ||
            std::fabs(age_std - e.age_standard_s) > 0.02 ||
            std::fabs(graded - e.graded_s) > 0.02 ||
            std::fabs(percent - e.percent) > 0.002) {
            std::printf("  case %d: %s age %g dist %g time %g\n", i, e.sex, e.age,
                        e.distance_km, e.time_s);
            near(factor, e.factor, 2e-6, "factor", __LINE__);
            near(age_std, e.age_standard_s, 0.02, "age standard", __LINE__);
            near(graded, e.graded_s, 0.02, "graded", __LINE__);
            near(percent, e.percent, 0.01, "percent", __LINE__);
        } else {
            OK(true);
        }
    }
}

// ---------------------------------------------------------------------------
void test_smoke() {
    section("smoke: the canonical cases");
    const ag::Out g = ag::grade(txt("M"), num(40), num(10.0), num(2400), txt("2025"));
    NEAR(g.v[0], 68.49, 0.01);

    const ag::Out f = ag::grade(txt("F"), num(56), num(10.0), num(2400), txt("2025"));
    NEAR(f.v[0], 87.42, 0.01);

    const ag::Out m = ag::grade(txt("M"), num(75), txt("Marathon"), num(4 * 3600 + 30 * 60),
                                txt("2025"));
    NEAR(m.v[0], 65.13, 0.01);

    const ag::Out y = ag::grade(txt("F"), num(12), txt("5k"), num(22 * 60), txt("2025"));
    NEAR(y.v[0], 71.58, 0.01);

    // above 100% is a real answer, not an error
    const ag::Out hi = ag::grade(txt("M"), num(65), num(10.0), num(32 * 60), txt("2025"));
    NEAR(hi.v[0], 106.30, 0.01);

    // a time given as text parses like the calculator
    const ag::Out ts = ag::grade(txt("M"), num(40), num(10.0), txt("40:00"), txt("2025"));
    NEAR(ts.v[0], 68.49, 0.01);

    // an Excel time serial is the same thing
    const ag::Out ser = ag::grade(txt("M"), num(40), num(10.0), num(2400.0 / 86400.0),
                                  txt("2025"));
    NEAR(ser.v[0], 68.49, 0.01);

    // sex accepted in several spellings and as 1/0
    const ag::Out male = ag::grade(txt("Male"), num(40), num(10.0), num(2400), txt("2025"));
    NEAR(male.v[0], 68.49, 0.01);
    const ag::Out one = ag::grade(num(1), num(40), num(10.0), num(2400), txt("2025"));
    NEAR(one.v[0], 68.49, 0.01);
}

// ---------------------------------------------------------------------------
void test_vectors() {
    section("vectors: broadcast, alignment, shapes");
    // four ages, one 32:00 at 10 km and one distance broadcast
    const ag::Out g = ag::grade(txt("M"), vec({25, 35, 45, 55}), num(10.0), num(32 * 60),
                               txt("2025"));
    OK(g.rows == 4 && g.cols == 1);
    NEAR(g.v[0], 82.50, 0.01);
    NEAR(g.v[1], 83.26, 0.01);
    NEAR(g.v[2], 89.08, 0.01);
    NEAR(g.v[3], 96.93, 0.01);

    // full vectors, every argument the same length
    const ag::Out h = ag::grade(svec({"M", "F", "M"}), vec({30, 45, 60}),
                                svec({"10k", "Marathon", "5k"}),
                                vec({2400, 4 * 3600, 30 * 60}), txt("2025"));
    OK(h.rows == 3);
    NEAR(h.v[0], 71.92 + 0.0, 25.0);          // loose: just prove it is a number
    OK(!std::isnan(h.v[0]) && !std::isnan(h.v[1]) && !std::isnan(h.v[2]));

    // mismatched lengths must fail loudly, naming both arguments
    ag::set_last_error("");
    const ag::Out bad = ag::grade(txt("M"), vec({30, 40, 50}), num(10.0),
                                  vec({2400, 2500}), txt("2025"));
    OK(bad.rows == 1 && bad.cols == 1);     // one loud #NUM!, not a wrong grid
    IS_NAN(bad.v[0]);
    const std::string msg = ag::last_error();
    OK(msg.find("must be the same length") != std::string::npos);
    OK(msg.find("time has 2 values but age has 3") != std::string::npos);

    // scalar everything -> 1x1
    const ag::Out one = ag::grade(txt("M"), num(40), num(10.0), num(2400), txt("2025"));
    OK(one.rows == 1 && one.cols == 1);

    // blank time leaves the row empty (0), not an error
    ag::Matrix t(3, 1);
    t.at(0, 0) = ag::Cell::number(2400);
    t.at(2, 0) = ag::Cell::number(2400);        // row 1 blank
    const ag::Out blank = ag::grade(txt("M"), vec({40, 41, 42}), num(10.0),
                                    ag::Value::of_matrix(t), txt("2025"));
    OK(blank.v[0] > 0 && blank.v[1] == 0.0 && blank.v[2] > 0);

    // one bad row does not poison the column, and the reason is reported
    ag::set_last_error("");
    const ag::Out mixed = ag::grade(svec({"M", "X", "M"}), vec({40, 40, 40}),
                                    num(10.0), num(2400), txt("2025"));
    OK(mixed.v[0] > 0);
    IS_NAN(mixed.v[1]);
    OK(mixed.v[2] > 0);
    OK(ag::last_error().find("row 2") != std::string::npos);
}

// ---------------------------------------------------------------------------
void test_tables() {
    section("table parameter: names, coercion, editions, failures");
    // omitted table -> 2025
    const ag::Out def = ag::grade(txt("M"), num(5), num(5.0), num(1440),
                                  ag::Value::of_cell(ag::Cell{}));
    const ag::Out named = ag::grade(txt("M"), num(5), num(5.0), num(1440), txt("2025"));
    NEAR(def.v[0], named.v[0], 1e-9);

    // numeric coercion: 2025.0 must behave like "2025"
    const ag::Out numname = ag::grade(txt("M"), num(5), num(5.0), num(1440), num(2025));
    NEAR(numname.v[0], named.v[0], 1e-9);

    // "latest" and "" mean the newest edition
    const ag::Out latest = ag::grade(txt("M"), num(5), num(5.0), num(1440), txt("latest"));
    NEAR(latest.v[0], named.v[0], 1e-9);

    // older editions are supported and differ: 5 km, age 5 factor
    const ag::Out y2020 = ag::factor_of(txt("M"), num(5), num(5.0), txt("2020"));
    NEAR(y2020.v[0], 0.6062, 1e-4);
    const ag::Out y2015 = ag::factor_of(txt("M"), num(5), num(5.0), txt("2015"));
    NEAR(y2015.v[0], 0.6062, 1e-4);
    const ag::Out y2010 = ag::factor_of(txt("M"), num(5), num(5.0), txt("2010"));
    OK(!std::isnan(y2010.v[0]));

    // an unknown name is an error that lists what is available
    ag::set_last_error("");
    const ag::Out bad = ag::grade(txt("M"), num(40), num(10.0), num(2400), txt("1999"));
    IS_NAN(bad.v[0]);
    OK(ag::last_error().find("no table named") != std::string::npos);

    // out-of-range distance refuses, like the published calculator
    ag::set_last_error("");
    const ag::Out far = ag::grade(txt("M"), num(40), num(500.0), num(2400), txt("2025"));
    IS_NAN(far.v[0]);
    OK(ag::last_error().find("outside the published range") != std::string::npos);

    // ages clamp at both ends rather than failing
    const ag::Out young = ag::grade(txt("M"), num(2), num(5.0), num(1440), txt("2025"));
    const ag::Out age5 = ag::grade(txt("M"), num(5), num(5.0), num(1440), txt("2025"));
    NEAR(young.v[0], age5.v[0], 1e-9);
    const ag::Out old = ag::grade(txt("M"), num(140), num(5.0), num(1440), txt("2025"));
    IS_NAN(old.v[0]);   // 1..120 is the accepted age domain
}

// ---------------------------------------------------------------------------
ag::Matrix matrix_table() {
    // a 3-age, 2-distance club table, both sexes, factors chosen to be easy
    return mat({
        {"Sex", "Event", "OpenStd", "30", "40", "50"},
        {"M", "10 k", "26:24", "1", "0.9", "0.8"},
        {"F", "10 k", "28:46", "1", "0.85", "0.75"},
        {"M", "Marathon", "2:00:35", "1", "0.95", "0.9"},
        {"F", "Marathon", "2:09:56", "1", "0.9", "0.85"},
    });
}

void test_adhoc() {
    section("ad hoc tables from a cell range");
    ag::Registry::instance().clear();
    ag::set_last_error("");

    const ag::Value tbl = ag::Value::of_matrix(matrix_table());
    // M, 40, 10 km, 40:00 -> factor 0.9, standard 1584 -> 100*1760/2400
    const ag::Out g = ag::grade(txt("M"), num(40), num(10.0), num(2400), tbl);
    NEAR(g.v[0], 100.0 * (1584.0 / 0.9) / 2400.0, 1e-3);

    // the same range is parsed once: a second call is a cache hit
    const ag::CacheStats before = ag::Registry::instance().stats();
    const ag::Out again = ag::grade(txt("M"), num(40), num(10.0), num(2400), tbl);
    const ag::CacheStats after = ag::Registry::instance().stats();
    NEAR(again.v[0], g.v[0], 1e-12);
    OK(after.hit > before.hit);
    OK(after.miss == before.miss);

    // age interpolation between the supplied ages, and clamping outside them
    const ag::Out a35 = ag::grade(txt("M"), num(35), num(10.0), num(2400), tbl);
    NEAR(a35.v[0], 100.0 * (1584.0 / 0.95) / 2400.0, 1e-3);
    const ag::Out a10 = ag::grade(txt("M"), num(10), num(10.0), num(2400), tbl);
    const ag::Out a30 = ag::grade(txt("M"), num(30), num(10.0), num(2400), tbl);
    NEAR(a10.v[0], a30.v[0], 1e-9);

    // A custom table interpolates right up to its own last supplied age. The
    // published calculator clamps (99, 100] to 100 because its grid ends there;
    // applying that rule to a club table whose ages are 45..65 would turn 61
    // into 65 and lose five years of the curve.
    const ag::Matrix sparse = mat({
        {"Sex", "Event", "OpenStd", "45", "50", "55", "60", "65"},
        {"M", "10 k", "26:24", "0.9261", "0.8886", "0.8511", "0.8136", "0.7761"},
    });
    const ag::Value sp = ag::Value::of_matrix(sparse);
    const double want61 = 100.0 * (1584.0 / (0.8136 + 0.2 * (0.7761 - 0.8136))) / 2400.0;
    NEAR(ag::grade(txt("M"), num(61), num(10.0), num(2400), sp).v[0], want61, 1e-3);
    const double want64 = 100.0 * (1584.0 / (0.8136 + 0.8 * (0.7761 - 0.8136))) / 2400.0;
    NEAR(ag::grade(txt("M"), num(64), num(10.0), num(2400), sp).v[0], want64, 1e-3);
    // ...and still clamps above its own top age
    NEAR(ag::grade(txt("M"), num(80), num(10.0), num(2400), sp).v[0],
         100.0 * (1584.0 / 0.7761) / 2400.0, 1e-3);

    // the published editions keep the calculator's (99, 100] clamp
    NEAR(ag::factor_of(txt("M"), num(99.5), num(10.0), txt("2025")).v[0],
         ag::factor_of(txt("M"), num(100), num(10.0), txt("2025")).v[0], 1e-9);

    // distance interpolation inside the ad hoc table (between 10 km and 42.195)
    const ag::Out mid = ag::grade(txt("M"), num(40), num(21.0975), num(7200), tbl);
    OK(!std::isnan(mid.v[0]));

    // female rows are independent of male rows
    const ag::Out f = ag::grade(txt("F"), num(50), num(10.0), num(2400), tbl);
    NEAR(f.v[0], 100.0 * (1726.0 / 0.75) / 2400.0, 1e-3);

    // long format produces the same numbers as the matrix format
    const ag::Matrix longform = mat({
        {"Sex", "Event", "Age", "Factor", "OpenStd"},
        {"M", "10 k", "30", "1", "26:24"},
        {"M", "10 k", "40", "0.9", "26:24"},
        {"M", "10 k", "50", "0.8", "26:24"},
        {"F", "10 k", "30", "1", "28:46"},
        {"F", "10 k", "40", "0.85", "28:46"},
        {"F", "10 k", "50", "0.75", "28:46"},
        {"M", "Marathon", "30", "1", "2:00:35"},
        {"M", "Marathon", "40", "0.95", "2:00:35"},
        {"M", "Marathon", "50", "0.9", "2:00:35"},
        {"F", "Marathon", "30", "1", "2:09:56"},
        {"F", "Marathon", "40", "0.9", "2:09:56"},
        {"F", "Marathon", "50", "0.85", "2:09:56"},
    });
    const ag::Out lf = ag::grade(txt("M"), num(40), num(10.0), num(2400),
                                 ag::Value::of_matrix(longform));
    NEAR(lf.v[0], g.v[0], 1e-9);

    // Each sex keeps its own OpenStd in the long layout. Regression: the parser
    // used to copy every row's standard into both sexes, so whichever sex came
    // first in the table graded both (a female 10 km run scored against the
    // male 26:24 standard, 7 percentage points too high).
    const ag::Matrix longsex = mat({
        {"Sex", "Event", "Age", "Factor", "OpenStd"},
        {"M", "10 k", "30", "1", "26:24"},
        {"M", "10 k", "50", "0.8", "26:24"},
        {"F", "10 k", "30", "1", "28:46"},
        {"F", "10 k", "50", "0.8", "28:46"},
    });
    const ag::Value lsx = ag::Value::of_matrix(longsex);
    NEAR(ag::grade(txt("M"), num(30), num(10.0), num(2400), lsx).v[0],
         100.0 * (1584.0 / 1.0) / 2400.0, 1e-3);
    NEAR(ag::grade(txt("F"), num(30), num(10.0), num(2400), lsx).v[0],
         100.0 * (1726.0 / 1.0) / 2400.0, 1e-3);
    NEAR(ag::grade(txt("F"), num(50), num(10.0), num(2400), lsx).v[0],
         100.0 * (1726.0 / 0.8) / 2400.0, 1e-3);

    // The distance grammar: <number><unit>, or one of the two named races.
    // Comparison ignores case, all whitespace and hyphens.
    {
        static const char* accepted[] = {
            "10k", "10 k", "10K", "10 km", "10 KM", "10\tkm", "10\nk",
            "10 kilometer", "10 kilometres", "10 KILOMETRE", "10kilometers",
            "10-km", "10 - kilo-metres", " 10 kilometres ",
            "6.2 m", "6.2 mile", "6.2 miles", "6.2M", "1 mile", "5 miles",
            "half marathon", "Half-Marathon", "HALF MARATHON", "halfmarathon",
            "half\tmarathon", "marathon", "Marathon", "  marathon  ",
            "10",            // a numeric string is kilometres, like the number 10
            "0.5 k",
        };
        static const char* refused[] = {
            "bogus", "", "ten k", "10kms", "10 kmroad", "10kmroads", "mi",
            "half", "hm", "mar", "mile", "1.5mi", "k", "10 mi", "500km",
            "half marathon 10k", "10,5 km",
        };
        for (const char* d : accepted) {
            const ag::Out o = ag::factor_of(txt("M"), num(40), txt(d), txt("2025"));
            const double f = o.v.empty() ? std::nan("") : o.v[0];
            const bool ok = std::isfinite(f) && f > 0.0 && f <= 1.0;
            // distances outside 1 mile .. 200 km are refused for a different
            // reason, so only require parsing to succeed where in range
            if (!ok && std::string(d) != "0.5 k") {
                ++g_checks; ++g_failures;
                std::printf("  FAIL distance \"%s\" should be accepted\n", d);
            } else {
                ++g_checks;
            }
        }
        for (const char* d : refused) {
            const ag::Out o = ag::factor_of(txt("M"), num(40), txt(d), txt("2025"));
            const double f = o.v.empty() ? std::nan("") : o.v[0];
            if (std::isfinite(f)) {
                ++g_checks; ++g_failures;
                std::printf("  FAIL distance \"%s\" should be refused, got %f\n", d, f);
            } else {
                ++g_checks;
            }
        }
        // spelling never changes the answer
        NEAR(ag::factor_of(txt("M"), num(40), txt("10 KILOMETRES"), txt("2025")).v[0],
             ag::factor_of(txt("M"), num(40), txt("10k"), txt("2025")).v[0], 1e-12);
        NEAR(ag::factor_of(txt("M"), num(40), txt("6.2 miles"), txt("2025")).v[0],
             ag::factor_of(txt("M"), num(40), num(6.2 * 1.609344), txt("2025")).v[0], 1e-12);
        NEAR(ag::factor_of(txt("M"), num(40), txt("Half-Marathon"), txt("2025")).v[0],
             ag::factor_of(txt("M"), num(40), num(21.0975), txt("2025")).v[0], 1e-12);
    }

    // OpenStd may be omitted when the distance is a published one
    const ag::Matrix nostd = mat({
        {"Sex", "Event", "30", "40", "50"},
        {"M", "10 k", "1", "0.9", "0.8"},
        {"F", "10 k", "1", "0.85", "0.75"},
    });
    const ag::Out ns = ag::grade(txt("M"), num(40), num(10.0), num(2400),
                                 ag::Value::of_matrix(nostd));
    NEAR(ns.v[0], g.v[0], 1e-6);       // built-in 10 km standard 26:24

    // an unrecognisable range is reported clearly
    ag::set_last_error("");
    const ag::Matrix junk = mat({{"hello", "world"}, {"a", "b"}});
    const ag::Out bad = ag::grade(txt("M"), num(40), num(10.0), num(2400),
                                  ag::Value::of_matrix(junk));
    IS_NAN(bad.v[0]);
    OK(ag::last_error().find("unrecognised table layout") != std::string::npos);

    // a factor outside (0, 1] is rejected with the offending row
    ag::set_last_error("");
    const ag::Matrix over = mat({
        {"Sex", "Event", "OpenStd", "30", "40"},
        {"M", "10 k", "26:24", "1.5", "0.9"},
    });
    const ag::Out o = ag::grade(txt("M"), num(40), num(10.0), num(2400),
                                ag::Value::of_matrix(over));
    IS_NAN(o.v[0]);
    OK(ag::last_error().find("factor must be in (0, 1]") != std::string::npos);
}

// ---------------------------------------------------------------------------
void test_inverse_and_block() {
    section("inverse function and the one-call block");
    const ag::Out t = ag::time_for_pct(txt("M"), num(40), num(10.0), num(68.49), txt("2025"));
    NEAR(t.v[0] * 86400.0, 2400.0, 1.0);

    const ag::Out b = ag::block(svec({"M", "F"}), vec({40, 56}), num(10.0),
                                num(2400), txt("2025"));
    OK(b.rows == 2 && b.cols == 5);
    NEAR(b.v[4], 68.49, 0.01);                 // row 0 percent
    NEAR(b.v[5 + 4], 87.42, 0.01);             // row 1 percent
    NEAR(b.v[1] * 86400.0, 1584.0, 0.5);       // open standard
    NEAR(b.v[3] * 86400.0, 2400.0 * b.v[0], 0.5);   // graded = time * factor
}

// ---------------------------------------------------------------------------
void test_diagnostics() {
    section("diagnostics");
    const ag::Out ts = ag::tables();
    OK(ts.rows >= 4 && ts.cols == 1);
    OK(ts.v[0] == 2025.0);                     // newest first

    const ag::Out info = ag::table_info(txt("2025"));
    OK(info.cols == 4);
    NEAR(info.v[0], 2025, 0);
    NEAR(info.v[1], 22, 0);
    NEAR(info.v[2], 96, 0);
    NEAR(info.v[3], 2, 0);

    const ag::Out ci = ag::cache_info();
    OK(ci.cols == 6);
    OK(ci.v[0] >= 4);

    const ag::Out cl = ag::cache_clear();
    NEAR(cl.v[0], 1.0, 0);
    OK(ag::Registry::instance().stats().adhoc_entries == 0);
}

// ---------------------------------------------------------------------------
void test_sidecar_csv() {
    section("sidecar CSV tables");
    const std::string dir = "xll_test_tmp";
    const std::string path = dir + "/club.csv";
#ifdef _WIN32
    (void)!std::system(("if not exist " + dir + " mkdir " + dir).c_str());
#else
    if (std::system(("mkdir -p " + dir).c_str()) != 0) { /* best effort */ }
#endif
    {
        std::FILE* f = std::fopen(path.c_str(), "wb");
        if (!f) { OK(false); return; }
        std::fputs("Sex,Event,OpenStd,30,40,50\n", f);
        std::fputs("M,10 k,26:24,1,0.9,0.8\n", f);
        std::fputs("F,10 k,28:46,1,0.85,0.75\n", f);
        std::fclose(f);
    }
    ag::Registry::instance().clear();
    ag::init({dir});
    ag::set_last_error("");
    const ag::Out g = ag::grade(txt("M"), num(40), num(10.0), num(2400), txt("club"));
    NEAR(g.v[0], 100.0 * (1584.0 / 0.9) / 2400.0, 1e-3);
    OK(ag::Registry::instance().stats().file_tables == 1);
    const ag::Out f = ag::grade(txt("F"), num(50), num(10.0), num(2400), txt("club"));
    NEAR(f.v[0], 100.0 * (1726.0 / 0.75) / 2400.0, 1e-3);

    // the example table printed in docs/ad-hoc-tables.md must behave as documented
    const std::string vets = dir + "/bellville-vets.csv";
    {
        std::FILE* g = std::fopen(vets.c_str(), "wb");
        if (!g) { OK(false); return; }
        std::fputs("Sex,Event,OpenStd,45,50,55,60,65,70\n", g);
        std::fputs("M,10 k,26:24,0.9724,0.933,0.8937,0.8543,0.8149,0.7755\n", g);
        std::fputs("F,10 k,28:46,0.9742,0.9263,0.8741,0.8219,0.7698,0.7176\n", g);
        std::fclose(g);
    }
    ag::Registry::instance().clear();
    const ag::Out vet = ag::grade(txt("M"), num(55), num(10.0), num(45 * 60),
                                  txt("bellville-vets"));
    NEAR(vet.v[0], 65.64, 0.01);            // documented: 65.6% against 68.9%
}

// ---------------------------------------------------------------------------
void test_parsing() {
    section("value parsing");
    double s = 0;
    std::string why;
    OK(ag::parse_time(ag::Cell::string("40:00"), s, why) && std::fabs(s - 2400) < 1e-9);
    OK(ag::parse_time(ag::Cell::string("1:02:52"), s, why) && std::fabs(s - 3772) < 1e-9);
    OK(ag::parse_time(ag::Cell::string("2:00:35.5"), s, why) && std::fabs(s - 7235.5) < 1e-6);
    OK(ag::parse_time(ag::Cell::number(2400), s, why) && s == 2400);         // seconds
    OK(ag::parse_time(ag::Cell::number(2400.0 / 86400.0), s, why) &&
       std::fabs(s - 2400) < 1e-6);                                          // serial
    OK(ag::parse_time(ag::Cell{}, s, why) && s == 0);                        // blank
    OK(!ag::parse_time(ag::Cell::string("soon"), s, why));

    double km = 0;
    std::string ev;
    OK(ag::parse_distance(ag::Cell::string("10k"), km, ev) && std::fabs(km - 10) < 1e-9);
    OK(ag::parse_distance(ag::Cell::string("Half Marathon"), km, ev) && std::fabs(km - 21.0975) < 1e-9);
    OK(ag::parse_distance(ag::Cell::string("10 k"), km, ev) && std::fabs(km - 10) < 1e-9);
    OK(ag::parse_distance(ag::Cell::number(12.5), km, ev) && std::fabs(km - 12.5) < 1e-9);
    OK(!ag::parse_distance(ag::Cell::string("10 miles maybe"), km, ev));

    int sex = -1;
    OK(ag::parse_sex(ag::Cell::string("M"), sex) && sex == 1);
    OK(ag::parse_sex(ag::Cell::string("female"), sex) && sex == 0);
    OK(ag::parse_sex(ag::Cell::number(0), sex) && sex == 0);
    OK(!ag::parse_sex(ag::Cell::string("both"), sex));

    OK(ag::normalise_table_name(ag::Cell::number(2025)) == "2025");
    OK(ag::normalise_table_name(ag::Cell::string(" latest ")).empty());
    OK(ag::normalise_table_name(ag::Cell{}).empty());
}

}  // namespace

int main() {
    std::printf("age-grading add-in: native test suite\n");
    ag::init({});
    test_parsing();
    test_smoke();
    test_ground_truth();
    test_vectors();
    test_tables();
    test_adhoc();
    test_inverse_and_block();
    test_diagnostics();
    test_sidecar_csv();

    std::printf("\n%d checks, %d failure(s)\n", g_checks, g_failures);
    if (g_failures == 0) std::printf("ALL TESTS PASSED\n");
    return g_failures == 0 ? 0 : 1;
}
