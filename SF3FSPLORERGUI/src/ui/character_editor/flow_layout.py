"""
FlowLayout - A flow layout that arranges widgets left-to-right, top-to-bottom.

This module provides a reusable flow layout widget based on Qt's FlowLayout
example. Extracted from window.py for better modularity.
"""

from PyQt6.QtCore import QPoint, QRect, QSize, Qt
from PyQt6.QtWidgets import QLayout, QLayoutItem, QSizePolicy, QWidget


class FlowLayout(QLayout):
    """A flow layout that arranges widgets left-to-right, top-to-bottom.

    This layout places widgets in horizontal rows, wrapping to the next
    row when the current row is full. Based on Qt's FlowLayout example.
    """

    def __init__(self, parent: QWidget | None = None, margin: int = 0, spacing: int = -1):
        """Initialize the flow layout.

        Args:
            parent: Parent widget
            margin: Margins around the layout
            spacing: Spacing between items (-1 for default)
        """
        super().__init__(parent)
        if parent is not None:
            self.setContentsMargins(margin, margin, margin, margin)
        self.setSpacing(spacing)
        self._item_list: list[QLayoutItem] = []

    def __del__(self) -> None:
        """Clean up layout items on destruction."""
        item = self.takeAt(0)
        while item:
            item = self.takeAt(0)

    def addItem(self, item: QLayoutItem | None) -> None:  # noqa: N802  # pylint: disable=invalid-name
        """Add an item to the layout.

        Args:
            item: The layout item to add. None items are ignored.
        """
        if item is not None:
            self._item_list.append(item)

    def count(self) -> int:
        """Return the number of items in the layout."""
        return len(self._item_list)

    def itemAt(self, index: int) -> QLayoutItem | None:  # noqa: N802  # pylint: disable=invalid-name
        """Return the item at the given index."""
        if 0 <= index < len(self._item_list):
            return self._item_list[index]
        return None

    def takeAt(self, index: int) -> QLayoutItem | None:  # noqa: N802  # pylint: disable=invalid-name
        """Remove and return the item at the given index."""
        if 0 <= index < len(self._item_list):
            return self._item_list.pop(index)
        return None

    def expandingDirections(self) -> Qt.Orientation:  # noqa: N802  # pylint: disable=invalid-name
        """Return the expanding directions (none for flow layout)."""
        return Qt.Orientation(0)

    def hasHeightForWidth(self) -> bool:  # noqa: N802  # pylint: disable=invalid-name
        """Return True since height depends on width."""
        return True

    def heightForWidth(self, width: int) -> int:  # noqa: N802  # pylint: disable=invalid-name
        """Calculate height needed for the given width."""
        height = self._do_layout(QRect(0, 0, width, 0), test_only=True)
        return height

    def setGeometry(self, rect: QRect) -> None:  # noqa: N802  # pylint: disable=invalid-name
        """Set the geometry of the layout."""
        super().setGeometry(rect)
        self._do_layout(rect, test_only=False)

    def sizeHint(self) -> QSize:  # noqa: N802  # pylint: disable=invalid-name
        """Return the preferred size of the layout."""
        return self.minimumSize()

    def minimumSize(self) -> QSize:  # noqa: N802  # pylint: disable=invalid-name
        """Return the minimum size of the layout."""
        size = QSize()
        for item in self._item_list:
            size = size.expandedTo(item.minimumSize())
        margins = self.contentsMargins()
        size += QSize(margins.left() + margins.right(), margins.top() + margins.bottom())
        return size

    def _do_layout(self, rect: QRect, test_only: bool) -> int:
        """Perform the actual layout calculation.

        Args:
            rect: Rectangle to lay out within
            test_only: If True, only calculate without moving widgets

        Returns:
            The height required for the layout
        """
        x = rect.x()
        y = rect.y()
        line_height = 0
        spacing = self.spacing()

        for item in self._item_list:
            wid = item.widget()
            if wid is None:
                continue

            style = wid.style()
            if style is not None:
                space_x = spacing + style.layoutSpacing(
                    QSizePolicy.ControlType.PushButton,
                    QSizePolicy.ControlType.PushButton,
                    Qt.Orientation.Horizontal,
                )
                space_y = spacing + style.layoutSpacing(
                    QSizePolicy.ControlType.PushButton,
                    QSizePolicy.ControlType.PushButton,
                    Qt.Orientation.Vertical,
                )
            else:
                # Fallback spacing when style is unavailable
                space_x = spacing if spacing >= 0 else 6
                space_y = spacing if spacing >= 0 else 6

            next_x = x + item.sizeHint().width() + space_x
            if next_x - space_x > rect.right() and line_height > 0:
                x = rect.x()
                y = y + line_height + space_y
                next_x = x + item.sizeHint().width() + space_x
                line_height = 0

            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), item.sizeHint()))

            x = next_x
            line_height = max(line_height, item.sizeHint().height())

        return y + line_height - rect.y()
