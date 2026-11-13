// ag_api.h — the worksheet-facing surface, independent of Excel.
//
// The XLL wrapper converts XLOPER12s to Values, calls these functions and
// converts the result back. Everything that can be wrong — vector alignment,
// per-cell parsing, table resolution, caching — is decided here, where the
// native test binary can exercise it.
#pragma once

#include "ag_core.h"

#include <string>
#include <vector>

namespace ag {

// One Excel argument: a scalar or a rectangle.
struct Value {
    bool is_matrix = false;
    Matrix m;
    Cell c;

    std::size_t count() const { return is_matrix ? m.size() : 1; }
    bool scalar() const { return !is_matrix || m.size() <= 1; }
    std::size_t rows() const { return is_matrix ? m.rows : 1; }
    std::size_t cols() const { return is_matrix ? m.cols : 1; }
    const Cell& at(std::size_t i) const { return is_matrix ? m.v[i] : c; }

    static Value of_cell(const Cell& cell) {
        Value v;
        v.c = cell;
        return v;
    }
    static Value of_matrix(Matrix mat) {
        Value v;
        v.is_matrix = true;
        v.m = std::move(mat);
        return v;
    }
};

// Result: a numeric rectangle (dynamic array), or text for the diagnostics
// functions. A NaN cell renders as #NUM!.
struct Out {
    std::size_t rows = 1, cols = 1;
    std::vector<double> v;          // rows*cols, row-major
    bool is_text = false;
    std::string text;

    static Out scalar(double x) {
        Out o;
        o.v.assign(1, x);
        return o;
    }
    static Out rectangle(std::size_t r, std::size_t c) {
        Out o;
        o.rows = r;
        o.cols = c;
        o.v.assign(r * c, 0.0);
        return o;
    }
    static Out string(std::string s) {
        Out o;
        o.is_text = true;
        o.text = std::move(s);
        return o;
    }
    double& at(std::size_t r, std::size_t c) { return v[r * cols + c]; }
};

// ---- worksheet functions -------------------------------------------------
// Every one returns a dynamic array; a scalar gives 1x1.
Out grade(const Value& sex, const Value& age, const Value& distance,
          const Value& time, const Value& table);
Out graded_time(const Value& sex, const Value& age, const Value& distance,
                const Value& time, const Value& table);
Out factor_of(const Value& sex, const Value& age, const Value& distance,
              const Value& table);
Out standard_of(const Value& sex, const Value& age, const Value& distance,
                const Value& table);
Out time_for_pct(const Value& sex, const Value& age, const Value& distance,
                 const Value& percent, const Value& table);
// n x 5: factor, open standard (s), age standard (s), graded time (s), percent
Out block(const Value& sex, const Value& age, const Value& distance,
          const Value& time, const Value& table);

// ---- diagnostics ---------------------------------------------------------
Out tables();                       // k x 1: edition years, newest first
Out table_info(const Value& table); // 1 x 4: year, events, ages, sexes
Out cache_info();                   // 1 x 6: builtin, files, adhoc, hits, misses, cap
Out cache_clear();                  // 1 x 1: 1 on success

// The most recent failure, for the cell next to a column of #NUM!s.
std::string last_error();
void set_last_error(const std::string& msg);

}  // namespace ag
