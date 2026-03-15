"""
Animation controls and canvas widgets for the Character Editor.

This module contains the AnimationCanvas for displaying frames and
AnimationControlsWidget for playback controls.
"""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QPixmap
from PyQt6.QtWidgets import (
    QColorDialog,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)


class AnimationCanvas(QWidget):
    """Simple canvas to display a pre-rendered frame."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setMinimumSize(300, 300)
        self.current_frame_pixmap: QPixmap | None = None
        self.zoom_level = 2.0
        self.offset_x = 0
        self.offset_y = 0
        self.background_color = QColor(30, 30, 30)  # Default #1e1e1e

        # Pan state
        self.is_panning = False
        self.last_mouse_pos = None

        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setMouseTracking(True)

    def set_zoom(self, zoom: float) -> None:
        """Set the canvas zoom level."""
        self.zoom_level = zoom
        self.update()

    def set_frame(self, pixmap: QPixmap | None) -> None:
        """Set the current frame to display."""
        self.current_frame_pixmap = pixmap
        self.update()

    def set_background_color(self, color: QColor) -> None:
        """Set the canvas background color."""
        self.background_color = color
        self.update()

    def mousePressEvent(self, event) -> None:  # noqa: N802
        """Handle mouse press event for panning."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.is_panning = True
            self.last_mouse_pos = event.pos()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        """Handle mouse move event for panning."""
        if self.is_panning and self.last_mouse_pos:
            delta = event.pos() - self.last_mouse_pos
            self.offset_x += delta.x()
            self.offset_y += delta.y()
            self.last_mouse_pos = event.pos()
            self.update()

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        """Handle mouse release event for panning."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.is_panning = False
            self.last_mouse_pos = None
            self.setCursor(Qt.CursorShape.OpenHandCursor)

    def paintEvent(self, _event) -> None:  # noqa: N802
        """Handle paint event."""
        painter = QPainter(self)
        painter.fillRect(self.rect(), self.background_color)

        cx = self.width() // 2 + self.offset_x
        cy = self.height() // 2 + self.offset_y

        if self.current_frame_pixmap and not self.current_frame_pixmap.isNull():
            # Draw centered with zoom
            w = int(self.current_frame_pixmap.width() * self.zoom_level)
            h = int(self.current_frame_pixmap.height() * self.zoom_level)
            x = cx - (w // 2)
            y = cy - (h // 2)

            painter.drawPixmap(x, y, w, h, self.current_frame_pixmap)


class AnimationControlsWidget(QWidget):
    """Widget for animation sequence controls."""

    play_requested = pyqtSignal()
    stop_requested = pyqtSignal()
    frame_selected = pyqtSignal(int)
    zoom_changed = pyqtSignal(float)
    gif_export_requested = pyqtSignal()
    smart_gif_export_requested = pyqtSignal(int)  # scale_factor
    bg_color_changed = pyqtSignal(QColor)

    # Sequence Signals
    seq_add_requested = pyqtSignal()
    seq_remove_requested = pyqtSignal()
    seq_save_requested = pyqtSignal()
    seq_edit_requested = pyqtSignal()  # Open sequence editor dialog
    seq_update_requested = pyqtSignal(int, int)  # start, end
    seq_selected = pyqtSignal(int)  # index

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        # Initialize widget references
        self.seq_list: QListWidget
        self.start_spin: QSpinBox
        self.end_spin: QSpinBox
        self.add_btn: QPushButton
        self.del_btn: QPushButton
        self.edit_btn: QPushButton
        self.save_btn: QPushButton
        self.gif_btn: QPushButton
        self.smart_gif_btn: QPushButton
        self.scale_combo: QComboBox
        self.play_btn: QPushButton
        self.speed_spin: QSpinBox
        self.loop_chk: QPushButton
        self.frame_lbl: QLabel
        self.filename_lbl: QLabel
        self.zoom_slider: QSlider
        self.zoom_val_lbl: QLabel
        self.bg_color_btn: QPushButton
        self.frames_list: QListWidget
        self.setup_ui()

    def setup_ui(self) -> None:
        """Set up the UI components."""
        layout = QHBoxLayout(self)

        # Left: Sequences logic (Ported/Simplified)
        seq_layout = QVBoxLayout()
        self.seq_list = QListWidget()
        seq_layout.addWidget(QLabel("Sequences"))
        seq_layout.addWidget(self.seq_list)

        # Simple Add/Remove
        input_row = QHBoxLayout()
        self.start_spin = QSpinBox()
        self.start_spin.setPrefix("S: ")
        self.start_spin.setFixedWidth(70)
        self.start_spin.valueChanged.connect(self.on_seq_range_changed)

        self.end_spin = QSpinBox()
        self.end_spin.setPrefix("E: ")
        self.end_spin.setFixedWidth(70)
        self.end_spin.valueChanged.connect(self.on_seq_range_changed)

        input_row.addWidget(self.start_spin)
        input_row.addWidget(self.end_spin)
        seq_layout.addLayout(input_row)

        btn_row = QHBoxLayout()
        self.add_btn = QPushButton("+")
        self.add_btn.clicked.connect(self.seq_add_requested.emit)
        self.del_btn = QPushButton("-")
        self.del_btn.clicked.connect(self.seq_remove_requested.emit)
        self.edit_btn = QPushButton("Edit...")
        self.edit_btn.clicked.connect(self.seq_edit_requested.emit)
        self.edit_btn.setToolTip("Edit sequence frames and durations")

        self.save_btn = QPushButton("Save")
        self.save_btn.clicked.connect(self.seq_save_requested.emit)

        self.gif_btn = QPushButton("GIF")
        self.gif_btn.clicked.connect(self.gif_export_requested.emit)

        self.smart_gif_btn = QPushButton("Smart GIF")
        self.smart_gif_btn.setToolTip("Export with auto-crop and upscale")
        self.smart_gif_btn.clicked.connect(self._on_smart_gif_clicked)

        self.scale_combo = QComboBox()
        self.scale_combo.addItems(["1x", "2x", "3x", "4x"])
        self.scale_combo.setCurrentIndex(1)  # Default 2x
        self.scale_combo.setFixedWidth(50)
        self.scale_combo.setToolTip("Upscale factor (nearest-neighbor)")

        btn_row.addWidget(self.add_btn)
        btn_row.addWidget(self.del_btn)
        btn_row.addWidget(self.edit_btn)
        btn_row.addWidget(self.save_btn)
        btn_row.addWidget(self.gif_btn)
        btn_row.addWidget(self.smart_gif_btn)
        btn_row.addWidget(self.scale_combo)

        seq_layout.addLayout(btn_row)

        self.seq_list.currentRowChanged.connect(self.on_seq_row_changed)

        layout.addLayout(seq_layout, 1)

        # Middle: Playback controls
        ctrl_layout = QVBoxLayout()
        self.play_btn = QPushButton("Play")
        self.play_btn.clicked.connect(self.on_play_stop)
        ctrl_layout.addWidget(self.play_btn)

        self.speed_spin = QSpinBox()
        self.speed_spin.setRange(10, 200)
        self.speed_spin.setValue(100)
        self.speed_spin.setSuffix("%")
        self.speed_spin.setToolTip("Playback speed: 100% = game speed (60 FPS base)")
        ctrl_layout.addWidget(self.speed_spin)

        # Loop Checkbox
        self.loop_chk = QPushButton("Loop: ON")
        self.loop_chk.setCheckable(True)
        self.loop_chk.setChecked(True)  # Default to Loop
        self.loop_chk.toggled.connect(self.on_loop_toggled)
        ctrl_layout.addWidget(self.loop_chk)

        self.frame_lbl = QLabel("Frame: -")
        ctrl_layout.addWidget(self.frame_lbl)

        self.filename_lbl = QLabel("File: -")
        self.filename_lbl.setStyleSheet("color: #888888;")
        ctrl_layout.addWidget(self.filename_lbl)

        # Zoom Slider
        zoom_layout = QHBoxLayout()
        zoom_layout.addWidget(QLabel("Zoom:"))
        self.zoom_slider = QSlider(Qt.Orientation.Horizontal)
        self.zoom_slider.setRange(1, 8)
        self.zoom_slider.setValue(2)  # Default 2x
        self.zoom_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.zoom_slider.setTickInterval(1)
        self.zoom_slider.valueChanged.connect(self.on_zoom_changed)
        zoom_layout.addWidget(self.zoom_slider)
        self.zoom_val_lbl = QLabel("2x")
        zoom_layout.addWidget(self.zoom_val_lbl)
        ctrl_layout.addLayout(zoom_layout)

        # Background Color Picker
        bg_layout = QHBoxLayout()
        bg_layout.addWidget(QLabel("BG:"))
        self.bg_color_btn = QPushButton()
        self.bg_color_btn.setFixedSize(30, 20)
        self.bg_color_btn.setStyleSheet("background-color: #1e1e1e; border: 1px solid gray;")
        self.bg_color_btn.clicked.connect(self.on_bg_color_pick)
        bg_layout.addWidget(self.bg_color_btn)
        ctrl_layout.addLayout(bg_layout)

        layout.addLayout(ctrl_layout, 0)

        # Right: Raw Frames List
        frames_layout = QVBoxLayout()
        frames_layout.addWidget(QLabel("Raw Frames"))
        self.frames_list = QListWidget()
        self.frames_list.currentRowChanged.connect(self.on_frame_row_changed)
        frames_layout.addWidget(self.frames_list)

        layout.addLayout(frames_layout, 1)

    def on_play_stop(self) -> None:
        """Handle play/stop toggle."""
        if self.play_btn.text() == "Play":
            self.play_requested.emit()
        else:
            self.stop_requested.emit()

    def on_loop_toggled(self, checked: bool) -> None:
        """Update loop button text."""
        self.loop_chk.setText(f"Loop: {'ON' if checked else 'OFF'}")

    def set_playing(self, playing: bool) -> None:
        """Update play/stop button text."""
        self.play_btn.setText("Stop" if playing else "Play")

    def on_frame_row_changed(self, row: int) -> None:
        """Handle frame list row change."""
        if row >= 0:
            self.frame_selected.emit(row)

    def update_frames_list(self, num_frames: int) -> None:
        """Update the raw frames list widget."""
        self.frames_list.clear()
        for i in range(num_frames):
            self.frames_list.addItem(f"Frame {i}")

    def on_zoom_changed(self, value: int) -> None:
        """Handle zoom slider change."""
        self.zoom_val_lbl.setText(f"{value}x")
        self.zoom_changed.emit(float(value))

    def on_seq_row_changed(self, row: int) -> None:
        """Handle sequence list row change."""
        if row >= 0:
            self.seq_selected.emit(row)

    def on_seq_range_changed(self) -> None:
        """Handle sequence range spinbox change."""
        # Prevent loops if modifying programmatically
        if self.start_spin.hasFocus() or self.end_spin.hasFocus():
            self.seq_update_requested.emit(self.start_spin.value(), self.end_spin.value())

    def on_bg_color_pick(self) -> None:
        """Open color picker dialog for background color."""
        color = QColorDialog.getColor(QColor(255, 255, 255), self, "Select Background Color")
        if color.isValid():
            self.bg_color_btn.setStyleSheet(f"background-color: {color.name()}; border: 1px solid gray;")
            self.bg_color_changed.emit(color)

    def _on_smart_gif_clicked(self) -> None:
        """Handle Smart GIF button click — emits scale factor from combo."""
        scale_text = self.scale_combo.currentText()  # "1x", "2x", etc.
        scale_factor = int(scale_text.replace("x", ""))
        self.smart_gif_export_requested.emit(scale_factor)
