"""
Palette Viewer Widget for displaying and editing color palettes.

Inspired by PalMod's palette viewer, displays a grid of colors
from the currently selected character palette.
"""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QPen
from PyQt6.QtWidgets import (
    QColorDialog,
    QFrame,
    QGroupBox,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


class PaletteGridWidget(QWidget):
    """Widget that displays a 16x4 grid of palette colors.

    Displays 64 colors in a grid matching PalMod's layout.
    Supports click-to-select and optional editing.
    """

    color_selected = pyqtSignal(int, tuple)  # index, (r, g, b)
    color_changed = pyqtSignal(int, tuple)  # index, (r, g, b)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.colors: list[tuple[int, int, int]] = [(0, 0, 0)] * 64
        self.cell_size = 16
        self.selected_index = -1
        self.editable = False

        # Calculate size: 16 columns x 4 rows
        self.setMinimumSize(16 * self.cell_size + 2, 4 * self.cell_size + 2)
        self.setMaximumHeight(4 * self.cell_size + 4)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMouseTracking(True)

    def set_colors(self, colors: list[tuple[int, int, int]]) -> None:
        """Set the palette colors to display.

        Args:
            colors: List of (r, g, b) tuples (up to 64 colors)
        """
        self.colors = list(colors[:64])
        # Pad to 64 if needed
        while len(self.colors) < 64:
            self.colors.append((0, 0, 0))
        self.update()

    def set_editable(self, editable: bool) -> None:
        """Set whether colors can be edited by clicking."""
        self.editable = editable
        self.setCursor(Qt.CursorShape.PointingHandCursor if editable else Qt.CursorShape.ArrowCursor)

    def get_colors(self) -> list[tuple[int, int, int]]:
        """Return the current palette colors."""
        return list(self.colors)

    def paintEvent(self, _event) -> None:
        """Paint the color grid."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)

        # Draw each color cell
        for i, (r, g, b) in enumerate(self.colors):
            col = i % 16
            row = i // 16

            x = col * self.cell_size + 1
            y = row * self.cell_size + 1

            # Fill cell with color
            painter.fillRect(x, y, self.cell_size - 1, self.cell_size - 1, QColor(r, g, b))

            # Draw selection highlight
            if i == self.selected_index:
                painter.setPen(QPen(QColor(255, 255, 255), 2))
                painter.drawRect(x, y, self.cell_size - 2, self.cell_size - 2)
                painter.setPen(QPen(QColor(0, 0, 0), 1))
                painter.drawRect(x - 1, y - 1, self.cell_size, self.cell_size)

        # Draw border
        painter.setPen(QPen(QColor(128, 128, 128), 1))
        painter.drawRect(0, 0, 16 * self.cell_size + 1, 4 * self.cell_size + 1)

    def mousePressEvent(self, event) -> None:
        """Handle mouse click to select/edit a color."""
        if event.button() != Qt.MouseButton.LeftButton:
            return

        # Calculate which cell was clicked
        col = (event.pos().x() - 1) // self.cell_size
        row = (event.pos().y() - 1) // self.cell_size

        if 0 <= col < 16 and 0 <= row < 4:
            index = row * 16 + col
            self.selected_index = index
            self.color_selected.emit(index, self.colors[index])
            self.update()

            # Open color picker if editable
            if self.editable:
                current = self.colors[index]
                color = QColorDialog.getColor(QColor(*current), self, f"Edit Color {index}")
                if color.isValid():
                    new_rgb = (color.red(), color.green(), color.blue())
                    self.colors[index] = new_rgb
                    self.color_changed.emit(index, new_rgb)
                    self.update()

    def mouseMoveEvent(self, event) -> None:
        """Show tooltip with color info on hover."""
        col = (event.pos().x() - 1) // self.cell_size
        row = (event.pos().y() - 1) // self.cell_size

        if 0 <= col < 16 and 0 <= row < 4:
            index = row * 16 + col
            r, g, b = self.colors[index]
            self.setToolTip(f"#{r:02X}{g:02X}{b:02X} (Index {index})")
        else:
            self.setToolTip("")


class PaletteViewerWidget(QGroupBox):
    """PalMod-style palette viewer widget.

    Displays the currently selected palette with:
    - Title showing palette name (e.g., "LP Main")
    - 16x4 color grid
    - Optional editing capability
    """

    palette_changed = pyqtSignal(list)  # Emitted when colors are edited

    def __init__(self, parent=None):
        super().__init__("Palette View", parent)
        self.setup_ui()

    def setup_ui(self) -> None:
        """Initialize the UI components."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 12, 8, 8)
        layout.setSpacing(4)

        # Palette name label
        self.name_label = QLabel("LP Main")
        self.name_label.setStyleSheet("font-weight: bold; color: #333333;")
        layout.addWidget(self.name_label)

        # Color grid
        self.grid = PaletteGridWidget()
        self.grid.color_selected.connect(self.on_color_selected)
        self.grid.color_changed.connect(self.on_color_changed)
        layout.addWidget(self.grid)

        # Info label (shows selected color info)
        self.info_label = QLabel("")
        self.info_label.setStyleSheet("color: #666666; font-size: 10px;")
        layout.addWidget(self.info_label)

        # Separator line
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(line)

    def set_palette_name(self, name: str) -> None:
        """Set the displayed palette name."""
        self.name_label.setText(name)

    def set_colors(self, colors: list[tuple[int, int, int]]) -> None:
        """Set the palette colors to display."""
        self.grid.set_colors(colors)

    def set_editable(self, editable: bool) -> None:
        """Enable or disable color editing."""
        self.grid.set_editable(editable)

    def get_colors(self) -> list[tuple[int, int, int]]:
        """Get the current palette colors."""
        return self.grid.get_colors()

    def on_color_selected(self, index: int, rgb: tuple) -> None:
        """Handle color selection."""
        r, g, b = rgb
        self.info_label.setText(f"Index {index}: RGB({r}, {g}, {b}) #{r:02X}{g:02X}{b:02X}")

    def on_color_changed(self, _index: int, _rgb: tuple) -> None:
        """Handle color change from editing."""
        self.palette_changed.emit(self.grid.get_colors())
