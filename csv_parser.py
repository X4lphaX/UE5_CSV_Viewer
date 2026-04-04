"""
UE5 CSV Profile Parser

Parses Unreal Engine 5 CSV profiling dumps.
Format: first row = headers (starting with "EVENTS"), data rows have empty first column,
last rows contain metadata with [HasHeaderRowAtEnd] marker.
"""

import csv
import io
import numpy as np
from dataclasses import dataclass, field
from typing import Optional


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
                prefix = h.split("/")[0]
                if len(h.split("/")) > 1:
                    prefix = "/".join(h.split("/")[:2])
                prefix_map.setdefault(prefix, []).append(h)
            else:
                prefix_map.setdefault("Other", []).append(h)

        for prefix in sorted(prefix_map.keys()):
            groups[prefix] = sorted(prefix_map[prefix])

        return groups


def parse_csv(filepath: str) -> ProfileData:
    """Parse a UE5 CSV profile file and return structured data."""
    with open(filepath, "r", encoding="utf-8-sig") as f:
        raw = f.read()

    lines = raw.strip().split("\n")
    if not lines:
        raise ValueError("Empty CSV file")

    # Parse header row
    header_line = lines[0]
    reader = csv.reader(io.StringIO(header_line))
    headers = next(reader)

    # Find data rows (skip metadata at end)
    data_lines = []
    events = []
    metadata = {}
    metadata_started = False

    for i, line in enumerate(lines[1:], 1):
        stripped = line.strip()
        if not stripped:
            continue

        # Check for metadata marker
        if stripped.startswith("[HasHeaderRowAtEnd]"):
            # Parse metadata from this line
            parts = stripped.split(",")
            j = 1
            while j < len(parts) - 1:
                key = parts[j].strip("[]")
                val = parts[j + 1] if j + 1 < len(parts) else ""
                metadata[key] = val
                j += 2
            metadata_started = True
            continue

        # Skip duplicate header row at end
        if stripped.startswith("EVENTS,") and i > 1:
            continue

        if metadata_started:
            continue

        # Parse data row
        reader = csv.reader(io.StringIO(stripped))
        row = next(reader)

        # First column is EVENTS (usually empty or contains event text)
        if len(row) > 0:
            events.append(row[0])

        data_lines.append(row)

    # Convert to numpy arrays per column
    profile = ProfileData()
    profile.headers = headers
    profile.events = events
    profile.frame_count = len(data_lines)
    profile.filename = filepath

    for col_idx, header in enumerate(headers):
        if header == "EVENTS":
            continue
        values = []
        for row in data_lines:
            if col_idx < len(row):
                try:
                    values.append(float(row[col_idx]))
                except (ValueError, IndexError):
                    values.append(0.0)
            else:
                values.append(0.0)
        profile.data[header] = np.array(values, dtype=np.float64)

    profile.metadata = metadata
    return profile
