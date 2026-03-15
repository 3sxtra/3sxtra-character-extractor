"""
Sequence Editor Dialog for the Character Editor.

Provides a full-featured dialog for editing animation sequences,
including frame ordering, duration control, and non-linear frame lists.
"""

import os

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


class SequenceEditorDialog(QDialog):
    """Dialog for editing animation sequences with full control over frames and durations."""

    def __init__(
        self,
        sequence_data: dict,
        frames_dir: str,
        total_frames: int,
        parent: QWidget | None = None,
    ):
        """
        Initialize the sequence editor dialog.

        Args:
            sequence_data: The sequence dict with 'name', 'frames', 'start', 'end'
            frames_dir: Path to the frames directory for loading thumbnails
            total_frames: Total number of available frames
            parent: Parent widget
        """
        super().__init__(parent)
        self.setWindowTitle("Edit Sequence")
        self.setMinimumSize(600, 500)
        self.resize(700, 550)

        self.frames_dir = frames_dir
        self.total_frames = total_frames
        self.thumbnail_cache: dict[int, QPixmap] = {}

        # Deep copy the frames data to avoid modifying original until OK
        self.original_name = sequence_data.get("name", "Unnamed")
        raw_frames = sequence_data.get("frames", [])

        # Normalize to (index, duration) tuples
        self.frames_data: list[tuple[int, int]] = []
        for f in raw_frames:
            if isinstance(f, (list, tuple)):
                self.frames_data.append((int(f[0]), int(f[1])))
            else:
                self.frames_data.append((int(f), 4))  # Default duration

        self._setup_ui()
        self._populate_table()

    def _setup_ui(self) -> None:
        """Set up the dialog UI components."""
        layout = QVBoxLayout(self)

        # Name input
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("Name:"))
        self.name_input = QLineEdit(self.original_name)
        self.name_input.setMinimumWidth(300)
        name_layout.addWidget(self.name_input)
        name_layout.addStretch()
        layout.addLayout(name_layout)

        # Main content: table + buttons
        content_layout = QHBoxLayout()

        # Frame table
        self.frame_table = QTableWidget()
        self.frame_table.setColumnCount(4)
        self.frame_table.setHorizontalHeaderLabels(["#", "Frame", "Duration", "Preview"])
        self.frame_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.frame_table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        v_header = self.frame_table.verticalHeader()
        if v_header:
            v_header.setVisible(False)

        # Column sizing
        header = self.frame_table.horizontalHeader()
        if header:
            header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
            header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
            header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
            header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self.frame_table.setColumnWidth(0, 40)
        self.frame_table.setColumnWidth(2, 70)
        self.frame_table.setColumnWidth(3, 50)

        self.frame_table.itemSelectionChanged.connect(self._on_selection_changed)
        content_layout.addWidget(self.frame_table, 1)

        # Buttons panel
        btn_layout = QVBoxLayout()

        self.add_frame_btn = QPushButton("+ Add Frame")
        self.add_frame_btn.clicked.connect(self._add_frame)
        btn_layout.addWidget(self.add_frame_btn)

        self.add_range_btn = QPushButton("+ Add Range")
        self.add_range_btn.clicked.connect(self._add_range)
        btn_layout.addWidget(self.add_range_btn)

        btn_layout.addSpacing(10)

        self.remove_btn = QPushButton("- Remove")
        self.remove_btn.clicked.connect(self._remove_selected)
        btn_layout.addWidget(self.remove_btn)

        btn_layout.addSpacing(10)

        self.move_up_btn = QPushButton("↑ Move Up")
        self.move_up_btn.clicked.connect(self._move_up)
        btn_layout.addWidget(self.move_up_btn)

        self.move_down_btn = QPushButton("↓ Move Down")
        self.move_down_btn.clicked.connect(self._move_down)
        btn_layout.addWidget(self.move_down_btn)

        btn_layout.addStretch()

        content_layout.addLayout(btn_layout)
        layout.addLayout(content_layout)

        # Duration editor
        dur_layout = QHBoxLayout()
        dur_layout.addWidget(QLabel("Duration:"))
        self.duration_spin = QSpinBox()
        self.duration_spin.setRange(1, 255)
        self.duration_spin.setValue(4)
        self.duration_spin.setSuffix(" ticks")
        self.duration_spin.setToolTip("Duration in game ticks (1 tick ≈ 16.67ms at 60 FPS)")
        self.duration_spin.valueChanged.connect(self._on_duration_changed)
        dur_layout.addWidget(self.duration_spin)
        dur_layout.addWidget(QLabel("(selected frame)"))
        dur_layout.addStretch()
        layout.addLayout(dur_layout)

        # Dialog buttons
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def _populate_table(self) -> None:
        """Populate the table with current frames data."""
        self.frame_table.setRowCount(len(self.frames_data))

        for row, (frame_idx, duration) in enumerate(self.frames_data):
            # Row number
            num_item = QTableWidgetItem(str(row + 1))
            num_item.setFlags(num_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            num_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.frame_table.setItem(row, 0, num_item)

            # Frame index
            frame_item = QTableWidgetItem(str(frame_idx))
            frame_item.setFlags(frame_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            frame_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.frame_table.setItem(row, 1, frame_item)

            # Duration
            dur_item = QTableWidgetItem(str(duration))
            dur_item.setFlags(dur_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            dur_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.frame_table.setItem(row, 2, dur_item)

            # Preview thumbnail
            thumb = self._get_thumbnail(frame_idx)
            if thumb and not thumb.isNull():
                preview_item = QTableWidgetItem()
                preview_item.setData(Qt.ItemDataRole.DecorationRole, thumb)
                preview_item.setFlags(preview_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.frame_table.setItem(row, 3, preview_item)
                self.frame_table.setRowHeight(row, 36)
            else:
                preview_item = QTableWidgetItem("-")
                preview_item.setFlags(preview_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                preview_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.frame_table.setItem(row, 3, preview_item)

    def _get_thumbnail(self, frame_idx: int) -> QPixmap | None:
        """Get a cached thumbnail for a frame index."""
        if frame_idx in self.thumbnail_cache:
            return self.thumbnail_cache[frame_idx]

        path = os.path.join(self.frames_dir, f"frame_{frame_idx}.png")
        if os.path.exists(path):
            pix = QPixmap(path)
            if not pix.isNull():
                # Scale to 32x32 maintaining aspect ratio
                thumb = pix.scaled(
                    32, 32, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
                )
                self.thumbnail_cache[frame_idx] = thumb
                return thumb
        return None

    def _on_selection_changed(self) -> None:
        """Update duration spinbox when selection changes."""
        selected = self.frame_table.selectedIndexes()
        if selected:
            row = selected[0].row()
            if 0 <= row < len(self.frames_data):
                _, duration = self.frames_data[row]
                self.duration_spin.blockSignals(True)
                self.duration_spin.setValue(duration)
                self.duration_spin.blockSignals(False)

    def _on_duration_changed(self, value: int) -> None:
        """Update duration for selected frame(s)."""
        selected_rows = set(idx.row() for idx in self.frame_table.selectedIndexes())
        for row in selected_rows:
            if 0 <= row < len(self.frames_data):
                frame_idx, _ = self.frames_data[row]
                self.frames_data[row] = (frame_idx, value)
                # Update table display
                dur_item = self.frame_table.item(row, 2)
                if dur_item:
                    dur_item.setText(str(value))

    def _add_frame(self) -> None:
        """Add a single frame to the sequence."""
        frame_idx, ok = QInputDialog.getInt(
            self, "Add Frame", f"Enter frame index (0 to {self.total_frames - 1}):", 0, 0, self.total_frames - 1
        )
        if ok:
            duration, ok2 = QInputDialog.getInt(self, "Frame Duration", "Enter duration in ticks:", 4, 1, 255)
            if ok2:
                self.frames_data.append((frame_idx, duration))
                self._populate_table()
                # Select the new row
                self.frame_table.selectRow(len(self.frames_data) - 1)

    def _add_range(self) -> None:
        """Add a range of frames to the sequence."""
        start, ok1 = QInputDialog.getInt(
            self, "Add Range - Start", f"Start frame index (0 to {self.total_frames - 1}):", 0, 0, self.total_frames - 1
        )
        if not ok1:
            return

        end, ok2 = QInputDialog.getInt(
            self,
            "Add Range - End",
            f"End frame index (0 to {self.total_frames - 1}):",
            min(start + 10, self.total_frames - 1),
            0,
            self.total_frames - 1,
        )
        if not ok2:
            return

        duration, ok3 = QInputDialog.getInt(self, "Range Duration", "Duration for each frame in ticks:", 4, 1, 255)
        if not ok3:
            return

        # Add frames in order (handle reverse ranges)
        if start <= end:
            for idx in range(start, end + 1):
                self.frames_data.append((idx, duration))
        else:
            for idx in range(start, end - 1, -1):
                self.frames_data.append((idx, duration))

        self._populate_table()
        # Select the last added row
        self.frame_table.selectRow(len(self.frames_data) - 1)

    def _remove_selected(self) -> None:
        """Remove selected frames from the sequence."""
        selected_rows = sorted(set(idx.row() for idx in self.frame_table.selectedIndexes()), reverse=True)
        if not selected_rows:
            return

        for row in selected_rows:
            if 0 <= row < len(self.frames_data):
                del self.frames_data[row]

        self._populate_table()

    def _move_up(self) -> None:
        """Move selected frame up in the list."""
        selected_rows = sorted(set(idx.row() for idx in self.frame_table.selectedIndexes()))
        if not selected_rows or selected_rows[0] == 0:
            return

        # Move each selected row up by one
        for row in selected_rows:
            if row > 0:
                self.frames_data[row], self.frames_data[row - 1] = (self.frames_data[row - 1], self.frames_data[row])

        self._populate_table()
        # Reselect moved rows
        self.frame_table.clearSelection()
        for row in selected_rows:
            self.frame_table.selectRow(row - 1)

    def _move_down(self) -> None:
        """Move selected frame down in the list."""
        selected_rows = sorted(set(idx.row() for idx in self.frame_table.selectedIndexes()), reverse=True)
        if not selected_rows or selected_rows[0] >= len(self.frames_data) - 1:
            return

        # Move each selected row down by one (process in reverse to avoid conflicts)
        for row in selected_rows:
            if row < len(self.frames_data) - 1:
                self.frames_data[row], self.frames_data[row + 1] = (self.frames_data[row + 1], self.frames_data[row])

        self._populate_table()
        # Reselect moved rows
        self.frame_table.clearSelection()
        for row in selected_rows:
            self.frame_table.selectRow(row + 1)

    def get_result(self) -> dict:
        """
        Get the edited sequence data.

        Returns:
            Updated sequence dict with name, frames, start, end
        """
        name = self.name_input.text().strip() or "Unnamed"

        if not self.frames_data:
            return {
                "name": name,
                "frames": [],
                "start": 0,
                "end": 0,
            }

        # Calculate start/end for display
        frame_indices = [f[0] for f in self.frames_data]
        start = frame_indices[0]
        end = frame_indices[-1]

        return {
            "name": name,
            "frames": list(self.frames_data),  # List of (index, duration) tuples
            "start": start,
            "end": end,
        }
