"""
UE5 CSV Profile Parser

Parses Unreal Engine 5 CSV profiling dumps.
Format: first row = headers (starting with "EVENTS"), data rows have empty first column,
last rows contain metadata with [HasHeaderRowAtEnd] marker.

Uses a native C++ backend when available, with a pure-Python fallback.
"""

import numpy as np
from dataclasses import dataclass, field

# Try to load native C++ acceleration
try:
    import _native_core
    HAS_NATIVE = True
except ImportError:
    HAS_NATIVE = False


@dataclass
class ProfileData:
    """Holds parsed CSV profile data."""
    headers: list[str] = field(default_factory=list)
    data: dict[str, np.ndarray] = field(default_factory=dict)
    events: list[str] = field(default_factory=list)
    metadata: dict[str, str] = field(default_factory=dict)
    frame_count: int = 0
    filename: str = ""

    # Predefined channel groups for the UI
    TIMING_CHANNELS = [
        "FrameTime", "GameThreadTime", "RenderThreadTime", "GPUTime",
        "RenderThreadTime_CriticalPath", "GameThreadTime_CriticalPath",
        "RHIThreadTime", "InputLatencyTime", "MaxFrameTime",
    ]

    MEMORY_CHANNELS = [
        "MemoryFreeMB", "PhysicalUsedMB", "VirtualUsedMB",
        "ExtendedUsedMB", "SystemMaxMB",
    ]

    CPU_CHANNELS = ["CPUUsage_Process", "CPUUsage_Idle"]

    def get_channel_groups(self) -> dict[str, list[str]]:
        """Return channels organized by prefix groups, only including columns that exist."""
        groups: dict[str, list[str]] = {}

        timing = [c for c in self.TIMING_CHANNELS if c in self.data]
        if timing:
            groups["Timing"] = timing

        mem = [c for c in self.MEMORY_CHANNELS if c in self.data]
        if mem:
            groups["Memory"] = mem

        cpu = [c for c in self.CPU_CHANNELS if c in self.data]
        if cpu:
            groups["CPU"] = cpu

        prefix_map: dict[str, list[str]] = {}
        skip = set(self.TIMING_CHANNELS + self.MEMORY_CHANNELS + self.CPU_CHANNELS + ["EVENTS"])
        for h in self.headers:
            if h in skip:
                continue
            if "/" in h:
                parts = h.split("/")
                prefix = "/".join(parts[:2]) if len(parts) > 1 else parts[0]
                prefix_map.setdefault(prefix, []).append(h)
            else:
                prefix_map.setdefault("Other", []).append(h)

        for prefix in sorted(prefix_map.keys()):
            groups[prefix] = sorted(prefix_map[prefix])

        return groups


def _parse_header(line: str) -> list[str]:
    """Parse the CSV header line, handling quoted fields."""
    headers = []
    in_quotes = False
    current = []
    for ch in line:
        if ch == '"':
            in_quotes = not in_quotes
        elif ch == ',' and not in_quotes:
            headers.append(''.join(current).strip())
            current = []
        else:
            current.append(ch)
    headers.append(''.join(current).strip())
    return headers


def _find_data_bounds(lines: list[str]) -> tuple[int, int, dict[str, str]]:
    """Scan from the end to find data region and parse metadata."""
    data_end = len(lines)
    metadata = {}

    for i in range(len(lines) - 1, 0, -1):
        stripped = lines[i].strip()
        if not stripped:
            data_end = i
            continue
        if stripped.startswith("[HasHeaderRowAtEnd]"):
            parts = stripped.split(",")
            j = 1
            while j < len(parts) - 1:
                key = parts[j].strip("[]")
                val = parts[j + 1] if j + 1 < len(parts) else ""
                metadata[key] = val
                j += 2
            data_end = i
            continue
        if stripped.startswith("EVENTS,") and i > 1:
            data_end = i
            continue
        break

    return 1, data_end, metadata


def _parse_block_python(raw: str, lines: list[str], data_start: int, data_end: int,
                        data_col_indices: list[int], events_col: int):
    """Pure-Python fallback for numeric data parsing."""
    max_rows = data_end - data_start
    num_data_cols = len(data_col_indices)
    data_arrays = np.zeros((num_data_cols, max_rows), dtype=np.float64)
    events = []
    row_count = 0

    for i in range(data_start, data_end):
        line = lines[i]
        if not line or line.isspace():
            continue

        fields = line.split(",")

        if events_col < len(fields):
            events.append(fields[events_col].strip())
        else:
            events.append("")

        for arr_idx, col_idx in enumerate(data_col_indices):
            if col_idx < len(fields):
                val = fields[col_idx]
                if val:
                    try:
                        data_arrays[arr_idx, row_count] = float(val)
                    except ValueError:
                        pass
        row_count += 1

    if row_count < max_rows:
        data_arrays = data_arrays[:, :row_count]

    return data_arrays, events, row_count


def parse_csv(filepath: str) -> ProfileData:
    """Parse a UE5 CSV profile file and return structured data."""
    with open(filepath, "r", encoding="utf-8-sig") as f:
        raw = f.read()

    lines = raw.split("\n")
    if not lines:
        raise ValueError("Empty CSV file")

    headers = _parse_header(lines[0])
    events_col = headers.index("EVENTS") if "EVENTS" in headers else 0
    data_col_indices = [i for i, h in enumerate(headers) if h != "EVENTS"]

    data_start, data_end, metadata = _find_data_bounds(lines)

    if HAS_NATIVE:
        data_arrays, events, row_count = _native_core.parse_csv_block(
            raw, data_start, data_end,
            data_col_indices, events_col, len(headers),
        )
    else:
        data_arrays, events, row_count = _parse_block_python(
            raw, lines, data_start, data_end,
            data_col_indices, events_col,
        )

    profile = ProfileData()
    profile.headers = headers
    profile.events = list(events)
    profile.frame_count = row_count
    profile.filename = filepath
    profile.metadata = metadata

    for arr_idx, col_idx in enumerate(data_col_indices):
        profile.data[headers[col_idx]] = np.ascontiguousarray(data_arrays[arr_idx])

    return profile
