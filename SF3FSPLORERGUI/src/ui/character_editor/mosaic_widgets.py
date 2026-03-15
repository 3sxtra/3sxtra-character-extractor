"""
Mosaic widgets for displaying character frames in grid layouts.

This module contains FrameMosaicWidget for flat frame display and
OrganisedFrameMosaicWidget for sequence-grouped display.
"""

import os

from PyQt6.QtCore import QEvent, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QImage, QPixmap
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLayout,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from SF3FSPLORERGUI.src.utils.image_crop import auto_crop_pixmap

from .flow_layout import FlowLayout


class FrameMosaicWidget(QWidget):
    """Scrollable widget displaying all character frames in a flowing layout."""

    frame_clicked = pyqtSignal(int)  # Emits frame index when clicked

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.frames_dir: str | None = None
        self.total_frames = 0
        self.frame_pixmaps: list[tuple[int, QPixmap]] = []
        self.frame_labels: list[QLabel] = []
        self.thumbnail_size = 64
        self.background_color = QColor(30, 30, 30)

        # UI elements initialized in setup_ui
        self.scroll_area: QScrollArea
        self.flow_container: QWidget
        self.flow_layout: QVBoxLayout
        self.info_label: QLabel

        self.setup_ui()

    def setup_ui(self) -> None:
        """Set up the scrollable flow layout."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Scroll area - vertical only
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setStyleSheet("QScrollArea { border: none; }")

        # Container widget for flow layout
        self.flow_container = QWidget()
        self.flow_container.setStyleSheet(f"background-color: {self.background_color.name()};")
        self.flow_layout = QVBoxLayout(self.flow_container)
        self.flow_layout.setSpacing(0)
        self.flow_layout.setContentsMargins(0, 0, 0, 0)
        self.flow_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.scroll_area.setWidget(self.flow_container)
        layout.addWidget(self.scroll_area)

        # Info label
        self.info_label = QLabel("No frames loaded")
        self.info_label.setStyleSheet("color: #888888; padding: 4px;")
        layout.addWidget(self.info_label)

    def set_background_color(self, color: QColor) -> None:
        """Set the background color of the mosaic."""
        self.background_color = color
        self.flow_container.setStyleSheet(f"background-color: {color.name()};")

    def set_zoom(self, zoom: float) -> None:
        """Set the zoom level for thumbnails.

        Args:
            zoom: Zoom factor (1-8), where 1 = 64px base size
        """
        new_size = int(64 * zoom)
        if new_size != self.thumbnail_size:
            self.thumbnail_size = new_size
            # Reload frames with new size if we have a directory loaded
            if self.frames_dir and self.total_frames > 0:
                self.load_frames(self.frames_dir, self.total_frames)

    def load_frames(self, frames_dir: str, total_frames: int) -> None:
        """Load frames from directory and cache pixmaps (synchronous fallback)."""
        self.frames_dir = frames_dir
        self.total_frames = total_frames
        self.frame_pixmaps.clear()
        self._clear_layout()

        if total_frames == 0:
            self.info_label.setText("No frames loaded")
            return

        # Load and cache all cropped pixmaps
        for i in range(total_frames):
            frame_path = os.path.join(frames_dir, f"frame_{i}.png")
            if os.path.exists(frame_path):
                pixmap = QPixmap(frame_path)
                if not pixmap.isNull():
                    cropped = auto_crop_pixmap(pixmap)
                    # Always scale to target thumbnail size
                    if cropped.height() != self.thumbnail_size:
                        cropped = cropped.scaledToHeight(
                            self.thumbnail_size,
                            Qt.TransformationMode.FastTransformation,
                        )
                    self.frame_pixmaps.append((i, cropped))

        self.info_label.setText(f"{len(self.frame_pixmaps)} frames loaded")
        self._reflow_layout()
        # Deferred reflow to ensure viewport is ready
        QTimer.singleShot(0, self._reflow_layout)

    def set_preloaded_frames(
        self, frames_dir: str, total_frames: int, preloaded: list[tuple[int, QImage]]
    ) -> None:
        """Display frames from pre-loaded QImage data (from background worker).

        Converts QImages to QPixmaps on the main thread and displays them.
        This avoids redundant disk I/O and numpy processing.

        Args:
            frames_dir: Source frames directory path
            total_frames: Total frame count
            preloaded: List of (frame_index, QImage) tuples from worker
        """
        self.frames_dir = frames_dir
        self.total_frames = total_frames
        self.frame_pixmaps.clear()
        self._clear_layout()

        for frame_idx, qimage in preloaded:
            pixmap = QPixmap.fromImage(qimage)
            if not pixmap.isNull():
                self.frame_pixmaps.append((frame_idx, pixmap))

        self.info_label.setText(f"{len(self.frame_pixmaps)} frames loaded")
        self._reflow_layout()
        QTimer.singleShot(0, self._reflow_layout)

    def resizeEvent(self, event) -> None:  # noqa: N802
        """Handle resize to reflow the layout."""
        super().resizeEvent(event)
        if self.frame_pixmaps:
            self._reflow_layout()

    def showEvent(self, event) -> None:  # noqa: N802
        """Handle show event to reflow when tab becomes visible."""
        super().showEvent(event)
        if self.frame_pixmaps:
            # Deferred to ensure geometry is ready
            QTimer.singleShot(0, self._reflow_layout)

    def eventFilter(self, obj, event) -> bool:  # noqa: N802
        """Handle click events on frame labels."""
        if event.type() == QEvent.Type.MouseButtonPress:
            frame_idx = obj.property("frame_index")
            if frame_idx is not None:
                self.frame_clicked.emit(int(frame_idx))
                return True
        return super().eventFilter(obj, event)

    def _clear_layout(self) -> None:
        """Clear all widgets from the flow layout."""
        for label in self.frame_labels:
            label.removeEventFilter(self)
            label.deleteLater()
        self.frame_labels.clear()

        # Clear row layouts
        while self.flow_layout.count():
            item = self.flow_layout.takeAt(0)
            if item is None:
                continue
            widget = item.widget()
            if widget:
                widget.deleteLater()
            else:
                layout = item.layout()
                if layout:
                    self._clear_nested_layout(layout)

    def _clear_nested_layout(self, layout: QLayout) -> None:
        """Recursively clear a nested layout."""
        while layout.count():
            item = layout.takeAt(0)
            if item is None:
                continue
            widget = item.widget()
            if widget:
                widget.deleteLater()
            else:
                nested_layout = item.layout()
                if nested_layout:
                    self._clear_nested_layout(nested_layout)

    def _reflow_layout(self) -> None:
        """Reflow all frames based on current viewport width."""
        self._clear_layout()

        if not self.frame_pixmaps:
            return

        viewport = self.scroll_area.viewport()
        available_width = viewport.width() if viewport else 0
        if available_width <= 0:
            available_width = 800  # Default fallback

        current_row = QHBoxLayout()
        current_row.setSpacing(0)
        current_row.setContentsMargins(0, 0, 0, 0)
        current_row_width = 0

        for frame_idx, pixmap in self.frame_pixmaps:
            label = self._create_frame_label(pixmap, frame_idx)
            label_width = pixmap.width()

            # Check if we need to start a new row
            if current_row_width + label_width > available_width and current_row_width > 0:
                # Finalize current row
                current_row.addStretch()
                self.flow_layout.addLayout(current_row)

                # Start new row
                current_row = QHBoxLayout()
                current_row.setSpacing(0)
                current_row.setContentsMargins(0, 0, 0, 0)
                current_row_width = 0

            current_row.addWidget(label)
            self.frame_labels.append(label)
            current_row_width += label_width

        # Add the last row
        if current_row.count() > 0:
            current_row.addStretch()
            self.flow_layout.addLayout(current_row)

        # Add stretch at bottom
        self.flow_layout.addStretch()

    def _create_frame_label(self, pixmap: QPixmap, frame_index: int) -> QLabel:
        """Create a clickable label for a frame thumbnail."""
        label = QLabel()
        label.setStyleSheet(
            "QLabel { border: none; padding: 0px; margin: 0px; }QLabel:hover { background-color: #0078d4; }"
        )
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setToolTip(f"Frame {frame_index}")
        label.setCursor(Qt.CursorShape.PointingHandCursor)

        # Set the pre-processed pixmap
        label.setPixmap(pixmap)

        # Store frame index and make clickable via event filter
        label.setProperty("frame_index", frame_index)
        label.installEventFilter(self)

        return label


class OrganisedFrameMosaicWidget(QWidget):
    """Scrollable widget displaying frames grouped by sequence."""

    frame_clicked = pyqtSignal(int)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.frames_dir: str | None = None
        self.sequences_data: list[dict] = []
        self.thumbnail_size = 64
        self.background_color = QColor(30, 30, 30)
        self.frame_pixmaps_cache: dict[int, QPixmap] = {}
        self._frame_labels: list[QLabel] = []  # Track labels for cleanup

        # UI Elements initialized in setup_ui
        self.scroll_area: QScrollArea
        self.main_container: QWidget
        self.main_layout: QVBoxLayout
        self.info_label: QLabel

        self.setup_ui()

    def setup_ui(self) -> None:
        """Set up the scrollable vertical layout."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        # Vertical scroll only
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setStyleSheet("QScrollArea { border: none; }")

        self.main_container = QWidget()
        self.main_container.setStyleSheet(f"background-color: {self.background_color.name()};")

        self.main_layout = QVBoxLayout(self.main_container)
        self.main_layout.setContentsMargins(10, 10, 10, 10)
        self.main_layout.setSpacing(10)
        self.main_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.scroll_area.setWidget(self.main_container)
        layout.addWidget(self.scroll_area)

        self.info_label = QLabel("No sequences loaded")
        self.info_label.setStyleSheet("color: #888888; padding: 4px;")
        layout.addWidget(self.info_label)

    def set_background_color(self, color: QColor) -> None:
        """Set background color."""
        self.background_color = color
        self.main_container.setStyleSheet(f"background-color: {color.name()};")

    def set_zoom(self, zoom: float) -> None:
        """Set the zoom level for thumbnails.

        Args:
            zoom: Zoom factor (1-8), where 1 = 64px base size
        """
        new_size = int(64 * zoom)
        if new_size != self.thumbnail_size:
            self.thumbnail_size = new_size
            # Clear cache and reload with new size if we have data
            self.frame_pixmaps_cache.clear()
            if self.sequences_data and self.frames_dir:
                self.load_sequences(self.sequences_data, self.frames_dir)

    def load_sequences(self, sequences_data: list[dict], frames_dir: str) -> None:
        """Load sequences and display them grouped."""
        self.sequences_data = sequences_data
        self.frames_dir = frames_dir

        # Clear existing
        self._clear_layout()
        self.frame_pixmaps_cache.clear()

        if not sequences_data:
            self.info_label.setText("No sequences loaded")
            return

        total_seqs = len(sequences_data)
        self.info_label.setText(f"{total_seqs} sequences loaded")

        self._populate_ui()

    def eventFilter(self, obj, event) -> bool:  # noqa: N802
        """Handle click events on frame labels."""
        if event.type() == QEvent.Type.MouseButtonPress:
            frame_idx = obj.property("frame_index")
            if frame_idx is not None:
                self.frame_clicked.emit(int(frame_idx))
                return True
        return super().eventFilter(obj, event)

    def _clear_layout(self) -> None:
        """Remove all child widgets."""
        # Clean up event filters
        for label in self._frame_labels:
            label.removeEventFilter(self)
        self._frame_labels.clear()

        while self.main_layout.count():
            item = self.main_layout.takeAt(0)
            if item is None:
                continue
            widget = item.widget()
            if widget:
                widget.deleteLater()
            else:
                layout = item.layout()
                if layout:
                    self._clear_nested_layout(layout)

    def _clear_nested_layout(self, layout: QLayout) -> None:
        """Recursively clear a nested layout."""
        while layout.count():
            item = layout.takeAt(0)
            if item is None:
                continue
            widget = item.widget()
            if widget:
                widget.deleteLater()
            else:
                nested_layout = item.layout()
                if nested_layout:
                    self._clear_nested_layout(nested_layout)

    def _populate_ui(self) -> None:
        """Create widgets for each sequence."""
        if not self.frames_dir:
            return

        for i, seq in enumerate(self.sequences_data):
            seq_name = seq.get("name", f"Sequence {i}")
            frames = seq.get("frames", [])

            # Extract just indices if they are tuples
            frame_indices: list[int] = []
            if frames:
                if isinstance(frames[0], (list, tuple)):
                    frame_indices = [int(f[0]) for f in frames]
                else:
                    frame_indices = [int(f) for f in frames]

            if not frame_indices:
                continue

            # Section Container
            section = QWidget()
            section_layout = QVBoxLayout(section)
            section_layout.setContentsMargins(0, 0, 0, 0)
            section_layout.setSpacing(5)

            # Header
            header = QLabel(f"{seq_name} ({len(frame_indices)} frames)")
            header.setStyleSheet(
                "font-weight: bold; color: #dddddd; padding: 5px; background-color: #3d3d3d; border-radius: 4px;"
            )
            section_layout.addWidget(header)

            # Flow Container for Frames
            flow_container = QWidget()
            flow_layout = FlowLayout(flow_container, margin=0, spacing=2)

            # Add frames
            for f_idx in frame_indices:
                pixmap = self._get_cached_pixmap(f_idx)
                if pixmap:
                    label = self._create_frame_label(pixmap, f_idx)
                    flow_layout.addWidget(label)

            section_layout.addWidget(flow_container)
            self.main_layout.addWidget(section)

        self.main_layout.addStretch()

    def _get_cached_pixmap(self, frame_idx: int) -> QPixmap | None:
        """Get or load pixmap with caching and auto-crop."""
        if frame_idx in self.frame_pixmaps_cache:
            return self.frame_pixmaps_cache[frame_idx]

        if not self.frames_dir:
            return None

        path = os.path.join(self.frames_dir, f"frame_{frame_idx}.png")
        if os.path.exists(path):
            pix = QPixmap(path)
            if not pix.isNull():
                cropped = auto_crop_pixmap(pix)
                # Always scale to target thumbnail size
                if cropped.height() != self.thumbnail_size:
                    cropped = cropped.scaledToHeight(self.thumbnail_size, Qt.TransformationMode.FastTransformation)

                self.frame_pixmaps_cache[frame_idx] = cropped
                return cropped
        return None

    def set_image_cache(self, images: dict[int, QImage]) -> None:
        """Pre-populate pixmap cache from background-loaded QImages.

        Converts QImages to QPixmaps for cached access, avoiding redundant
        disk I/O when loading the organised mosaic view.

        Args:
            images: Dict mapping frame_index to pre-loaded QImage
        """
        for idx, qimage in images.items():
            pixmap = QPixmap.fromImage(qimage)
            if not pixmap.isNull():
                if pixmap.height() != self.thumbnail_size:
                    pixmap = pixmap.scaledToHeight(
                        self.thumbnail_size,
                        Qt.TransformationMode.FastTransformation,
                    )
                self.frame_pixmaps_cache[idx] = pixmap

    def _create_frame_label(self, pixmap: QPixmap, frame_index: int) -> QLabel:
        """Create clickable label."""
        label = QLabel()
        label.setStyleSheet("QLabel { border: none; } QLabel:hover { background-color: #0078d4; }")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setToolTip(f"Frame {frame_index}")
        label.setCursor(Qt.CursorShape.PointingHandCursor)
        label.setPixmap(pixmap)
        label.setProperty("frame_index", frame_index)
        label.installEventFilter(self)
        self._frame_labels.append(label)
        return label
