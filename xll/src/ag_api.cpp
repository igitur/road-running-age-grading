// ag_api.cpp — see ag_api.h
#include "ag_api.h"

#include <algorithm>
#include <cmath>
#include <limits>
#include <sstream>

namespace ag {

namespace {

constexpr double kNaN = std::numeric_limits<double>::quiet_NaN();
constexpr std::size_t kMaxRows = 200000;

thread_local std::string g_last_error;

// The core functions share their names with the worksheet-facing ones above;
// spell the core calls out so overload resolution is never in doubt.
inline Lookup core_lookup(const Table& t, int sex, double age, double km) {
    return lookup(t, sex, age, km);
}
inline Graded core_grade(const Table& t, int sex, double age, double km,
                         double seconds) {
    return grade(t, sex, age, km, seconds);
}
inline double core_time_for_percent(const Table& t, int sex, double age,
                                    double km, double pct) {
    return time_for_percent(t, sex, age, km, pct);
}

// Broadcast shape for the data vectors.
//
// Every argument may be a scalar (broadcast) or a vector. All vectors must hold
// the same number of values — the rule a club sheet expects. Excel itself would
// broadcast silently, pairing one athlete's age with another's time; here a
// mismatch is an error that names both arguments.
struct Shape {
    std::size_t n = 1;
    std::size_t rows = 1, cols = 1;
};

Shape align(const std::vector<const Value*>& args,
            const std::vector<const char*>& names) {
    Shape s;
    std::size_t first = args.size();
    for (std::size_t i = 0; i < args.size(); ++i) {
        if (args[i]->scalar()) continue;
        if (first == args.size()) {
            first = i;
            s.n = args[i]->count();
            s.rows = args[i]->rows();
            s.cols = args[i]->cols();
            continue;
        }
        if (args[i]->count() != s.n) {
            std::ostringstream os;
            os << names[i] << " has " << args[i]->count()
               << " values but " << names[first] << " has " << s.n
               << "; every vector argument must be the same length";
            g_last_error = os.str();
            throw Error{Err::Value, g_last_error};
        }
        if (args[i]->rows() != s.rows || args[i]->cols() != s.cols) {
            s.rows = s.n;      // mixed shapes (3x1 with 1x3) -> one column
            s.cols = 1;
        }
    }
    if (s.n > kMaxRows) {
        std::ostringstream os;
        os << s.n << " rows exceeds the " << kMaxRows << "-row limit";
        g_last_error = os.str();
        throw Error{Err::Num, g_last_error};
    }
    if (first == args.size()) {
        s.rows = s.cols = 1;
    }
    return s;
}

// Resolve the table argument. A range is an ad hoc table; a scalar is an
// edition name ("2025", "latest", "" ...) or a sidecar CSV name.
const Table* resolve_table(const Value& tbl, std::string& why) {
    Registry& reg = Registry::instance();
    try {
        if (!tbl.scalar()) return &reg.adhoc(tbl.m, "range");
        return &reg.find(normalise_table_name(tbl.c));
    } catch (const Error& e) {
        why = e.what;
        return nullptr;
    }
}

struct Core {
    int sex = 0;
    double age = 0;
    double km = 0;
};

bool read_core(const Value& sex, const Value& age, const Value& dist,
               std::size_t i, Core& out, std::string& why) {
    if (!parse_sex(sex.at(i), out.sex)) {
        why = "sex must be M or F";
        return false;
    }
    const Cell& ac = age.at(i);
    if (!ac.is_num()) {
        why = "age must be a number";
        return false;
    }
    out.age = ac.num;
    if (out.age < 1 || out.age > 120) {
        why = "age must be between 1 and 120";
        return false;
    }
    std::string ev;
    if (!parse_distance(dist.at(i), out.km, ev)) {
        const Cell& dc = dist.at(i);
        why = dc.is_text() ? ("unknown event \"" + dc.text + "\"")
                           : "distance must be a positive number of km";
        return false;
    }
    return true;
}

std::string row_message(std::size_t i, const std::string& why) {
    std::ostringstream os;
    os << "row " << (i + 1) << ": " << why;
    return os.str();
}

// Driver for the functions that need a time.
template <typename Fn>
Out run_with_time(const Value& sex, const Value& age, const Value& dist,
                  const Value& time, const Value& tbl, Fn&& fn) {
    Shape s;
    std::string why;
    const Table* t = nullptr;
    try {
        s = align({&sex, &age, &dist, &time}, {"sex", "age", "distance", "time"});
        t = resolve_table(tbl, why);
    } catch (const Error& e) {
        why = e.what;
    }
    Out out = Out::rectangle(s.rows, s.cols);
    if (t == nullptr) {
        std::fill(out.v.begin(), out.v.end(), kNaN);
        if (g_last_error.empty()) g_last_error = why;
        return out;
    }
    bool first_failure = true;
    for (std::size_t i = 0; i < s.n; ++i) {
        Core in;
        std::string row_why;
        double seconds = 0;
        if (!parse_time(time.at(i), seconds, row_why)) {
            out.v[i] = kNaN;
            if (first_failure) { g_last_error = row_message(i, row_why); first_failure = false; }
            continue;
        }
        if (seconds <= 0) { out.v[i] = 0.0; continue; }   // blank time: empty row
        if (!read_core(sex, age, dist, i, in, row_why)) {
            out.v[i] = kNaN;
            if (first_failure) { g_last_error = row_message(i, row_why); first_failure = false; }
            continue;
        }
        try {
            out.v[i] = fn(*t, in, seconds);
        } catch (const Error& e) {
            out.v[i] = kNaN;
            if (first_failure) { g_last_error = row_message(i, e.what); first_failure = false; }
        }
    }
    return out;
}

// Driver for the functions that do not.
template <typename Fn>
Out run_plain(const Value& sex, const Value& age, const Value& dist,
              const Value& tbl, Fn&& fn) {
    Shape s;
    std::string why;
    const Table* t = nullptr;
    try {
        s = align({&sex, &age, &dist}, {"sex", "age", "distance"});
        t = resolve_table(tbl, why);
    } catch (const Error& e) {
        why = e.what;
    }
    Out out = Out::rectangle(s.rows, s.cols);
    if (t == nullptr) {
        std::fill(out.v.begin(), out.v.end(), kNaN);
        if (g_last_error.empty()) g_last_error = why;
        return out;
    }
    bool first_failure = true;
    for (std::size_t i = 0; i < s.n; ++i) {
        Core in;
        std::string row_why;
        if (!read_core(sex, age, dist, i, in, row_why)) {
            out.v[i] = kNaN;
            if (first_failure) { g_last_error = row_message(i, row_why); first_failure = false; }
            continue;
        }
        try {
            out.v[i] = fn(*t, in);
        } catch (const Error& e) {
            out.v[i] = kNaN;
            if (first_failure) { g_last_error = row_message(i, e.what); first_failure = false; }
        }
    }
    return out;
}

}  // namespace

// ---------------------------------------------------------------------------
std::string last_error() { return g_last_error; }
void set_last_error(const std::string& msg) { g_last_error = msg; }

// ---------------------------------------------------------------------------
// grading
// ---------------------------------------------------------------------------
Out grade(const Value& sex, const Value& age, const Value& distance,
          const Value& time, const Value& table) {
    return run_with_time(sex, age, distance, time, table,
                         [](const Table& t, const Core& c, double seconds) {
                             return core_grade(t, c.sex, c.age, c.km, seconds).percent;
                         });
}

Out graded_time(const Value& sex, const Value& age, const Value& distance,
                const Value& time, const Value& table) {
    return run_with_time(sex, age, distance, time, table,
                         [](const Table& t, const Core& c, double seconds) {
                             return seconds_to_days(
                                 core_grade(t, c.sex, c.age, c.km, seconds).graded);
                         });
}

Out factor_of(const Value& sex, const Value& age, const Value& distance,
              const Value& table) {
    return run_plain(sex, age, distance, table,
                     [](const Table& t, const Core& c) {
                         return core_lookup(t, c.sex, c.age, c.km).factor;
                     });
}

Out standard_of(const Value& sex, const Value& age, const Value& distance,
                const Value& table) {
    return run_plain(sex, age, distance, table,
                     [](const Table& t, const Core& c) {
                         return seconds_to_days(
                             core_lookup(t, c.sex, c.age, c.km).standard);
                     });
}

Out time_for_pct(const Value& sex, const Value& age, const Value& distance,
                 const Value& percent, const Value& table) {
    Shape s;
    std::string why;
    const Table* t = nullptr;
    try {
        s = align({&sex, &age, &distance, &percent},
                  {"sex", "age", "distance", "percent"});
        t = resolve_table(table, why);
    } catch (const Error& e) {
        why = e.what;
    }
    Out out = Out::rectangle(s.rows, s.cols);
    if (t == nullptr) {
        std::fill(out.v.begin(), out.v.end(), kNaN);
        if (g_last_error.empty()) g_last_error = why;
        return out;
    }
    bool first_failure = true;
    for (std::size_t i = 0; i < s.n; ++i) {
        Core in;
        std::string row_why;
        if (!read_core(sex, age, distance, i, in, row_why)) {
            out.v[i] = kNaN;
            if (first_failure) { g_last_error = row_message(i, row_why); first_failure = false; }
            continue;
        }
        const Cell& pc = percent.at(i);
        if (!pc.is_num() || pc.num <= 0) {
            out.v[i] = kNaN;
            if (first_failure) {
                g_last_error = row_message(i, "percent must be a positive number");
                first_failure = false;
            }
            continue;
        }
        try {
            out.v[i] = seconds_to_days(
                core_time_for_percent(*t, in.sex, in.age, in.km, pc.num));
        } catch (const Error& e) {
            out.v[i] = kNaN;
            if (first_failure) { g_last_error = row_message(i, e.what); first_failure = false; }
        }
    }
    return out;
}

Out block(const Value& sex, const Value& age, const Value& distance,
          const Value& time, const Value& table) {
    Shape s;
    std::string why;
    const Table* t = nullptr;
    try {
        s = align({&sex, &age, &distance, &time}, {"sex", "age", "distance", "time"});
        t = resolve_table(table, why);
    } catch (const Error& e) {
        why = e.what;
    }
    Out out = Out::rectangle(s.rows, 5);
    if (t == nullptr) {
        std::fill(out.v.begin(), out.v.end(), kNaN);
        if (g_last_error.empty()) g_last_error = why;
        return out;
    }
    bool first_failure = true;
    for (std::size_t i = 0; i < s.n; ++i) {
        Core in;
        std::string row_why;
        double* row = &out.v[i * 5];
        double seconds = 0;
        if (!parse_time(time.at(i), seconds, row_why)) {
            for (int k = 0; k < 5; ++k) row[k] = kNaN;
            if (first_failure) { g_last_error = row_message(i, row_why); first_failure = false; }
            continue;
        }
        if (seconds <= 0) {
            for (int k = 0; k < 5; ++k) row[k] = 0.0;
            continue;
        }
        if (!read_core(sex, age, distance, i, in, row_why)) {
            for (int k = 0; k < 5; ++k) row[k] = kNaN;
            if (first_failure) { g_last_error = row_message(i, row_why); first_failure = false; }
            continue;
        }
        try {
            const Graded g = core_grade(*t, in.sex, in.age, in.km, seconds);
            row[0] = g.factor;
            row[1] = seconds_to_days(g.standard);
            row[2] = seconds_to_days(g.age_standard);
            row[3] = seconds_to_days(g.graded);
            row[4] = g.percent;
        } catch (const Error& e) {
            for (int k = 0; k < 5; ++k) row[k] = kNaN;
            if (first_failure) { g_last_error = row_message(i, e.what); first_failure = false; }
        }
    }
    return out;
}

// ---------------------------------------------------------------------------
// diagnostics
// ---------------------------------------------------------------------------
Out tables() {
    Registry& reg = Registry::instance();
    const std::vector<std::string> names = reg.names();
    std::vector<double> years;
    for (const auto& n : names) {
        try {
            const Table& t = reg.find(n);
            years.push_back(t.year > 0 ? static_cast<double>(t.year) : kNaN);
        } catch (const Error&) {
            years.push_back(kNaN);
        }
    }
    std::sort(years.begin(), years.end(), [](double a, double b) { return a > b; });
    if (years.empty()) years.push_back(kNaN);
    Out o;
    o.rows = years.size();
    o.cols = 1;
    o.v = std::move(years);
    return o;
}

Out table_info(const Value& table) {
    std::string why;
    const Table* t = resolve_table(table, why);
    Out o = Out::rectangle(1, 4);
    if (t == nullptr) {
        std::fill(o.v.begin(), o.v.end(), kNaN);
        g_last_error = why;
        return o;
    }
    o.v[0] = static_cast<double>(t->year);
    o.v[1] = static_cast<double>(t->events.size());
    o.v[2] = t->sex[1].present ? static_cast<double>(t->sex[1].ages.size())
                              : (t->sex[0].present
                                     ? static_cast<double>(t->sex[0].ages.size())
                                     : 0.0);
    o.v[3] = (t->sex[0].present ? 1.0 : 0.0) + (t->sex[1].present ? 1.0 : 0.0);
    return o;
}

Out cache_info() {
    Registry& reg = Registry::instance();
    const CacheStats s = reg.stats();
    Out o = Out::rectangle(1, 6);
    o.v[0] = static_cast<double>(s.builtin_tables);
    o.v[1] = static_cast<double>(s.file_tables);
    o.v[2] = static_cast<double>(s.adhoc_entries);
    o.v[3] = static_cast<double>(s.hit);
    o.v[4] = static_cast<double>(s.miss);
    o.v[5] = static_cast<double>(reg.adhoc_capacity());
    return o;
}

Out cache_clear() {
    Registry::instance().clear();
    return Out::scalar(1.0);
}

}  // namespace ag
