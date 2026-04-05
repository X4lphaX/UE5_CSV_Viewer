/*
 * UE5 CSV Viewer — native C++ acceleration module.
 *
 * Provides three hot-path routines exposed to Python via pybind11:
 *   1. parse_csv_block  — bulk CSV text -> column-major float64 arrays
 *   2. downsample_minmax — min/max envelope decimation for display
 *   3. smooth_moving_avg — O(n) moving average
 */

#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>
#include <pybind11/stl.h>

#include <cstdlib>
#include <cstdint>
#include <cstring>
#include <string>
#include <vector>
#include <algorithm>
#include <cmath>
#include <utility>

namespace py = pybind11;

using idx_t = int64_t;

// ---------------------------------------------------------------------------
// 1. Fast CSV numeric block parser
// ---------------------------------------------------------------------------

static py::tuple parse_csv_block(
        const std::string &text,
        int data_start_line,
        int data_end_line,
        const std::vector<int> &data_col_indices,
        int events_col,
        int num_cols)
{
    // Locate line boundaries once
    std::vector<const char *> line_starts;
    line_starts.reserve(data_end_line + 1);
    const char *p = text.data();
    const char *end = p + text.size();
    line_starts.push_back(p);
    while (p < end) {
        if (*p == '\n') {
            line_starts.push_back(p + 1);
        }
        ++p;
    }
    int total_lines = static_cast<int>(line_starts.size());

    if (data_start_line < 0) data_start_line = 0;
    if (data_end_line > total_lines) data_end_line = total_lines;

    int max_rows = data_end_line - data_start_line;
    int num_data_cols = static_cast<int>(data_col_indices.size());

    std::vector<double> flat(static_cast<size_t>(num_data_cols) * max_rows, 0.0);
    std::vector<std::string> events;
    events.reserve(max_rows);
    int row_count = 0;

    // Build col_index -> array position lookup
    int max_col = 0;
    for (int ci : data_col_indices) max_col = std::max(max_col, ci);
    max_col = std::max(max_col, events_col);
    std::vector<int> col_map(max_col + 1, -1);
    for (int i = 0; i < num_data_cols; ++i) {
        col_map[data_col_indices[i]] = i;
    }

    // Parse rows
    for (int li = data_start_line; li < data_end_line; ++li) {
        if (li >= total_lines) break;
        const char *ls = line_starts[li];
        const char *le;
        if (li + 1 < total_lines) {
            le = line_starts[li + 1];
            if (le > ls && *(le - 1) == '\n') --le;
            if (le > ls && *(le - 1) == '\r') --le;
        } else {
            le = text.data() + text.size();
        }

        if (ls >= le) continue;

        const char *fp = ls;
        int col = 0;
        bool got_event = false;
        std::string event_str;

        while (fp <= le && col <= max_col) {
            const char *fe = fp;
            while (fe < le && *fe != ',') ++fe;

            if (col == events_col) {
                const char *ts = fp;
                const char *te2 = fe;
                while (ts < te2 && (*ts == ' ' || *ts == '\t')) ++ts;
                while (te2 > ts && (*(te2 - 1) == ' ' || *(te2 - 1) == '\t')) --te2;
                event_str.assign(ts, te2);
                got_event = true;
            }

            if (col < static_cast<int>(col_map.size()) && col_map[col] >= 0) {
                if (fp < fe) {
                    char *endptr = nullptr;
                    double val = std::strtod(fp, &endptr);
                    if (endptr > fp) {
                        size_t offset = static_cast<size_t>(col_map[col]) * max_rows + row_count;
                        flat[offset] = val;
                    }
                }
            }

            fp = fe + 1;
            ++col;
        }

        events.push_back(got_event ? std::move(event_str) : std::string());
        ++row_count;
    }

    // Build numpy array
    py::array_t<double> arr({num_data_cols, row_count});
    auto buf = arr.mutable_unchecked<2>();
    for (int c = 0; c < num_data_cols; ++c) {
        const double *src = flat.data() + static_cast<size_t>(c) * max_rows;
        for (int r = 0; r < row_count; ++r) {
            buf(c, r) = src[r];
        }
    }

    return py::make_tuple(arr, events, row_count);
}

// ---------------------------------------------------------------------------
// 2. Min/Max downsampling for display
// ---------------------------------------------------------------------------

static py::tuple downsample_minmax(
        py::array_t<double> x_arr,
        py::array_t<double> y_arr,
        int num_bins)
{
    auto x_buf = x_arr.request();
    auto y_buf = y_arr.request();
    const double *x = static_cast<const double *>(x_buf.ptr);
    const double *y = static_cast<const double *>(y_buf.ptr);
    idx_t n = static_cast<idx_t>(x_buf.shape[0]);

    if (n <= 2 * num_bins || num_bins <= 0) {
        return py::make_tuple(x_arr, y_arr);
    }

    std::vector<double> ox, oy;
    ox.reserve(2 * num_bins + 2);
    oy.reserve(2 * num_bins + 2);

    double x_min = x[0];
    double x_max = x[n - 1];
    double bin_width = (x_max - x_min) / num_bins;

    idx_t i = 0;
    for (int b = 0; b < num_bins; ++b) {
        double bin_end = x_min + (b + 1) * bin_width;

        if (i >= n) break;

        double y_lo = y[i];
        double y_hi = y[i];
        double x_lo = x[i];
        double x_hi = x[i];

        while (i < n && x[i] < bin_end) {
            double yv = y[i];
            if (yv < y_lo) { y_lo = yv; x_lo = x[i]; }
            if (yv > y_hi) { y_hi = yv; x_hi = x[i]; }
            ++i;
        }

        if (x_lo <= x_hi) {
            ox.push_back(x_lo); oy.push_back(y_lo);
            if (x_lo != x_hi) {
                ox.push_back(x_hi); oy.push_back(y_hi);
            }
        } else {
            ox.push_back(x_hi); oy.push_back(y_hi);
            ox.push_back(x_lo); oy.push_back(y_lo);
        }
    }

    idx_t out_n = static_cast<idx_t>(ox.size());
    py::array_t<double> out_x(out_n);
    py::array_t<double> out_y(out_n);
    std::memcpy(out_x.mutable_data(), ox.data(), out_n * sizeof(double));
    std::memcpy(out_y.mutable_data(), oy.data(), out_n * sizeof(double));

    return py::make_tuple(out_x, out_y);
}

// ---------------------------------------------------------------------------
// 3. Fast moving average (smoothing)
// ---------------------------------------------------------------------------

static py::array_t<double> smooth_moving_avg(
        py::array_t<double> data_arr,
        int window)
{
    auto buf = data_arr.request();
    const double *data = static_cast<const double *>(buf.ptr);
    idx_t n = static_cast<idx_t>(buf.shape[0]);

    if (window <= 1 || n == 0) {
        // Return a copy
        py::array_t<double> out(n);
        std::memcpy(out.mutable_data(), data, n * sizeof(double));
        return out;
    }

    py::array_t<double> out(n);
    double *o = out.mutable_data();

    // Prefix sum for O(n) computation
    std::vector<double> prefix(n + 1, 0.0);
    for (idx_t i = 0; i < n; ++i) {
        prefix[i + 1] = prefix[i] + data[i];
    }

    int half = window / 2;
    for (idx_t i = 0; i < n; ++i) {
        idx_t left = std::max(i - half, static_cast<idx_t>(0));
        idx_t right = std::min(i + half, n - 1);
        idx_t count = right - left + 1;
        o[i] = (prefix[right + 1] - prefix[left]) / count;
    }

    return out;
}


// ---------------------------------------------------------------------------
// Module definition
// ---------------------------------------------------------------------------

PYBIND11_MODULE(_native_core, m) {
    m.doc() = "UE5 CSV Viewer native acceleration";

    m.def("parse_csv_block", &parse_csv_block,
          py::arg("text"),
          py::arg("data_start_line"),
          py::arg("data_end_line"),
          py::arg("data_col_indices"),
          py::arg("events_col"),
          py::arg("num_cols"),
          "Parse the numeric data block of a UE5 CSV dump into column-major arrays.");

    m.def("downsample_minmax", &downsample_minmax,
          py::arg("x"), py::arg("y"), py::arg("num_bins"),
          "Min/max envelope downsampling for efficient display.");

    m.def("smooth_moving_avg", &smooth_moving_avg,
          py::arg("data"), py::arg("window"),
          "O(n) moving average smoothing.");
}
