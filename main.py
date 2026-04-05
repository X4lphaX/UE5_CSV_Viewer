"""
UE5 CSV Profile Viewer
A desktop application for viewing and comparing Unreal Engine 5 CSV profile dumps.
"""

import sys
import os
import numpy as np
import pyqtgraph as pg
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QFileDialog, QPushButton, QLabel, QScrollArea, QCheckBox,
    QSlider, QGroupBox, QSplitter, QFrame, QTreeWidget, QTreeWidgetItem,
    QHeaderView, QToolButton, QSizePolicy, QGridLayout, QSpinBox,
    QDoubleSpinBox, QTabWidget, QTableWidget, QTableWidgetItem,
    QLineEdit, QComboBox, QScrollBar,
)
from PySide6.QtCore import Qt, Signal, QPointF
from PySide6.QtGui import QColor, QPen, QFont, QIcon, QPainter, QAction

from csv_parser import parse_csv, ProfileData


class CustomViewBox(pg.ViewBox):
    """Custom ViewBox: left-drag = rect zoom, middle-drag = pan, scroll = zoom."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setMouseMode(pg.ViewBox.RectMode)
        self._middle_dragging = False
        self._middle_drag_start = None

    def mousePressEvent(self, ev):
        if ev.button() == Qt.MouseButton.MiddleButton:
            self._middle_dragging = True
            self._middle_drag_start = ev.pos()
            ev.accept()
        else:
            super().mousePressEvent(ev)

    def mouseMoveEvent(self, ev):
        if self._middle_dragging and self._middle_drag_start is not None:
            delta = ev.pos() - self._middle_drag_start
            self._middle_drag_start = ev.pos()
            # Translate the view
            tr = self.viewRect()
            x_scale = tr.width() / self.width()
            y_scale = tr.height() / self.height()
            self.translateBy(x=-delta.x() * x_scale, y=delta.y() * y_scale)
            ev.accept()
        else:
            super().mouseMoveEvent(ev)

    def mouseReleaseEvent(self, ev):
        if ev.button() == Qt.MouseButton.MiddleButton:
            self._middle_dragging = False
            self._middle_drag_start = None
            ev.accept()
        else:
            super().mouseReleaseEvent(ev)

# --- Color Palette ---
CHANNEL_COLORS = {
    "FrameTime": "#4A9EFF",
    "GameThreadTime": "#FF6B6B",
    "RenderThreadTime": "#4ECDC4",
    "GPUTime": "#FFE66D",
    "RenderThreadTime_CriticalPath": "#45B7D1",
    "GameThreadTime_CriticalPath": "#F7797D",
    "RHIThreadTime": "#C56CF0",
    "InputLatencyTime": "#FF9FF3",
    "MaxFrameTime": "#FFFFFF",
    "MemoryFreeMB": "#2ECC71",
    "PhysicalUsedMB": "#E74C3C",
    "VirtualUsedMB": "#3498DB",
    "CPUUsage_Process": "#E67E22",
    "CPUUsage_Idle": "#95A5A6",
}

# Generate colors for channels not in the predefined map
def get_channel_color(name: str, index: int = 0) -> QColor:
    if name in CHANNEL_COLORS:
        return QColor(CHANNEL_COLORS[name])
    # Generate a distinct color from index using golden ratio
    hue = (index * 137.508) % 360
    return QColor.fromHsvF(hue / 360.0, 0.7, 0.9)


DARK_BG = "#1E1E2E"
DARK_PANEL = "#2A2A3C"
DARK_BORDER = "#3A3A4C"
DARK_TEXT = "#CDD6F4"
DARK_ACCENT = "#89B4FA"
DARK_HOVER = "#45475A"

STYLESHEET = f"""
QMainWindow, QWidget {{
    background-color: {DARK_BG};
    color: {DARK_TEXT};
    font-family: "Segoe UI", sans-serif;
    font-size: 12px;
}}
QPushButton {{
    background-color: {DARK_PANEL};
    border: 1px solid {DARK_BORDER};
    border-radius: 4px;
    padding: 6px 14px;
    color: {DARK_TEXT};
}}
QPushButton:hover {{
    background-color: {DARK_HOVER};
    border-color: {DARK_ACCENT};
}}
QPushButton:pressed {{
    background-color: {DARK_ACCENT};
    color: #1E1E2E;
}}
QGroupBox {{
    border: 1px solid {DARK_BORDER};
    border-radius: 4px;
    margin-top: 8px;
    padding-top: 16px;
    font-weight: bold;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 4px;
}}
QSlider::groove:horizontal {{
    height: 4px;
    background: {DARK_BORDER};
    border-radius: 2px;
}}
QSlider::handle:horizontal {{
    background: {DARK_ACCENT};
    width: 14px;
    height: 14px;
    margin: -5px 0;
    border-radius: 7px;
}}
QSlider::groove:vertical {{
    width: 4px;
    background: {DARK_BORDER};
    border-radius: 2px;
}}
QSlider::handle:vertical {{
    background: {DARK_ACCENT};
    width: 14px;
    height: 14px;
    margin: 0 -5px;
    border-radius: 7px;
}}
QScrollArea {{
    border: none;
}}
QScrollBar:horizontal {{
    background: {DARK_BG};
    height: 14px;
    border: none;
}}
QScrollBar::handle:horizontal {{
    background: {DARK_HOVER};
    border-radius: 4px;
    min-width: 20px;
}}
QScrollBar::handle:horizontal:hover {{
    background: {DARK_ACCENT};
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0px;
}}
QScrollBar:vertical {{
    background: {DARK_BG};
    width: 14px;
    border: none;
}}
QScrollBar::handle:vertical {{
    background: {DARK_HOVER};
    border-radius: 4px;
    min-height: 20px;
}}
QScrollBar::handle:vertical:hover {{
    background: {DARK_ACCENT};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}
QTreeWidget {{
    background-color: {DARK_PANEL};
    border: 1px solid {DARK_BORDER};
    border-radius: 4px;
    outline: none;
}}
QTreeWidget::item {{
    padding: 2px;
}}
QTreeWidget::item:hover {{
    background-color: {DARK_HOVER};
}}
QTreeWidget::item:selected {{
    background-color: {DARK_ACCENT};
    color: #1E1E2E;
}}
QHeaderView::section {{
    background-color: {DARK_PANEL};
    border: 1px solid {DARK_BORDER};
    padding: 4px;
}}
QTabWidget::pane {{
    border: 1px solid {DARK_BORDER};
    background-color: {DARK_PANEL};
}}
QTabBar::tab {{
    background-color: {DARK_BG};
    border: 1px solid {DARK_BORDER};
    padding: 6px 12px;
    margin-right: 2px;
}}
QTabBar::tab:selected {{
    background-color: {DARK_PANEL};
    border-bottom: 2px solid {DARK_ACCENT};
}}
QTableWidget {{
    background-color: {DARK_PANEL};
    border: 1px solid {DARK_BORDER};
    gridline-color: {DARK_BORDER};
}}
QTableWidget::item {{
    padding: 2px 6px;
}}
QLineEdit {{
    background-color: {DARK_PANEL};
    border: 1px solid {DARK_BORDER};
    border-radius: 4px;
    padding: 4px 8px;
    color: {DARK_TEXT};
}}
QSpinBox, QDoubleSpinBox {{
    background-color: {DARK_PANEL};
    border: 1px solid {DARK_BORDER};
    border-radius: 4px;
    padding: 2px 6px;
    color: {DARK_TEXT};
}}
QComboBox {{
    background-color: {DARK_PANEL};
    border: 1px solid {DARK_BORDER};
    border-radius: 4px;
    padding: 4px 8px;
    color: {DARK_TEXT};
}}
QSplitter::handle {{
    background-color: {DARK_BORDER};
}}
QCheckBox {{
    spacing: 6px;
}}
QCheckBox::indicator {{
    width: 14px;
    height: 14px;
    border: 1px solid {DARK_BORDER};
    border-radius: 3px;
    background-color: {DARK_PANEL};
}}
QCheckBox::indicator:checked {{
    background-color: {DARK_ACCENT};
    border-color: {DARK_ACCENT};
}}
"""


class ChannelToggleWidget(QWidget):
    """A single channel toggle with color swatch and checkbox."""
    toggled = Signal(str, bool)

    def __init__(self, name: str, color: QColor, checked: bool = False, parent=None):
        super().__init__(parent)
        self.channel_name = name
        layout = QHBoxLayout(self)
        layout.setContentsMargins(2, 1, 2, 1)
        layout.setSpacing(4)

        # Color swatch
        self.swatch = QLabel()
        self.swatch.setFixedSize(12, 12)
        self.swatch.setStyleSheet(
            f"background-color: {color.name()}; border-radius: 2px; border: 1px solid #555;"
        )
        layout.addWidget(self.swatch)

        # Checkbox
        self.checkbox = QCheckBox(self._short_name(name))
        self.checkbox.setChecked(checked)
        self.checkbox.stateChanged.connect(self._on_toggle)
        layout.addWidget(self.checkbox, 1)

    def _short_name(self, name: str) -> str:
        """Shorten long channel names for display."""
        parts = name.split("/")
        if len(parts) > 2:
            return parts[-1]
        return name

    def _on_toggle(self, state):
        self.toggled.emit(self.channel_name, state == Qt.CheckState.Checked.value)

    def set_checked(self, checked: bool):
        self.checkbox.setChecked(checked)


class LayerPanel(QWidget):
    """Photoshop-style layer toggle panel with grouped channels."""
    channel_toggled = Signal(str, bool)
    smoothing_changed = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(260)
        self.setMaximumWidth(350)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # Search filter
        self.search = QLineEdit()
        self.search.setPlaceholderText("Filter channels...")
        self.search.textChanged.connect(self._filter_channels)
        layout.addWidget(self.search)

        # Smoothing
        smooth_group = QGroupBox("Smoothing")
        smooth_layout = QHBoxLayout(smooth_group)
        self.smooth_slider = QSlider(Qt.Orientation.Horizontal)
        self.smooth_slider.setRange(1, 50)
        self.smooth_slider.setValue(1)
        self.smooth_slider.valueChanged.connect(self._on_smooth_change)
        smooth_layout.addWidget(self.smooth_slider)
        self.smooth_label = QLabel("Off")
        self.smooth_label.setFixedWidth(45)
        smooth_layout.addWidget(self.smooth_label)
        layout.addWidget(smooth_group)

        # Quick toggles
        btn_layout = QHBoxLayout()
        self.btn_all = QPushButton("All On")
        self.btn_all.clicked.connect(lambda: self._set_all(True))
        self.btn_none = QPushButton("All Off")
        self.btn_none.clicked.connect(lambda: self._set_all(False))
        self.btn_timing = QPushButton("Timing")
        self.btn_timing.clicked.connect(self._select_timing)
        btn_layout.addWidget(self.btn_all)
        btn_layout.addWidget(self.btn_none)
        btn_layout.addWidget(self.btn_timing)
        layout.addLayout(btn_layout)

        # Scrollable channel list
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.channel_container = QWidget()
        self.channel_layout = QVBoxLayout(self.channel_container)
        self.channel_layout.setContentsMargins(0, 0, 0, 0)
        self.channel_layout.setSpacing(0)
        self.channel_layout.addStretch()
        scroll.setWidget(self.channel_container)
        layout.addWidget(scroll, 1)

        self.toggles: dict[str, ChannelToggleWidget] = {}
        self.group_widgets: dict[str, QGroupBox] = {}

    def populate(self, profile: ProfileData, color_map: dict[str, QColor]):
        """Populate the layer panel from profile data."""
        # Clear existing
        for t in self.toggles.values():
            t.setParent(None)
            t.deleteLater()
        for g in self.group_widgets.values():
            g.setParent(None)
            g.deleteLater()
        self.toggles.clear()
        self.group_widgets.clear()

        # Remove stretch
        while self.channel_layout.count():
            item = self.channel_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        groups = profile.get_channel_groups()
        default_on = set(ProfileData.TIMING_CHANNELS)

        for group_name, channels in groups.items():
            group_box = QGroupBox(group_name)
            group_box.setCheckable(True)
            group_box.setChecked(True)
            group_layout = QVBoxLayout(group_box)
            group_layout.setContentsMargins(4, 4, 4, 4)
            group_layout.setSpacing(0)

            group_box.toggled.connect(lambda checked, gn=group_name: self._toggle_group(gn, checked))

            for ch in channels:
                color = color_map.get(ch, QColor("#888888"))
                toggle = ChannelToggleWidget(ch, color, checked=(ch in default_on))
                toggle.toggled.connect(self._on_channel_toggle)
                group_layout.addWidget(toggle)
                self.toggles[ch] = toggle

            self.channel_layout.addWidget(group_box)
            self.group_widgets[group_name] = group_box

        self.channel_layout.addStretch()

    def _on_channel_toggle(self, name: str, checked: bool):
        self.channel_toggled.emit(name, checked)

    def _on_smooth_change(self, value: int):
        if value <= 1:
            self.smooth_label.setText("Off")
        else:
            self.smooth_label.setText(f"{value}")
        self.smoothing_changed.emit(value)

    def _set_all(self, checked: bool):
        for toggle in self.toggles.values():
            toggle.set_checked(checked)

    def _select_timing(self):
        timing_set = set(ProfileData.TIMING_CHANNELS)
        for name, toggle in self.toggles.items():
            toggle.set_checked(name in timing_set)

    def _toggle_group(self, group_name: str, checked: bool):
        groups = {}
        for name, toggle in self.toggles.items():
            # Find which group this belongs to
            for gn, gw in self.group_widgets.items():
                if toggle.parent() and toggle.parent().parent() == gw:
                    groups.setdefault(gn, []).append(toggle)
        if group_name in groups:
            for toggle in groups[group_name]:
                toggle.set_checked(checked)

    def _filter_channels(self, text: str):
        text = text.lower()
        for name, toggle in self.toggles.items():
            toggle.setVisible(text == "" or text in name.lower())

    def get_enabled_channels(self) -> set[str]:
        return {name for name, t in self.toggles.items() if t.checkbox.isChecked()}


class FrameDetailPanel(QWidget):
    """Panel showing detailed frame data when a frame is clicked."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        self.title_label = QLabel("Frame Details")
        self.title_label.setStyleSheet(f"font-size: 14px; font-weight: bold; color: {DARK_ACCENT};")
        layout.addWidget(self.title_label)

        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        # Timing tab
        self.timing_table = QTableWidget()
        self.timing_table.setColumnCount(2)
        self.timing_table.setHorizontalHeaderLabels(["Metric", "Value"])
        self.timing_table.horizontalHeader().setStretchLastSection(True)
        self.timing_table.verticalHeader().setVisible(False)
        self.tabs.addTab(self.timing_table, "Timing")

        # Threads tab
        self.threads_table = QTableWidget()
        self.threads_table.setColumnCount(2)
        self.threads_table.setHorizontalHeaderLabels(["Metric", "Value (ms)"])
        self.threads_table.horizontalHeader().setStretchLastSection(True)
        self.threads_table.verticalHeader().setVisible(False)
        self.tabs.addTab(self.threads_table, "Threads")

        # Memory tab
        self.memory_table = QTableWidget()
        self.memory_table.setColumnCount(2)
        self.memory_table.setHorizontalHeaderLabels(["Metric", "Value"])
        self.memory_table.horizontalHeader().setStretchLastSection(True)
        self.memory_table.verticalHeader().setVisible(False)
        self.tabs.addTab(self.memory_table, "Memory")

        # Rendering tab
        self.render_table = QTableWidget()
        self.render_table.setColumnCount(2)
        self.render_table.setHorizontalHeaderLabels(["Metric", "Value"])
        self.render_table.horizontalHeader().setStretchLastSection(True)
        self.render_table.verticalHeader().setVisible(False)
        self.tabs.addTab(self.render_table, "Rendering")

        # Physics tab
        self.physics_table = QTableWidget()
        self.physics_table.setColumnCount(2)
        self.physics_table.setHorizontalHeaderLabels(["Metric", "Value"])
        self.physics_table.horizontalHeader().setStretchLastSection(True)
        self.physics_table.verticalHeader().setVisible(False)
        self.tabs.addTab(self.physics_table, "Physics/Ticks")

        # All data tab
        self.all_table = QTableWidget()
        self.all_table.setColumnCount(2)
        self.all_table.setHorizontalHeaderLabels(["Channel", "Value"])
        self.all_table.horizontalHeader().setStretchLastSection(True)
        self.all_table.verticalHeader().setVisible(False)
        self.tabs.addTab(self.all_table, "All Data")

    def show_frame(self, profile: ProfileData, frame_idx: int, profile_label: str = ""):
        """Display all data for the given frame index."""
        if frame_idx < 0 or frame_idx >= profile.frame_count:
            return

        label = f"Frame {frame_idx}"
        if profile_label:
            label += f" ({profile_label})"
        event = profile.events[frame_idx] if frame_idx < len(profile.events) else ""
        if event:
            label += f" - {event}"
        self.title_label.setText(label)

        def fill_table(table: QTableWidget, keys: list[str]):
            rows = []
            for k in keys:
                if k in profile.data:
                    val = profile.data[k][frame_idx]
                    rows.append((k, f"{val:.4f}" if val != int(val) else f"{int(val)}"))
            table.setRowCount(len(rows))
            for i, (k, v) in enumerate(rows):
                table.setItem(i, 0, QTableWidgetItem(k))
                table.setItem(i, 1, QTableWidgetItem(v))
            table.resizeColumnsToContents()

        # Timing
        fill_table(self.timing_table, [
            "FrameTime", "GameThreadTime", "RenderThreadTime", "GPUTime",
            "GameThreadTime_CriticalPath", "RenderThreadTime_CriticalPath",
            "RHIThreadTime", "InputLatencyTime", "MaxFrameTime",
            "CPUUsage_Process", "CPUUsage_Idle",
        ])

        # Threads detail
        gt_keys = [h for h in profile.headers if h.startswith("Exclusive/GameThread/")]
        fill_table(self.threads_table, gt_keys)

        # Memory
        fill_table(self.memory_table, [
            "MemoryFreeMB", "PhysicalUsedMB", "VirtualUsedMB",
            "ExtendedUsedMB", "SystemMaxMB",
            "GPUMem/LocalBudgetMB", "GPUMem/LocalUsedMB",
            "GPUMem/SystemBudgetMB", "GPUMem/SystemUsedMB",
            "TextureStreaming/StreamingPool", "TextureStreaming/CachedMips",
            "TextureStreaming/WantedMips",
        ])

        # Rendering
        fill_table(self.render_table, [
            "RHI/DrawCalls", "RHI/PrimitivesDrawn",
            "RenderTargetPool/PeakUsedMB", "RenderTargetPoolSize",
            "RDGCount/Passes", "RDGCount/Buffers", "RDGCount/Textures",
            "LightCount/All", "LightCount/Batched", "LightCount/Unbatched",
            "LightCount/UpdatedShadowMaps", "ShadowCacheUsageMB",
            "GPUSceneInstanceCount",
            "PSO/PSOMisses", "PSO/PSOMissesOnHitch",
            "Shaders/ShaderMemoryMB", "Shaders/NumShadersLoaded",
        ])

        # Physics / Ticks
        phys_keys = [h for h in profile.headers if h.startswith("ChaosPhysics/") or h.startswith("Ticks/") or h.startswith("ActorCount/")]
        fill_table(self.physics_table, phys_keys)

        # All data
        all_keys = [h for h in profile.headers if h != "EVENTS"]
        fill_table(self.all_table, all_keys)


class ProfileChart(pg.PlotWidget):
    """Interactive chart widget with zoom, pan, drag-select, and crosshair."""
    frame_clicked = Signal(int)
    frame_hovered = Signal(int)

    def __init__(self, parent=None):
        vb = CustomViewBox()
        super().__init__(parent, background=DARK_BG, viewBox=vb)

        self.setMouseTracking(True)
        self.showGrid(x=True, y=True, alpha=0.15)
        self.setLabel("bottom", "Frame")
        self.setLabel("left", "Value (ms)")

        # Left-drag = rect zoom (RectMode), scroll = zoom, middle-drag = pan (handled by CustomViewBox)
        self.setMouseEnabled(x=True, y=True)

        # Crosshair
        self.vline = pg.InfiniteLine(angle=90, movable=False,
                                      pen=pg.mkPen("#FFFFFF", width=1, style=Qt.PenStyle.DashLine))
        self.hline = pg.InfiniteLine(angle=0, movable=False,
                                      pen=pg.mkPen("#FFFFFF", width=1, style=Qt.PenStyle.DashLine))
        self.addItem(self.vline, ignoreBounds=True)
        self.addItem(self.hline, ignoreBounds=True)
        self.vline.setVisible(False)
        self.hline.setVisible(False)

        # Click marker
        self.click_line = pg.InfiniteLine(angle=90, movable=False,
                                           pen=pg.mkPen(DARK_ACCENT, width=2))
        self.addItem(self.click_line, ignoreBounds=True)
        self.click_line.setVisible(False)

        # Tooltip
        self.tooltip_label = pg.TextItem(anchor=(0, 1), fill=pg.mkBrush(DARK_PANEL + "E0"),
                                          border=pg.mkPen(DARK_BORDER))
        self.tooltip_label.setZValue(1000)
        self.addItem(self.tooltip_label, ignoreBounds=True)
        self.tooltip_label.setVisible(False)

        # Data storage
        self.curves: dict[str, pg.PlotDataItem] = {}
        self.curves_secondary: dict[str, pg.PlotDataItem] = {}
        self.profiles: list[ProfileData] = []
        self.color_map: dict[str, QColor] = {}
        self.enabled_channels: set[str] = set()
        self._sorted_enabled: list[str] = []  # cached sorted list
        self.vertical_scale: float = 1.0
        self.shift_offset: int = 0
        self.smoothing_window: int = 1
        self._smooth_cache: dict[tuple, np.ndarray] = {}
        self._smooth_cache_secondary: dict[tuple, np.ndarray] = {}
        self._secondary_x_base: np.ndarray | None = None

        # Connect mouse signals
        self.scene().sigMouseMoved.connect(self._on_mouse_moved)
        self.scene().sigMouseClicked.connect(self._on_mouse_clicked)

        # Origin axis lines (zero lines)
        self.zero_h = pg.InfiniteLine(pos=0, angle=0, movable=False,
                                       pen=pg.mkPen("#888888", width=1.5))
        self.zero_v = pg.InfiniteLine(pos=0, angle=90, movable=False,
                                       pen=pg.mkPen("#888888", width=1.5))
        self.addItem(self.zero_h, ignoreBounds=True)
        self.addItem(self.zero_v, ignoreBounds=True)

        # Target lines (16.67ms = 60fps, 33.33ms = 30fps)
        self.target_60 = pg.InfiniteLine(pos=16.67, angle=0, movable=False,
                                          pen=pg.mkPen("#2ECC71", width=1, style=Qt.PenStyle.DotLine),
                                          label="60 FPS", labelOpts={"position": 0.98, "color": "#2ECC71"})
        self.target_30 = pg.InfiniteLine(pos=33.33, angle=0, movable=False,
                                          pen=pg.mkPen("#E74C3C", width=1, style=Qt.PenStyle.DotLine),
                                          label="30 FPS", labelOpts={"position": 0.98, "color": "#E74C3C"})
        self.addItem(self.target_60, ignoreBounds=True)
        self.addItem(self.target_30, ignoreBounds=True)

    def load_profile(self, profile: ProfileData, is_secondary: bool = False):
        """Load a profile and create plot curves."""
        if not is_secondary:
            if len(self.profiles) == 0:
                self.profiles.append(profile)
            else:
                self.profiles[0] = profile
            self._rebuild_curves()
        else:
            if len(self.profiles) < 2:
                self.profiles.append(profile)
            else:
                self.profiles[1] = profile
            self._rebuild_secondary_curves()

    def _rebuild_curves(self):
        """Rebuild all primary curves."""
        for curve in self.curves.values():
            self.removeItem(curve)
        self.curves.clear()
        self._invalidate_smooth_cache(secondary=False)

        if not self.profiles:
            return

        profile = self.profiles[0]
        x = np.arange(profile.frame_count, dtype=np.float64)

        color_idx = 0
        for header in profile.headers:
            if header == "EVENTS":
                continue
            color = get_channel_color(header, color_idx)
            self.color_map[header] = color
            pen = pg.mkPen(color, width=2)
            curve = self.plot(x, self._get_smoothed(header, secondary=False),
                             pen=pen, name=header)
            curve.setVisible(header in self.enabled_channels)
            self.curves[header] = curve
            color_idx += 1

    def _rebuild_secondary_curves(self):
        """Rebuild secondary (comparison) curves with dotted lines."""
        for curve in self.curves_secondary.values():
            self.removeItem(curve)
        self.curves_secondary.clear()
        self._secondary_x_base = None

        if len(self.profiles) < 2:
            return

        profile = self.profiles[1]
        self._secondary_x_base = np.arange(profile.frame_count, dtype=np.float64)
        x = self._secondary_x_base + self.shift_offset

        color_idx = 0
        for header in profile.headers:
            if header == "EVENTS":
                continue
            color = QColor(get_channel_color(header, color_idx))
            color.setAlpha(153)  # ~60% opacity
            pen = pg.mkPen(color, width=2, style=Qt.PenStyle.DashLine)
            curve = self.plot(x, self._get_smoothed(header, secondary=True),
                             pen=pen)
            curve.setVisible(header in self.enabled_channels)
            self.curves_secondary[header] = curve
            color_idx += 1

    def set_channel_visible(self, channel: str, visible: bool):
        if visible:
            self.enabled_channels.add(channel)
        else:
            self.enabled_channels.discard(channel)
        self._sorted_enabled = sorted(self.enabled_channels)

        if channel in self.curves:
            self.curves[channel].setVisible(visible)
        if channel in self.curves_secondary:
            self.curves_secondary[channel].setVisible(visible)

    def set_vertical_scale(self, scale: float):
        self.vertical_scale = scale
        # Instead of scaling data, adjust the Y-axis view range
        # Higher scale = zoom in on Y axis (smaller range visible)
        if self.profiles:
            # Find max value across all visible channels to set a reasonable base range
            max_val = 0
            for ch in self.enabled_channels:
                if ch in self.profiles[0].data:
                    ch_max = np.max(np.abs(self.profiles[0].data[ch]))
                    max_val = max(max_val, ch_max)
            if max_val == 0:
                max_val = 100
            # Base range shows full data; scale zooms in
            y_range = max_val * 1.1 / scale
            self.setYRange(-y_range * 0.05, y_range, padding=0)

    def _get_smoothed(self, header: str, secondary: bool = False) -> np.ndarray:
        """Return smoothed data, using cache to avoid recomputation."""
        cache = self._smooth_cache_secondary if secondary else self._smooth_cache
        key = (header, self.smoothing_window)
        if key in cache:
            return cache[key]
        idx = 1 if secondary else 0
        if idx >= len(self.profiles) or header not in self.profiles[idx].data:
            return np.array([])
        raw = self.profiles[idx].data[header]
        if self.smoothing_window <= 1:
            result = raw
        else:
            kernel = np.ones(self.smoothing_window) / self.smoothing_window
            result = np.convolve(raw, kernel, mode='same')
        cache[key] = result
        return result

    def _invalidate_smooth_cache(self, secondary: bool = False):
        if secondary:
            self._smooth_cache_secondary.clear()
        else:
            self._smooth_cache.clear()

    def set_smoothing(self, window: int):
        self.smoothing_window = window
        self._smooth_cache.clear()
        self._smooth_cache_secondary.clear()
        self._rebuild_curves()
        if len(self.profiles) > 1:
            self._rebuild_secondary_curves()

    def set_shift_offset(self, offset: int):
        self.shift_offset = offset
        if len(self.profiles) > 1 and self._secondary_x_base is not None:
            # Update X data in-place on existing curves instead of full rebuild
            x = self._secondary_x_base + offset
            for header, curve in self.curves_secondary.items():
                y = self._get_smoothed(header, secondary=True)
                curve.setData(x, y)
        elif len(self.profiles) > 1:
            self._rebuild_secondary_curves()

    def _on_mouse_moved(self, pos):
        mouse_point = self.getViewBox().mapSceneToView(pos)
        frame_idx = int(round(mouse_point.x()))

        if not self.profiles:
            self.vline.setVisible(False)
            self.hline.setVisible(False)
            self.tooltip_label.setVisible(False)
            return

        profile = self.profiles[0]
        if frame_idx < 0 or frame_idx >= profile.frame_count:
            self.tooltip_label.setVisible(False)
            self.vline.setVisible(False)
            self.hline.setVisible(False)
            return

        self.vline.setPos(mouse_point.x())
        self.hline.setPos(mouse_point.y())
        self.vline.setVisible(True)
        self.hline.setVisible(True)

        # Build tooltip text with visible channel values
        parts = [f"<b>Frame {frame_idx}</b>"]

        event = profile.events[frame_idx] if frame_idx < len(profile.events) else ""
        if event:
            parts.append(f"<i>{event}</i>")

        has_secondary = len(self.profiles) > 1
        p2 = self.profiles[1] if has_secondary else None
        shifted_idx = frame_idx - self.shift_offset if has_secondary else -1

        for ch in self._sorted_enabled:
            ch_data = profile.data.get(ch)
            if ch_data is None or frame_idx >= len(ch_data):
                continue
            val = ch_data[frame_idx]
            color_name = self.color_map[ch].name() if ch in self.color_map else "#888888"
            parts.append(
                f'<span style="color:{color_name};">■ {ch}: {val:.3f}</span>'
            )

            if p2 is not None:
                p2_data = p2.data.get(ch)
                if p2_data is not None and 0 <= shifted_idx < p2.frame_count:
                    val2 = p2_data[shifted_idx]
                    diff = val - val2
                    sign = "+" if diff >= 0 else ""
                    parts.append(
                        f'<span style="color:{color_name};">  ⌐ Compare: {val2:.3f} ({sign}{diff:.3f})</span>'
                    )

        html = "<br>".join(parts)
        self.tooltip_label.setHtml(html)
        self.tooltip_label.setPos(mouse_point)
        self.tooltip_label.setVisible(True)
        self.frame_hovered.emit(frame_idx)

    def _on_mouse_clicked(self, event):
        if event.button() == Qt.MouseButton.LeftButton and not event.modifiers():
            mouse_point = self.getViewBox().mapSceneToView(event.scenePos())
            frame_idx = int(round(mouse_point.x()))
            if self.profiles and 0 <= frame_idx < self.profiles[0].frame_count:
                self.click_line.setPos(frame_idx)
                self.click_line.setVisible(True)
                self.frame_clicked.emit(frame_idx)

    def reset_zoom(self):
        self.enableAutoRange()


class MainWindow(QMainWindow):
    """Main application window."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("UE5 CSV Profile Viewer")
        self.setMinimumSize(1280, 720)
        self.resize(1600, 900)

        self.profiles: list[ProfileData] = []
        self.color_map: dict[str, QColor] = {}

        self._build_ui()
        self._connect_signals()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(4, 4, 4, 4)
        main_layout.setSpacing(4)

        # Top toolbar
        toolbar = QHBoxLayout()
        self.btn_load_primary = QPushButton("Load CSV")
        self.btn_load_primary.setToolTip("Load primary CSV profile")
        self.btn_load_secondary = QPushButton("Load Comparison CSV")
        self.btn_load_secondary.setToolTip("Load a second CSV for comparison")
        self.btn_clear_secondary = QPushButton("Clear Comparison")
        self.btn_clear_secondary.setEnabled(False)
        self.btn_reset_zoom = QPushButton("Reset Zoom")

        self.file_label = QLabel("No file loaded")
        self.file_label.setStyleSheet(f"color: {DARK_ACCENT};")

        toolbar.addWidget(self.btn_load_primary)
        toolbar.addWidget(self.btn_load_secondary)
        toolbar.addWidget(self.btn_clear_secondary)
        toolbar.addWidget(self.btn_reset_zoom)
        toolbar.addStretch()
        toolbar.addWidget(self.file_label)
        main_layout.addLayout(toolbar)

        # Main content splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left: Layer panel
        self.layer_panel = LayerPanel()
        splitter.addWidget(self.layer_panel)

        # Center: Chart area with vertical scale on the left and shift slider on the bottom
        chart_container = QWidget()
        chart_grid = QGridLayout(chart_container)
        chart_grid.setContentsMargins(0, 0, 0, 0)
        chart_grid.setSpacing(2)

        # Chart interaction hint (top, spanning columns 1-2)
        hint = QLabel("Scroll: Zoom | Middle-click drag: Pan | Left-click drag: Select region to zoom | Click: Select frame")
        hint.setStyleSheet(f"color: #666; font-size: 10px; padding: 2px;")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        chart_grid.addWidget(hint, 0, 1)

        # Vertical scale slider (left of chart)
        scale_widget = QWidget()
        scale_vlayout = QVBoxLayout(scale_widget)
        scale_vlayout.setContentsMargins(2, 0, 2, 0)
        scale_vlayout.setSpacing(2)
        self.scale_label = QLabel("1.0x")
        self.scale_label.setStyleSheet(f"color: {DARK_TEXT}; font-size: 10px;")
        self.scale_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        scale_vlayout.addWidget(self.scale_label)
        self.scale_slider = QSlider(Qt.Orientation.Vertical)
        self.scale_slider.setRange(1, 10000)
        self.scale_slider.setValue(100)
        self.scale_slider.setFixedWidth(20)
        self.scale_slider.setToolTip("Vertical Scale")
        scale_vlayout.addWidget(self.scale_slider, 1)
        scale_widget.setFixedWidth(30)
        chart_grid.addWidget(scale_widget, 1, 0)

        # Chart (center)
        self.chart = ProfileChart()
        chart_grid.addWidget(self.chart, 1, 1)

        # Shift slider (below chart, same width) with arrow buttons
        self.shift_widget = QWidget()
        shift_layout = QHBoxLayout(self.shift_widget)
        shift_layout.setContentsMargins(0, 2, 0, 0)
        shift_layout.setSpacing(4)
        self.shift_left_btn = QToolButton()
        self.shift_left_btn.setText("\u25C0")
        self.shift_left_btn.setFixedSize(18, 18)
        self.shift_left_btn.setToolTip("Shift left 1 frame")
        self.shift_left_btn.setAutoRepeat(True)
        self.shift_left_btn.setAutoRepeatInterval(100)
        self.shift_slider = QSlider(Qt.Orientation.Horizontal)
        self.shift_slider.setRange(-500, 500)
        self.shift_slider.setValue(0)
        self.shift_slider.setFixedHeight(16)
        self.shift_right_btn = QToolButton()
        self.shift_right_btn.setText("\u25B6")
        self.shift_right_btn.setFixedSize(18, 18)
        self.shift_right_btn.setToolTip("Shift right 1 frame")
        self.shift_right_btn.setAutoRepeat(True)
        self.shift_right_btn.setAutoRepeatInterval(100)
        self.shift_label = QLabel("0 frames")
        self.shift_label.setStyleSheet(f"color: {DARK_TEXT}; font-size: 10px;")
        self.shift_label.setFixedWidth(65)
        self.shift_reset = QPushButton("Reset")
        self.shift_reset.setFixedWidth(45)
        self.shift_reset.setFixedHeight(18)
        self.shift_reset.setStyleSheet("font-size: 10px; padding: 1px 4px;")
        shift_layout.addWidget(QLabel("Shift:"))
        shift_layout.addWidget(self.shift_left_btn)
        shift_layout.addWidget(self.shift_slider, 1)
        shift_layout.addWidget(self.shift_right_btn)
        shift_layout.addWidget(self.shift_label)
        shift_layout.addWidget(self.shift_reset)
        self.shift_widget.setVisible(False)
        chart_grid.addWidget(self.shift_widget, 2, 1)

        # Horizontal scrollbar (below shift slider / chart)
        self.h_scrollbar = QScrollBar(Qt.Orientation.Horizontal)
        self.h_scrollbar.setFixedHeight(14)
        self.h_scrollbar.setRange(0, 0)
        chart_grid.addWidget(self.h_scrollbar, 3, 1)

        # Vertical scrollbar (right of chart)
        self.v_scrollbar = QScrollBar(Qt.Orientation.Vertical)
        self.v_scrollbar.setFixedWidth(14)
        self.v_scrollbar.setRange(0, 0)
        chart_grid.addWidget(self.v_scrollbar, 1, 2)

        # Make the chart row stretch
        chart_grid.setRowStretch(1, 1)

        splitter.addWidget(chart_container)

        # Right: Frame detail panel
        self.detail_panel = FrameDetailPanel()
        self.detail_panel.setMinimumWidth(280)
        self.detail_panel.setMaximumWidth(450)
        splitter.addWidget(self.detail_panel)

        splitter.setSizes([280, 900, 350])
        main_layout.addWidget(splitter, 1)

        # Status bar
        self.statusBar().showMessage("Ready - Load a CSV file to begin")
        self.statusBar().setStyleSheet(f"color: {DARK_TEXT}; background: {DARK_PANEL};")

    def _connect_signals(self):
        self.btn_load_primary.clicked.connect(lambda: self._load_csv(False))
        self.btn_load_secondary.clicked.connect(lambda: self._load_csv(True))
        self.btn_clear_secondary.clicked.connect(self._clear_secondary)
        self.btn_reset_zoom.clicked.connect(self.chart.reset_zoom)

        self.layer_panel.channel_toggled.connect(self.chart.set_channel_visible)
        self.scale_slider.valueChanged.connect(self._on_scale_change)
        self.layer_panel.smoothing_changed.connect(self.chart.set_smoothing)

        self.shift_slider.valueChanged.connect(self._on_shift_changed)
        self.shift_reset.clicked.connect(lambda: self.shift_slider.setValue(0))
        self.shift_left_btn.clicked.connect(lambda: self.shift_slider.setValue(self.shift_slider.value() - 1))
        self.shift_right_btn.clicked.connect(lambda: self.shift_slider.setValue(self.shift_slider.value() + 1))

        # Scrollbars for chart panning
        self.h_scrollbar.valueChanged.connect(self._on_h_scroll)
        self.v_scrollbar.valueChanged.connect(self._on_v_scroll)
        self.chart.getViewBox().sigRangeChanged.connect(self._on_chart_range_changed)

        self.chart.frame_clicked.connect(self._on_frame_clicked)

    def _load_csv(self, is_secondary: bool):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open UE5 CSV Profile", "",
            "CSV Files (*.csv);;All Files (*)"
        )
        if not path:
            return

        try:
            profile = parse_csv(path)
        except Exception as e:
            self.statusBar().showMessage(f"Error loading CSV: {e}")
            return

        if not is_secondary:
            self.profiles = [profile]
            # Build color map
            self.color_map.clear()
            color_idx = 0
            for h in profile.headers:
                if h == "EVENTS":
                    continue
                self.color_map[h] = get_channel_color(h, color_idx)
                color_idx += 1

            self.layer_panel.populate(profile, self.color_map)

            # Set default enabled channels to timing
            default_channels = set(ProfileData.TIMING_CHANNELS) & set(profile.data.keys())
            self.chart.enabled_channels = default_channels
            self.chart.color_map = self.color_map

            self.chart.load_profile(profile, is_secondary=False)

            # Apply initial visibility
            for ch in profile.data:
                self.chart.set_channel_visible(ch, ch in default_channels)

            self.chart.reset_zoom()

            fname = os.path.basename(path)
            self.file_label.setText(f"Primary: {fname} ({profile.frame_count} frames)")
            self.statusBar().showMessage(
                f"Loaded {fname}: {profile.frame_count} frames, {len(profile.data)} channels"
            )

            # Show first frame details
            if profile.frame_count > 0:
                self.detail_panel.show_frame(profile, 0, "Primary")

        else:
            if not self.profiles:
                self.statusBar().showMessage("Load a primary CSV first")
                return

            if len(self.profiles) < 2:
                self.profiles.append(profile)
            else:
                self.profiles[1] = profile

            self.chart.load_profile(profile, is_secondary=True)

            # Apply current visibility to secondary curves
            for ch in profile.data:
                self.chart.set_channel_visible(ch, ch in self.chart.enabled_channels)

            self.btn_clear_secondary.setEnabled(True)
            self.shift_widget.setVisible(True)

            # Update shift slider range
            max_shift = max(self.profiles[0].frame_count, profile.frame_count)
            self.shift_slider.setRange(-max_shift, max_shift)

            fname = os.path.basename(path)
            self.file_label.setText(
                self.file_label.text() + f" | Compare: {fname} ({profile.frame_count} frames)"
            )
            self.statusBar().showMessage(f"Loaded comparison: {fname}")

    def _clear_secondary(self):
        if len(self.profiles) > 1:
            self.profiles.pop()
        # Remove secondary curves
        for curve in self.chart.curves_secondary.values():
            self.chart.removeItem(curve)
        self.chart.curves_secondary.clear()
        self.chart.profiles = self.profiles.copy()

        self.btn_clear_secondary.setEnabled(False)
        self.shift_widget.setVisible(False)
        self.shift_slider.setValue(0)

        # Update label
        if self.profiles:
            fname = os.path.basename(self.profiles[0].filename)
            self.file_label.setText(f"Primary: {fname} ({self.profiles[0].frame_count} frames)")

    def _on_scale_change(self, value: int):
        scale = value / 100.0
        self.scale_label.setText(f"{scale:.1f}x")
        self.chart.set_vertical_scale(scale)

    def _on_shift_changed(self, value: int):
        self.shift_label.setText(f"{value} frames")
        self.chart.set_shift_offset(value)

    def _on_frame_clicked(self, frame_idx: int):
        if self.profiles:
            self.detail_panel.show_frame(self.profiles[0], frame_idx, "Primary")
        self.statusBar().showMessage(f"Selected frame {frame_idx}")

    # --- Scrollbar sync ---
    def _update_scrollbars(self):
        """Update scrollbar ranges and positions to reflect the current chart view."""
        if not self.profiles:
            return

        profile = self.profiles[0]
        vb = self.chart.getViewBox()
        view_range = vb.viewRange()
        x_min, x_max = view_range[0]
        y_min, y_max = view_range[1]

        # Horizontal scrollbar: full data range is 0..frame_count
        data_width = profile.frame_count
        view_width = x_max - x_min
        if view_width < data_width:
            page = int(view_width)
            h_max = int(data_width - view_width)
            self.h_scrollbar.blockSignals(True)
            self.h_scrollbar.setRange(0, h_max)
            self.h_scrollbar.setPageStep(max(1, page))
            self.h_scrollbar.setSingleStep(1)
            self.h_scrollbar.setValue(max(0, int(x_min)))
            self.h_scrollbar.blockSignals(False)
        else:
            self.h_scrollbar.blockSignals(True)
            self.h_scrollbar.setRange(0, 0)
            self.h_scrollbar.blockSignals(False)

        # Vertical scrollbar: estimate full Y range from visible channels
        full_y_min = 0
        full_y_max = 100
        for ch in self.chart.enabled_channels:
            if ch in profile.data:
                ch_max = float(np.max(profile.data[ch]))
                full_y_max = max(full_y_max, ch_max * 1.1)

        view_height = y_max - y_min
        data_height = full_y_max - full_y_min
        if view_height < data_height:
            scale = 1000  # integer precision
            page = int(view_height * scale)
            v_max = int((data_height - view_height) * scale)
            self.v_scrollbar.blockSignals(True)
            self.v_scrollbar.setRange(0, max(0, v_max))
            self.v_scrollbar.setPageStep(max(1, page))
            self.v_scrollbar.setSingleStep(max(1, page // 20))
            # Invert: scrollbar top = high Y values
            val = int((full_y_max - y_max) * scale)
            self.v_scrollbar.setValue(max(0, min(v_max, val)))
            self.v_scrollbar.blockSignals(False)
        else:
            self.v_scrollbar.blockSignals(True)
            self.v_scrollbar.setRange(0, 0)
            self.v_scrollbar.blockSignals(False)

    def _on_chart_range_changed(self):
        self._update_scrollbars()

    def _on_h_scroll(self, value: int):
        vb = self.chart.getViewBox()
        view_range = vb.viewRange()
        view_width = view_range[0][1] - view_range[0][0]
        vb.setXRange(value, value + view_width, padding=0)

    def _on_v_scroll(self, value: int):
        if not self.profiles:
            return
        profile = self.profiles[0]
        full_y_max = 100
        for ch in self.chart.enabled_channels:
            if ch in profile.data:
                ch_max = float(np.max(profile.data[ch]))
                full_y_max = max(full_y_max, ch_max * 1.1)

        vb = self.chart.getViewBox()
        view_range = vb.viewRange()
        view_height = view_range[1][1] - view_range[1][0]
        scale = 1000
        # Invert: scrollbar value 0 = top of data
        y_top = full_y_max - value / scale
        y_bottom = y_top - view_height
        vb.setYRange(y_bottom, y_top, padding=0)


def main():
    # High DPI support
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(STYLESHEET)

    # Set app icon if available
    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
