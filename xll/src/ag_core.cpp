// ag_core.cpp — see ag_core.h
#include "ag_core.h"

#include "ag_tables_generated.h"

#include <algorithm>
#include <cctype>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <fstream>
#include <limits>
#include <sstream>
#include <stdexcept>

namespace ag {

namespace {

constexpr double kNaN = std::numeric_limits<double>::quiet_NaN();

std::string lower(std::string s) {
    for (auto& c : s) c = static_cast<char>(std::tolower(static_cast<unsigned char>(c)));
    return s;
}

std::string trim(const std::string& s) {
    const auto b = s.find_first_not_of(" \t\r\n");
    if (b == std::string::npos) return {};
    const auto e = s.find_last_not_of(" \t\r\n");
    return s.substr(b, e - b + 1);
}

// Remove spaces and underscores for label/number comparison: "10 Mile" -> "10mile".
// Normalise for comparison: no whitespace of any kind (spaces, tabs, newlines,
// non-breaking spaces), no hyphens or underscores, lower case. "Half-Marathon",
// "10 K M" and "10\tkm" then compare as "halfmarathon", "10km", "10km".
std::string squash(std::string s) {
    std::string o;
    o.reserve(s.size());
    for (char c : s) {
        const unsigned char u = static_cast<unsigned char>(c);
        if (std::isspace(u) || c == '-' || c == '_') continue;
        if (u == 0xC2 || u == 0xC3) continue;          // UTF-8 lead of NBSP/dashes
        if (u == 0xA0 || u == 0x96 || u == 0x97) continue;  // NBSP, en/em dash tails
        o.push_back(static_cast<char>(std::tolower(u)));
    }
    return o;
}

bool parse_double(const std::string& s, double& out) {
    if (s.empty()) return false;
    char* end = nullptr;
    const double v = std::strtod(s.c_str(), &end);
    if (end == s.c_str()) return false;
    while (end && *end && std::isspace(static_cast<unsigned char>(*end))) ++end;
    if (end && *end) return false;
    out = v;
    return true;
}

// ---------------------------------------------------------------------------
// hh:mm:ss / mm:ss / ss  ->  seconds
// ---------------------------------------------------------------------------
bool parse_clock_text(const std::string& raw, double& seconds) {
    std::string s = trim(raw);
    if (s.empty()) return false;
    std::replace(s.begin(), s.end(), ';', ':');
    std::vector<double> parts;
    std::size_t start = 0;
    while (true) {
        const auto pos = s.find(':', start);
        const std::string piece = (pos == std::string::npos)
                                      ? s.substr(start)
                                      : s.substr(start, pos - start);
        double v = 0;
        if (!parse_double(trim(piece), v) || v < 0) return false;
        parts.push_back(v);
        if (pos == std::string::npos) break;
        start = pos + 1;
        if (parts.size() > 3) return false;
    }
    if (parts.size() > 3) return false;
    double total = 0;
    for (double p : parts) total = total * 60.0 + p;
    seconds = total;
    return true;
}

// ---------------------------------------------------------------------------
// distance aliases, mirroring the Python CLI so the two agree
// ---------------------------------------------------------------------------
// One mile in kilometres; the tables are in km, so miles convert on the way in.
constexpr double kMileKm = 1.609344;

}  // namespace

// ---------------------------------------------------------------------------
// Cell
// ---------------------------------------------------------------------------
Cell Cell::number(double v) {
    Cell c;
    c.kind = Kind::Num;
    c.num = v;
    return c;
}

Cell Cell::string(std::string s) {
    Cell c;
    c.kind = Kind::Text;
    c.text = std::move(s);
    return c;
}

// ---------------------------------------------------------------------------
// parsing
// ---------------------------------------------------------------------------
bool parse_sex(const Cell& c, int& sex_out) {
    if (c.is_num()) {
        const double n = c.num;
        if (n == 0.0) { sex_out = 0; return true; }
        if (n == 1.0) { sex_out = 1; return true; }
        return false;
    }
    if (!c.is_text()) return false;
    const std::string k = lower(trim(c.text));
    // accept the whole word (or a word starting with it) so "both", "mixed" and
    // other guesses are rejected rather than silently becoming male
    static const struct { const char* word; int sex; } kWords[] = {
        {"male", 1},   {"man", 1},   {"m", 1},     {"boy", 1},
        {"female", 0}, {"woman", 0}, {"women", 0}, {"f", 0},
        {"girl", 0},   {"w", 0},
    };
    for (const auto& w : kWords) {
        const std::size_t n = std::strlen(w.word);
        if (k.compare(0, n, w.word) != 0) continue;
        // "m" must be alone or followed by a non-letter ("m", "m40")
        if (n == 1 && k.size() > 1 && std::isalpha(static_cast<unsigned char>(k[1]))) {
            if (!(k[1] == ' ' || k[1] == '/' )) continue;
        }
        sex_out = w.sex;
        return true;
    }
    return false;
}

bool parse_time(const Cell& c, double& seconds_out, std::string& why) {
    if (c.is_blank()) { seconds_out = 0.0; return true; }
    if (c.is_num()) {
        const double n = c.num;
        if (n <= 0) { seconds_out = 0.0; return true; }
        // A value below one day is an Excel time serial; a value of one or more
        // is a number of seconds. Documented in xll/docs/functions.md — the only
        // sane reading, since a serial of 2400 would be six and a half years.
        seconds_out = (n < 1.0) ? days_to_seconds(n) : n;
        return true;
    }
    if (c.is_text()) {
        double s = 0;
        if (parse_clock_text(c.text, s) && s > 0) { seconds_out = s; return true; }
        why = "not a time: \"" + c.text + "\" (use 40:00 or 0:40:00)";
        return false;
    }
    why = "not a time";
    return false;
}

// Distance grammar. Accepted, after squash() has removed whitespace and hyphens
// and folded case:
//
//   <number>k | <number>km | <number>kilometer(s) | <number>kilometre(s)   km
//   <number>m | <number>mile | <number>miles                              miles
//   halfmarathon                                                          21.0975 km
//   marathon                                                              42.195 km
//
// A bare number is kilometres: in a cell that is a number, in text it is the
// same thing spelled out ("10"). Anything else is refused rather than snapped to
// a neighbour, because a plausible wrong grade is worse than an error.
bool parse_distance(const Cell& c, double& km_out, std::string& event_out) {
    event_out.clear();
    if (c.is_num()) {
        if (!(c.num > 0)) return false;
        km_out = c.num;
        return true;
    }
    if (!c.is_text()) return false;
    const std::string raw = trim(c.text);
    if (raw.empty()) return false;
    const std::string key = squash(raw);
    if (key.empty()) return false;

    if (key == "halfmarathon") { km_out = 21.0975; event_out = raw; return true; }
    if (key == "marathon")     { km_out = 42.195;  event_out = raw; return true; }

    char* end = nullptr;
    const double n = std::strtod(key.c_str(), &end);
    if (end == key.c_str() || !(n > 0) || !std::isfinite(n)) return false;
    const std::string unit = key.substr(static_cast<std::size_t>(end - key.c_str()));

    if (unit.empty()) { km_out = n; return true; }          // "10" == 10 km
    if (unit == "k" || unit == "km" || unit == "kilometer" || unit == "kilometers" ||
        unit == "kilometre" || unit == "kilometres") {
        km_out = n;
        return true;
    }
    if (unit == "m" || unit == "mile" || unit == "miles") {  // m = miles here
        km_out = n * kMileKm;
        return true;
    }
    return false;
}

std::string normalise_table_name(const Cell& c) {
    if (c.is_blank()) return {};
    if (c.is_num()) {
        const double n = c.num;
        if (n == std::floor(n) && std::fabs(n) < 1e9) {
            char buf[32];
            std::snprintf(buf, sizeof buf, "%lld", static_cast<long long>(n));
            return buf;
        }
        std::ostringstream os;
        os << n;
        return os.str();
    }
    const std::string s = trim(c.text);
    if (s.empty()) return {};
    if (lower(s) == "latest") return {};
    return s;
}

// ---------------------------------------------------------------------------
// events
// ---------------------------------------------------------------------------
namespace {

// Linear interpolation over a sparse row: gaps are filled from their neighbours
// and the ends are clamped. Returns false when there is no data at all.
bool fill_sparse(const std::vector<int>& ages, std::vector<double>& v) {
    std::size_t known = 0;
    for (double x : v) if (!std::isnan(x)) ++known;
    if (known == 0) return false;
    if (known == 1) {
        double only = 0;
        for (double x : v) if (!std::isnan(x)) { only = x; break; }
        std::fill(v.begin(), v.end(), only);
        return true;
    }
    std::size_t i = 0;
    while (i < v.size() && std::isnan(v[i])) ++i;
    for (std::size_t j = 0; j < i; ++j) v[j] = v[i];          // clamp low
    while (i < v.size()) {
        if (std::isnan(v[i])) {
            std::size_t k = i;
            while (k < v.size() && std::isnan(v[k])) ++k;
            if (k == v.size()) break;
            const double x0 = ages[i - 1], x1 = ages[k];
            const double y0 = v[i - 1], y1 = v[k];
            for (std::size_t m = i; m < k; ++m) {
                const double p = (ages[m] - x0) / (x1 - x0);
                v[m] = y0 * (1 - p) + y1 * p;
            }
            i = k;
        } else {
            ++i;
        }
    }
    std::size_t last = v.size();
    while (last > 0 && std::isnan(v[last - 1])) --last;
    for (std::size_t j = last; j < v.size(); ++j) v[j] = v[last - 1];  // clamp high
    return true;
}

}  // namespace

// ---------------------------------------------------------------------------
// lookup / grade
// ---------------------------------------------------------------------------
Lookup lookup(const Table& t, int sex, double age, double distance_km) {
    const SexTable& st = t.sex[sex];
    if (!st.present) {
        throw Error{Err::NA, std::string("table \"") + t.name + "\" has no " +
                                (sex ? "male" : "female") + " factors"};
    }
    if (t.events.empty() || st.ages.size() < 2) {
        throw Error{Err::Num, "table \"" + t.name + "\" is empty"};
    }
    if (std::isnan(distance_km)) {
        throw Error{Err::Num, "distance is blank"};
    }

    // ---- age axis: clamp at both ends, interpolate between integer ages -----
    const std::vector<int>& ages = st.ages;
    if (std::isnan(age)) throw Error{Err::Num, "age is blank"};
    if (age < ages.front()) age = ages.front();
    // Published editions reproduce the calculator's (99, 100] clamp; custom
    // tables interpolate normally up to their last supplied age.
    if (st.ui_age_quirk && age > static_cast<double>(ages[ages.size() - 2])) {
        age = ages.back();
    }

    std::size_t ia = 0, ib = 0;
    double pa = 0;
    if (age <= ages.front()) {
        ia = ib = 0;
    } else if (age >= ages.back()) {
        ia = ib = ages.size() - 1;
    } else {
        std::size_t i = 0;
        while (i < ages.size() && static_cast<double>(ages[i]) < age) ++i;
        ia = i - 1;
        ib = i;
        const double span = static_cast<double>(ages[ib]) - ages[ia];
        pa = span == 0 ? 0.0 : (age - ages[ia]) / span;
    }

    // ---- distance axis: linear between published rows, refuse outside ------
    const double dmin = t.events.front().distance_km;
    const double dmax = t.events.back().distance_km;
    if (distance_km < dmin || distance_km > dmax) {
        throw Error{Err::Num,
                    "distance " + std::to_string(distance_km) +
                        " km is outside the published range " +
                        std::to_string(dmin) + "-" + std::to_string(dmax) + " km"};
    }
    std::size_t e0 = t.events.size() - 1;
    for (std::size_t j = 0; j < t.events.size(); ++j) {
        if (t.events[j].distance_km > distance_km) { e0 = j - 1; break; }
    }
    const std::size_t e1 = std::min(e0 + 1, t.events.size() - 1);
    double pd = 0;
    if (e1 != e0) {
        const double d0 = t.events[e0].distance_km, d1 = t.events[e1].distance_km;
        pd = (distance_km - d0) / (d1 - d0);
    }

    const double f00 = st.at(e0, ia), f01 = st.at(e0, ib);
    const double f10 = st.at(e1, ia), f11 = st.at(e1, ib);
    const double factor = (1 - pd) * ((1 - pa) * f00 + pa * f01) +
                          pd * ((1 - pa) * f10 + pa * f11);
    const double s0 = t.events[e0].std_[sex], s1 = t.events[e1].std_[sex];
    const double standard = (1 - pd) * s0 + pd * s1;

    if (!(factor > 0)) {
        throw Error{Err::Num, "no factor for that age/distance in table \"" + t.name + "\""};
    }
    return Lookup{factor, standard};
}

Graded grade(const Table& t, int sex, double age, double distance_km,
             double time_seconds) {
    const Lookup lk = lookup(t, sex, age, distance_km);
    if (!(time_seconds > 0)) throw Error{Err::Num, "time must be positive"};
    Graded g;
    g.factor = lk.factor;
    g.standard = lk.standard;
    g.age_standard = lk.standard / lk.factor;
    g.graded = time_seconds * lk.factor;
    g.percent = g.age_standard / time_seconds;   // a fraction: 0.6849
    return g;
}

double time_for_percent(const Table& t, int sex, double age, double distance_km,
                        double percent) {
    const Lookup lk = lookup(t, sex, age, distance_km);
    if (!(percent > 0)) throw Error{Err::Num, "percent must be positive"};
    return (lk.standard / lk.factor) / percent;
}

// ---------------------------------------------------------------------------
// ad hoc tables
// ---------------------------------------------------------------------------
namespace {

struct Cols {
    int sex = -1, event = -1, distance = -1, std_ = -1, age = -1, factor = -1;
    std::vector<std::pair<int, int>> age_cols;   // (column, age)
};

Cols read_header(const Matrix& m, std::size_t row) {
    Cols c;
    for (std::size_t j = 0; j < m.cols; ++j) {
        const Cell& cell = m.at(row, j);
        if (cell.is_text()) {
            const std::string k = squash(cell.text);
            if (k == "sex" || k == "gender" || k == "m/f") { c.sex = static_cast<int>(j); continue; }
            if (k == "event" || k == "eventdistance" || k == "discipline") { c.event = static_cast<int>(j); continue; }
            if (k == "distance" || k == "distancekm" || k == "km" || k == "dist") { c.distance = static_cast<int>(j); continue; }
            if (k == "openstd" || k == "openstandard" || k == "standard" || k == "std" ||
                k == "open" || k == "opentime") { c.std_ = static_cast<int>(j); continue; }
            if (k == "age") { c.age = static_cast<int>(j); continue; }
            if (k == "factor" || k == "agefactor" || k == "f") { c.factor = static_cast<int>(j); continue; }
            double v = 0;
            if (parse_double(trim(cell.text), v) && v >= 1 && v <= 120 && v == std::floor(v)) {
                c.age_cols.emplace_back(static_cast<int>(j), static_cast<int>(v));
                continue;
            }
        } else if (cell.is_num()) {
            const double v = cell.num;
            if (v >= 1 && v <= 120 && v == std::floor(v)) {
                c.age_cols.emplace_back(static_cast<int>(j), static_cast<int>(v));
            }
        }
    }
    std::sort(c.age_cols.begin(), c.age_cols.end(),
              [](auto& a, auto& b) { return a.second < b.second; });
    return c;
}

double require_time(const Cell& c, const char* what, std::size_t row) {
    double s = 0;
    std::string why;
    if (!parse_time(c, s, why) || s <= 0) {
        throw Error{Err::Value, "row " + std::to_string(row + 1) + ": " + what +
                               " is not a time"};
    }
    return s;
}

}  // namespace

Table parse_table(const Matrix& m, const std::string& name) {
    if (m.empty()) throw Error{Err::Value, "the table range is empty"};

    // header: first row with at least two non-blank cells
    std::size_t hdr = 0;
    for (; hdr < m.rows; ++hdr) {
        std::size_t n = 0;
        for (std::size_t j = 0; j < m.cols; ++j) if (!m.at(hdr, j).is_blank()) ++n;
        if (n >= 2) break;
    }
    if (hdr == m.rows) throw Error{Err::Value, "the table range has no header row"};

    const Cols c = read_header(m, hdr);
    const bool long_format = c.age >= 0 && c.factor >= 0;
    const bool matrix_format = !c.age_cols.empty() && (c.event >= 0 || c.distance >= 0);

    Table t;
    t.name = name;
    t.authority = "custom";
    t.year = 0;
    t.source = "adhoc";

    if (long_format) {
        // ---- long format: Sex | Event | Age | Factor | [OpenStd] ------------
        std::map<int, std::map<std::string, std::map<int, double>>> pts;  // sex->event->age->f
        std::map<std::string, double> km_of;
        std::map<std::string, double> std_of[2];
        std::vector<int> age_union;

        for (std::size_t r = hdr + 1; r < m.rows; ++r) {
            const Cell& sexc = c.sex >= 0 ? m.at(r, static_cast<std::size_t>(c.sex)) : Cell{};
            const Cell& agec = m.at(r, static_cast<std::size_t>(c.age));
            const Cell& facc = m.at(r, static_cast<std::size_t>(c.factor));
            if (agec.is_blank() && facc.is_blank()) continue;
            int sex = 0;
            if (!parse_sex(sexc, sex)) {
                throw Error{Err::Value, "row " + std::to_string(r + 1) +
                                            ": sex must be M or F"};
            }
            if (!agec.is_num() || agec.num != std::floor(agec.num) ||
                agec.num < 1 || agec.num > 120) {
                throw Error{Err::Value, "row " + std::to_string(r + 1) +
                                            ": age must be a whole number 1-120"};
            }
            if (!facc.is_num() || facc.num <= 0 || facc.num > 1) {
                throw Error{Err::Value, "row " + std::to_string(r + 1) +
                                            ": factor must be in (0, 1]"};
            }
            std::string ev;
            double km = 0;
            bool have_km = false;
            if (c.event >= 0) {
                const Cell& e = m.at(r, static_cast<std::size_t>(c.event));
                if (e.is_blank()) throw Error{Err::Value, "row " + std::to_string(r + 1) + ": event is blank"};
                if (!parse_distance(e, km, ev)) {
                    throw Error{Err::Value, "row " + std::to_string(r + 1) +
                                                ": unknown event \"" + e.text + "\""};
                }
                have_km = true;
            }
            if (c.distance >= 0) {
                const Cell& d = m.at(r, static_cast<std::size_t>(c.distance));
                if (!parse_distance(d, km, ev)) {
                    throw Error{Err::Value, "row " + std::to_string(r + 1) + ": distance is not a number"};
                }
                have_km = true;
            }
            if (!have_km) throw Error{Err::Value, "no event or distance column"};
            const std::string key = std::to_string(km);   // keyed by distance
            km_of.emplace(key, km);
            const int a = static_cast<int>(agec.num);
            pts[sex][key][a] = facc.num;
            age_union.push_back(a);
            if (c.std_ >= 0) {
                const Cell& s = m.at(r, static_cast<std::size_t>(c.std_));
                if (!s.is_blank()) {
                    double secs = require_time(s, "OpenStd", r);
                    // The standard belongs to the row's sex, not to the
                    // distance: a male 10 km standard is 26:24 and a female one
                    // 28:46. Copying it to the other sex silently graded that
                    // sex against the wrong standard (the first sex listed in
                    // the table won for both). The other sex falls back to the
                    // built-in standard, or fails with a clear message.
                    std_of[sex].emplace(key, secs);
                }
            }
        }
        if (pts.empty()) throw Error{Err::Value, "the table range has no rows"};

        std::sort(age_union.begin(), age_union.end());
        age_union.erase(std::unique(age_union.begin(), age_union.end()), age_union.end());
        if (age_union.size() < 2) {
            throw Error{Err::Value, "a table needs factors at two or more ages"};
        }

        for (auto& kv : km_of) {
            EventRow row;
            row.name = kv.first;
            row.distance_km = kv.second;
            for (int s = 0; s < 2; ++s) {
                auto it = std_of[s].find(kv.first);
                row.std_[s] = it == std_of[s].end()
                                  ? builtin_standard(kv.second, s)
                                  : it->second;
                if (!(row.std_[s] > 0)) {
                    throw Error{Err::Value,
                                "no OpenStd for \"" + kv.first +
                                    "\" and no built-in standard for " +
                                    std::to_string(kv.second) + " km — add an OpenStd column"};
                }
            }
            t.events.push_back(row);
        }
        std::sort(t.events.begin(), t.events.end(),
                  [](const EventRow& a, const EventRow& b) {
                      return a.distance_km < b.distance_km;
                  });

        for (int s = 0; s < 2; ++s) {
            if (pts.count(s) == 0) continue;
            SexTable st;
            st.present = true;
            st.ages = age_union;
            st.n_events = t.events.size();
            st.factors.assign(st.n_events * st.ages.size(), 0.0f);
            for (std::size_t e = 0; e < t.events.size(); ++e) {
                auto pit = pts[s].find(t.events[e].name);
                if (pit == pts[s].end()) {
                    throw Error{Err::Value, "event \"" + t.events[e].name +
                                                "\" has no factors for " +
                                                (s ? "male" : "female") + " rows"};
                }
                std::vector<double> row(st.ages.size(), kNaN);
                for (std::size_t a = 0; a < st.ages.size(); ++a) {
                    auto f = pit->second.find(st.ages[a]);
                    if (f != pit->second.end()) row[a] = f->second;
                }
                if (!fill_sparse(st.ages, row)) {
                    throw Error{Err::Value, "no factors for event \"" +
                                                t.events[e].name + "\""};
                }
                for (std::size_t a = 0; a < st.ages.size(); ++a) {
                    st.factors[e * st.ages.size() + a] = static_cast<float>(row[a]);
                }
            }
            t.sex[s] = std::move(st);
        }
        return t;
    }

    if (!matrix_format) {
        throw Error{Err::Value,
                    "unrecognised table layout: expected a Sex column and either "
                    "numeric age columns or Age+Factor columns"};
    }

    // ---- matrix format: Sex | Event | OpenStd | 5 | 6 | ... | 100 ----------
    struct RowData {
        int sex = 0;
        std::string key;                  // the distance, as a string
        std::string origin;               // as written, for messages
        double km = 0;
        double std_s = 0;                 // 0 = column absent or blank
        std::vector<double> factors;      // one per header age column
    };

    std::vector<int> ages;
    for (auto& ac : c.age_cols) ages.push_back(ac.second);

    std::vector<RowData> rows;
    int last_sex = -1;

    for (std::size_t r = hdr + 1; r < m.rows; ++r) {
        std::string ev;
        double km = 0;
        bool have_km = false;

        if (c.event >= 0) {
            const Cell& e = m.at(r, static_cast<std::size_t>(c.event));
            if (!e.is_blank()) have_km = parse_distance(e, km, ev);
        }
        if (!have_km && c.distance >= 0) {
            const Cell& d = m.at(r, static_cast<std::size_t>(c.distance));
            if (!d.is_blank() && !parse_distance(d, km, ev)) {
                throw Error{Err::Value, "row " + std::to_string(r + 1) +
                                            ": \"" + (d.is_text() ? d.text : "?") +
                                            "\" is not a known event or a distance in km"};
            }
            if (!d.is_blank()) have_km = true;
        }
        if (!have_km) {
            // no event on this row: tolerate a spacer, reject stray factors
            bool stray = false;
            for (auto& ac : c.age_cols) {
                if (!m.at(r, static_cast<std::size_t>(ac.first)).is_blank()) stray = true;
            }
            if (stray) {
                throw Error{Err::Value, "row " + std::to_string(r + 1) +
                                            ": has factors but no event"};
            }
            continue;
        }

        int sex = -1;
        if (c.sex >= 0) {
            const Cell& sc = m.at(r, static_cast<std::size_t>(c.sex));
            if (sc.is_blank()) {
                sex = last_sex;                 // blank sex inherits the row above
            } else if (!parse_sex(sc, sex)) {
                throw Error{Err::Value, "row " + std::to_string(r + 1) +
                                            ": sex must be M or F"};
            }
            if (sex >= 0) last_sex = sex;
        }
        if (sex < 0) {
            throw Error{Err::Value, "row " + std::to_string(r + 1) +
                                        ": the first data row must name a sex"};
        }

        RowData rd;
        rd.sex = sex;
        rd.key = std::to_string(km);                      // keyed by distance
        rd.origin = ev.empty() ? std::to_string(km) : ev;
        rd.km = km;
        if (c.std_ >= 0) {
            const Cell& sc = m.at(r, static_cast<std::size_t>(c.std_));
            if (!sc.is_blank()) rd.std_s = require_time(sc, "OpenStd", r);
        }
        rd.factors.assign(ages.size(), kNaN);
        for (std::size_t k = 0; k < c.age_cols.size(); ++k) {
            const Cell& f = m.at(r, static_cast<std::size_t>(c.age_cols[k].first));
            if (f.is_blank()) continue;
            if (!f.is_num() || f.num <= 0 || f.num > 1) {
                throw Error{Err::Value, "row " + std::to_string(r + 1) + ", age " +
                                            std::to_string(c.age_cols[k].second) +
                                            ": factor must be in (0, 1]"};
            }
            rd.factors[k] = f.num;
        }
        rows.push_back(std::move(rd));
    }
    if (rows.empty()) throw Error{Err::Value, "the table range has no data rows"};

    // one event list for the table, sorted by distance
    std::map<std::string, double> km_of;
    for (const auto& rd : rows) km_of.emplace(rd.key, rd.km);
    std::vector<std::string> keys;
    for (const auto& kv : km_of) keys.push_back(kv.first);
    std::sort(keys.begin(), keys.end(), [&](const std::string& a, const std::string& b) {
        return km_of[a] < km_of[b];
    });
    std::map<std::string, std::size_t> index;
    for (std::size_t i = 0; i < keys.size(); ++i) {
        index[keys[i]] = i;
        EventRow row;
        row.name = keys[i];
        row.distance_km = km_of[keys[i]];
        t.events.push_back(row);
    }

    // open standards: explicit, else built-in for that distance, else shared
    for (const auto& rd : rows) {
        if (rd.std_s > 0) t.events[index[rd.key]].std_[rd.sex] = rd.std_s;
    }
    for (auto& e : t.events) {
        for (int s = 0; s < 2; ++s) {
            if (!(e.std_[s] > 0)) e.std_[s] = builtin_standard(e.distance_km, s);
            if (!(e.std_[s] > 0)) e.std_[s] = e.std_[1 - s];
            if (!(e.std_[s] > 0)) {
                throw Error{Err::Value,
                            "no OpenStd for \"" + e.name +
                                "\" and no built-in standard for " +
                                std::to_string(e.distance_km) +
                                " km — add an OpenStd column"};
            }
        }
    }

    for (int s = 0; s < 2; ++s) {
        bool present = false;
        for (const auto& rd : rows) if (rd.sex == s) { present = true; break; }
        if (!present) continue;
        SexTable st;
        st.present = true;
        st.ages = ages;
        st.n_events = keys.size();
        st.factors.assign(st.n_events * ages.size(), 0.0f);
        for (const auto& rd : rows) {
            if (rd.sex != s) continue;
            std::vector<double> row = rd.factors;
            if (!fill_sparse(ages, row)) {
                throw Error{Err::Value, "no factors for \"" + rd.origin + "\" (" +
                                            (s ? "male" : "female") + " rows)"};
            }
            const std::size_t e = index[rd.key];
            for (std::size_t a = 0; a < ages.size(); ++a) {
                st.factors[e * ages.size() + a] = static_cast<float>(row[a]);
            }
        }
        t.sex[s] = std::move(st);
    }
    return t;
}

std::uint64_t matrix_hash(const Matrix& m) {
    std::uint64_t h = 1469598103934665603ull;
    auto mix = [&h](const void* p, std::size_t n) {
        const auto* b = static_cast<const unsigned char*>(p);
        for (std::size_t i = 0; i < n; ++i) {
            h ^= b[i];
            h *= 1099511628211ull;
        }
    };
    mix(&m.rows, sizeof m.rows);
    mix(&m.cols, sizeof m.cols);
    for (const Cell& c : m.v) {
        const int k = static_cast<int>(c.kind);
        mix(&k, sizeof k);
        if (c.is_num()) {
            mix(&c.num, sizeof c.num);
        } else {
            mix(c.text.data(), c.text.size());
        }
    }
    return h;
}

// ---------------------------------------------------------------------------
// registry
// ---------------------------------------------------------------------------
Registry& Registry::instance() {
    static Registry r;
    return r;
}

Registry::Registry() { ensure_builtins(); }

void Registry::ensure_builtins() {
    if (!builtin_.empty()) return;
    for (int i = 0; i < builtin::n_tables; ++i) {
        const builtin::GenTable& g = builtin::tables[i];
        Table t;
        t.name = g.name;
        t.authority = g.authority;
        t.year = g.year;
        t.source = "builtin";
        for (int e = 0; e < g.sex[1].n_events; ++e) {
            EventRow row;
            row.name = g.sex[1].events[e].name;
            row.distance_km = g.sex[1].events[e].distance_km;
            row.std_[0] = g.sex[1].events[e].open_std_f;
            row.std_[1] = g.sex[1].events[e].open_std_m;
            t.events.push_back(row);
        }
        for (int s = 0; s < 2; ++s) {
            const builtin::GenSex& gs = g.sex[s];
            if (gs.n_events == 0 || gs.factors == nullptr) continue;
            SexTable& st = t.sex[s];
            st.present = true;
            st.ui_age_quirk = true;          // published editions only
            st.ages.assign(gs.ages, gs.ages + gs.n_ages);
            st.n_events = static_cast<std::size_t>(gs.n_events);
            st.factors.assign(gs.factors, gs.factors + gs.n_events * gs.n_ages);
        }
        if (t.year > 0 && (latest_.empty() || t.year > builtin_[latest_].year)) {
            latest_ = t.name;
        }
        builtin_.emplace(t.name, std::move(t));
    }
}

void Registry::add_search_dir(const std::string& dir) {
    if (dir.empty()) return;
    std::lock_guard<std::mutex> lk(mu_);
    for (const auto& d : dirs_) if (d == dir) return;
    dirs_.push_back(dir);
}

std::vector<std::string> Registry::search_dirs() const {
    std::lock_guard<std::mutex> lk(mu_);
    return dirs_;
}

namespace {

// Minimal RFC-4180-ish CSV reader: handles quoted fields and doubled quotes.
bool read_csv(const std::string& path, Matrix& out, std::string& why) {
    std::ifstream f(path, std::ios::binary);
    if (!f) { why = "cannot open " + path; return false; }
    std::vector<std::vector<std::string>> rows;
    std::vector<std::string> row;
    std::string field;
    bool quoted = false, any = false;
    char ch;
    while (f.get(ch)) {
        any = true;
        if (quoted) {
            if (ch == '"') {
                if (f.peek() == '"') { f.get(ch); field.push_back('"'); }
                else quoted = false;
            } else {
                field.push_back(ch);
            }
        } else if (ch == '"') {
            quoted = true;
        } else if (ch == ',') {
            row.push_back(field);
            field.clear();
        } else if (ch == '\n' || ch == '\r') {
            if (ch == '\r' && f.peek() == '\n') f.get(ch);
            row.push_back(field);
            field.clear();
            rows.push_back(row);
            row.clear();
        } else {
            field.push_back(ch);
        }
    }
    if (!any) { why = path + " is empty"; return false; }
    if (!field.empty() || !row.empty()) {
        row.push_back(field);
        rows.push_back(row);
    }
    if (rows.empty()) { why = path + " is empty"; return false; }

    std::size_t cols = 0;
    for (auto& r : rows) cols = std::max(cols, r.size());
    out = Matrix(rows.size(), cols);
    for (std::size_t i = 0; i < rows.size(); ++i) {
        for (std::size_t j = 0; j < rows[i].size(); ++j) {
            const std::string s = trim(rows[i][j]);
            if (s.empty()) continue;
            double v = 0;
            // keep things like "10km" and "40:00" as text; plain numbers as numbers
            if (parse_double(s, v)) out.at(i, j) = Cell::number(v);
            else out.at(i, j) = Cell::string(s);
        }
    }
    return true;
}

std::string join_path(const std::string& dir, const std::string& file) {
    if (dir.empty()) return file;
    const char last = dir.back();
    if (last == '/' || last == '\\') return dir + file;
    return dir + "/" + file;
}

bool file_exists(const std::string& p) {
    std::ifstream f(p, std::ios::binary);
    return static_cast<bool>(f);
}

}  // namespace

bool Registry::has(const std::string& name) {
    try {
        find(name);
        return true;
    } catch (const Error&) {
        return false;
    }
}

const Table& Registry::find(const std::string& raw_name) {
    const std::string name = raw_name.empty() ? latest_ : raw_name;
    {
        std::lock_guard<std::mutex> lk(mu_);
        auto it = builtin_.find(name);
        if (it != builtin_.end()) { ++hit_; return it->second; }
        auto f = file_.find(name);
        if (f != file_.end()) { ++hit_; return f->second; }
        ++miss_;
    }

    // not loaded yet: try <name>.csv in the search dirs
    std::string tried;
    std::vector<std::string> dirs;
    { std::lock_guard<std::mutex> lk(mu_); dirs = dirs_; }
    for (const auto& d : dirs) {
        const std::string path = join_path(d, name + ".csv");
        if (!file_exists(path)) { tried += path + " "; continue; }
        Matrix m;
        std::string why;
        if (!read_csv(path, m, why)) throw Error{Err::Value, why};
        Table t = parse_table(m, name);   // throws Error{Value} with context
        t.source = "file:" + path;
        {
            std::lock_guard<std::mutex> lk(mu_);
            auto ins = file_.emplace(name, std::move(t));
            return ins.first->second;
        }
    }

    std::string known;
    for (const auto& kv : builtin_) known += kv.first + " ";
    {
        std::lock_guard<std::mutex> lk(mu_);
        for (const auto& kv : file_) known += kv.first + " ";
    }
    throw Error{Err::NA, "no table named \"" + name + "\" (known: " + known +
                            "; looked for " + (tried.empty() ? "no search dirs"
                                                             : tried) + ")"};
}

const Table& Registry::adhoc(const Matrix& m, const std::string& label) {
    const std::uint64_t key = matrix_hash(m);
    {
        std::lock_guard<std::mutex> lk(mu_);
        auto it = adhoc_.find(key);
        if (it != adhoc_.end()) {
            ++hit_;
            return it->second;
        }
        ++miss_;
    }
    Table t = parse_table(m, label.empty() ? "adhoc" : label);
    t.source = "adhoc";
    std::lock_guard<std::mutex> lk(mu_);
    auto ins = adhoc_.emplace(key, std::move(t));
    adhoc_order_.push_back(key);
    while (adhoc_order_.size() > adhoc_capacity_ && !adhoc_order_.empty()) {
        const std::uint64_t victim = adhoc_order_.front();
        adhoc_order_.erase(adhoc_order_.begin());
        if (victim != key) adhoc_.erase(victim);
    }
    return ins.first->second;
}

std::vector<std::string> Registry::names() {
    std::vector<std::string> out;
    {
        std::lock_guard<std::mutex> lk(mu_);
        for (const auto& kv : builtin_) out.push_back(kv.first);
        for (const auto& kv : file_) out.push_back(kv.first);
    }
    // Sidecar CSVs appear here once they have been loaded at least once; the
    // add-in's RRAG.TABLES() reports the editions it can serve right now.
    std::sort(out.begin(), out.end());
    out.erase(std::unique(out.begin(), out.end()), out.end());
    return out;
}

CacheStats Registry::stats() const {
    std::lock_guard<std::mutex> lk(mu_);
    CacheStats s;
    s.builtin_tables = builtin_.size();
    s.file_tables = file_.size();
    s.adhoc_entries = adhoc_.size();
    s.hit = hit_;
    s.miss = miss_;
    return s;
}

void Registry::clear() {
    std::lock_guard<std::mutex> lk(mu_);
    file_.clear();
    adhoc_.clear();
    adhoc_order_.clear();
}

void Registry::set_adhoc_capacity(std::size_t n) {
    std::lock_guard<std::mutex> lk(mu_);
    adhoc_capacity_ = n == 0 ? 1 : n;
}

std::size_t Registry::adhoc_capacity() const {
    std::lock_guard<std::mutex> lk(mu_);
    return adhoc_capacity_;
}

double builtin_standard(double distance_km, int sex) {
    Registry& r = Registry::instance();
    const Table& t = r.find("");    // newest edition
    if (!t.sex[sex].present) return 0;
    for (const auto& e : t.events) {
        if (std::fabs(e.distance_km - distance_km) < 1e-3) return e.std_[sex];
    }
    return 0;
}

void init(const std::vector<std::string>& search_dirs) {
    Registry& r = Registry::instance();
    for (const auto& d : search_dirs) r.add_search_dir(d);
}

std::string version_string() {
    Registry& r = Registry::instance();
    const CacheStats s = r.stats();
    std::ostringstream os;
    os << "aggrade-xll " << "2025.1" << " (" << s.builtin_tables
       << " built-in editions)";
    return os.str();
}

}  // namespace ag
