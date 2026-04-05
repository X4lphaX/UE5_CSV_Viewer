"""
UE5 CSV Profile Parser

Parses Unreal Engine 5 CSV profiling dumps.
Format: first row = headers (starting with "EVENTS"), data rows have empty first column,
last rows contain metadata with [HasHeaderRowAtEnd] marker.
"""

import numpy as np
from dataclasses import dataclass, field


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

        # Primary timing
        timing = [c for c in self.TIMING_CHANNELS if c in self.data]
        if timing:
            groups["Timing"] = timing

        # Memory
        mem = [c for c in self.MEMORY_CHANNELS if c in self.data]
        if mem:
            groups["Memory"] = mem

        # CPU
        cpu = [c for c in self.CPU_CHANNELS if c in self.data]
        if cpu:
            groups["CPU"] = cpu

        # Auto-group by prefix
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


def parse_csv(filepath: str) -> ProfileData:
    """Parse a UE5 CSV profile file and return structured data."""
    with open(filepath, "r", encoding="utf-8-sig") as f:
        raw = f.read()

    lines = raw.split("\n")
    if not lines:
        raise ValueError("Empty CSV file")

    # Parse header row
    headers = _parse_header(lines[0])
    num_cols = len(headers)

    # Find the EVENTS column index
    events_col = headers.index("EVENTS") if "EVENTS" in headers else 0

    # Identify data columns (non-EVENTS)
    data_col_indices = [i for i, h in enumerate(headers) if h != "EVENTS"]

    # Pre-scan to count data rows and find metadata boundary
    data_start = 1
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

    # Pre-allocate numpy arrays and parse in a single pass
    # Estimate row count (upper bound)
    max_rows = data_end - data_start
    data_arrays = np.zeros((len(data_col_indices), max_rows), dtype=np.float64)
    events = []
    row_count = 0

    for i in range(data_start, data_end):
        line = lines[i]
        if not line or line.isspace():
            continue

        # Fast split — CSV data rows in UE5 profiles don't use quoting for numeric fields
        fields = line.split(",")

        # Extract event
        if events_col < len(fields):
            events.append(fields[events_col].strip())
        else:
            events.append("")

        # Parse numeric columns directly into pre-allocated array
        for arr_idx, col_idx in enumerate(data_col_indices):
            if col_idx < len(fields):
                val = fields[col_idx]
                if val:
                    try:
                        data_arrays[arr_idx, row_count] = float(val)
                    except ValueError:
                        pass  # stays 0.0

        row_count += 1

    # Trim to actual row count
    if row_count < max_rows:
        data_arrays = data_arrays[:, :row_count]

    # Build profile
    profile = ProfileData()
    profile.headers = headers
    profile.events = events
    profile.frame_count = row_count
    profile.filename = filepath
    profile.metadata = metadata

    for arr_idx, col_idx in enumerate(data_col_indices):
        profile.data[headers[col_idx]] = data_arrays[arr_idx]

    return profile
