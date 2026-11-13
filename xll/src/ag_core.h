// ag_core.h — portable core of the age-grading add-in.
//
// No Excel, no Windows, no I/O beyond reading an optional CSV sidecar. The XLL
// wrapper is a thin marshaller over this, and the native test binary compiles
// exactly the same code, so what is tested is what ships.
//
// The arithmetic mirrors the published calculator (see docs/03-algorithm.md in
// the parent repo): bilinear lookup in (age, distance) over the published rows,
// then percent = open_standard / (time * factor), as a fraction (0.6849).
#pragma once

#include <cstdint>
#include <map>
#include <memory>
#include <mutex>
#include <string>
#include <unordered_map>
#include <vector>

namespace ag {

// --------------------------------------------------------------------------
// errors
// --------------------------------------------------------------------------
enum class Err {
    Value,   // bad argument, unknown name, length mismatch  -> #VALUE!
    Num,     // out of range, blank, not a number           -> #NUM!
    NA,      // no such table                               -> #N/A
};

struct Error {
    Err kind;
    std::string what;
};

// --------------------------------------------------------------------------
// one spreadsheet cell, and a rectangle of them
// --------------------------------------------------------------------------
struct Cell {
    enum class Kind { Blank, Num, Text, Bool, Err } kind = Kind::Blank;
    double num = 0.0;
    std::string text;
    int err = 0;                      // Excel error code when kind == Err

    bool is_blank() const { return kind == Kind::Blank; }
    bool is_num() const { return kind == Kind::Num || kind == Kind::Bool; }
    bool is_text() const { return kind == Kind::Text; }

    static Cell blank() { return Cell{}; }
    static Cell number(double v);     // NOLINT: implicit by design
    static Cell string(std::string s);
};

struct Matrix {
    std::size_t rows = 0, cols = 0;
    std::vector<Cell> v;

    Matrix() = default;
    Matrix(std::size_t r, std::size_t c) : rows(r), cols(c), v(r * c) {}

    const Cell& at(std::size_t r, std::size_t c) const { return v[r * cols + c]; }
    Cell& at(std::size_t r, std::size_t c) { return v[r * cols + c]; }
    std::size_t size() const { return rows * cols; }
    bool empty() const { return rows == 0 || cols == 0; }
};

// --------------------------------------------------------------------------
// a table: one event list shared by both sexes, factors per sex
// --------------------------------------------------------------------------
struct EventRow {
    std::string name;      // "10kmRoad"
    double distance_km = 0;
    double std_[2] = {0, 0};   // open standard in seconds, 0 = female, 1 = male
};

struct SexTable {
    bool present = false;
    // The published calculator clamps any age in (99, 100] to the age-100
    // factors instead of interpolating — a faithful quirk of its search loop,
    // kept so results match it exactly. That rule is an artefact of a grid that
    // ends at 100 and must NOT be applied to a custom table whose last two ages
    // might be 60 and 65, where it would turn 61 into 65. Built-in editions set
    // this; ad hoc tables leave it false.
    bool ui_age_quirk = false;
    std::vector<int> ages;              // ascending, e.g. 5..100
    std::vector<float> factors;         // events x ages, event-major
    std::size_t n_events = 0;

    float at(std::size_t e, std::size_t a) const {
        return factors[e * ages.size() + a];
    }
};

struct Table {
    std::string name;
    std::string authority;
    int year = 0;
    std::string source;                 // "builtin", "file:<path>", "adhoc"
    std::vector<EventRow> events;       // sorted by distance_km
    SexTable sex[2];                    // 0 = female, 1 = male

    bool has(int s) const { return sex[s].present; }
};

// --------------------------------------------------------------------------
// value parsing (shared by the API layer, the CSV loader and the tests)
// --------------------------------------------------------------------------
// "M"/"F"/"Male"/"Female"/1/0 -> 1/0. Returns false if not a sex.
bool parse_sex(const Cell& c, int& sex_out);

// A time in seconds from a cell: h:mm:ss / mm:ss text, an Excel serial
// (< 1 day) or a plain number of seconds (>= 1). 0 means "blank/zero".
bool parse_time(const Cell& c, double& seconds_out, std::string& why);

// A distance in km from a cell: a number, "10km", "10 k", "half", "marathon",
// "10kmRoad", "10 Mile", ... Returns false if unrecognised.
bool parse_distance(const Cell& c, double& km_out, std::string& event_out);

// Excel serial day fraction <-> seconds.
inline double days_to_seconds(double d) { return d * 86400.0; }
inline double seconds_to_days(double s) { return s / 86400.0; }

// Normalise an edition name: "2025", " 2025 ", numeric 2025 -> "2025";
// "" and "latest" -> "" (meaning: newest built-in).
std::string normalise_table_name(const Cell& c);

// --------------------------------------------------------------------------
// lookup and grading
// --------------------------------------------------------------------------
struct Lookup {
    double factor = 1.0;
    double standard = 0.0;      // open standard, seconds
};

struct Graded {
    double factor = 1.0;
    double standard = 0.0;      // open standard, seconds
    double age_standard = 0.0;  // time that scores 100%
    double graded = 0.0;        // time * factor
    double percent = 0.0;   // a fraction, not 0-100: Excel's % format shows it
};

// Throws Error{Num} when the distance is outside the published range.
Lookup lookup(const Table& t, int sex, double age, double distance_km);

Graded grade(const Table& t, int sex, double age, double distance_km,
             double time_seconds);

// The time that would score `percent` (the calculator's "Result" button).
// `percent` is a fraction: 0.75 for 75 %.
double time_for_percent(const Table& t, int sex, double age, double distance_km,
                        double percent);

// Resolve an event name (case-insensitive, "Road" suffix optional) or a
// distance in km to the event index. Returns -1 when nothing matches.
int find_event(const Table& t, const std::string& name, double km,
               bool have_km);

// --------------------------------------------------------------------------
// ad hoc tables
// --------------------------------------------------------------------------
// Two layouts are understood, auto-detected from the header row:
//
//  matrix  (recommended; copies 1:1 out of the official workbook)
//      Sex | Event     | OpenStd | 5      | 6      | ... | 100
//      M   | 10kmRoad  | 26:24   | 0.5073 | 0.5678 | ...
//
//  long
//      Sex | Event     | Age | Factor | OpenStd
//      M   | 10kmRoad  | 40  | 0.9636 | 26:24
//
// OpenStd may be omitted in either layout, in which case the built-in 2025
// open standard for that distance is used.
//
// Throws Error{Value} with a message naming the offending row/column.
Table parse_table(const Matrix& m, const std::string& name);

// 64-bit FNV-1a over the cell contents, used as the cache key for a range.
std::uint64_t matrix_hash(const Matrix& m);

// --------------------------------------------------------------------------
// registry: built-in editions, CSV sidecars, ad hoc ranges — all cached
// --------------------------------------------------------------------------
struct CacheStats {
    std::size_t builtin_tables = 0;
    std::size_t file_tables = 0;
    std::size_t adhoc_entries = 0;
    std::uint64_t hit = 0, miss = 0;
};

class Registry {
public:
    static Registry& instance();

    // Directories scanned for "<name>.csv" sidecars, e.g. the folder holding
    // the .xll and %APPDATA%/aggrade/tables.
    void add_search_dir(const std::string& dir);
    std::vector<std::string> search_dirs() const;

    // "" or "latest" -> newest built-in edition.
    // Name lookup: built-in edition, then <name>.csv in a search dir.
    const Table& find(const std::string& name);
    bool has(const std::string& name);

    // Parse a range as a table and cache it by content hash. `label` is only
    // used for diagnostics.
    const Table& adhoc(const Matrix& m, const std::string& label);

    std::vector<std::string> names();          // built-in + file editions
    CacheStats stats() const;
    void clear();                              // drop non-builtin entries
    void set_adhoc_capacity(std::size_t n);    // default 16
    std::size_t adhoc_capacity() const;

private:
    Registry();
    void ensure_builtins();

    mutable std::mutex mu_;
    std::vector<std::string> dirs_;
    std::map<std::string, Table> builtin_;
    std::map<std::string, Table> file_;
    std::unordered_map<std::uint64_t, Table> adhoc_;
    std::vector<std::uint64_t> adhoc_order_;   // LRU
    std::size_t adhoc_capacity_ = 16;
    mutable std::uint64_t hit_ = 0, miss_ = 0;
    std::string latest_;
};

// The open standard for a distance in the newest built-in table, used when an
// ad hoc table omits the OpenStd column. 0 when the distance is not published.
double builtin_standard(double distance_km, int sex);

// Everything the add-in needs to know before serving calls.
void init(const std::vector<std::string>& search_dirs);
std::string version_string();

}  // namespace ag
