"""
Animation sequence browser widget with table-based organization.
"""

from PyQt6.QtCore import QSize, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QIcon, QPixmap
from PyQt6.QtWidgets import QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget

from SF3FSPLORERGUI.src.utils.image_crop import auto_crop_pixmap


# Human-readable labels for animation table types
# Human-readable labels for animation table types
TABLE_LABELS = {
    "atca": "Attacks",  # Renamed from "Tricks" (User request)
    "nmca": "Normal",
    "dmca": "Damage",
    "btca": "Battle",
    "caca": "Throws",
    "cuca": "Hit",  # Renamed from "Caught"
    "saca": "Supers",
    "exca": "Various",  # Renamed from "Landing"
    "cbca": "Subroutine",
    "yuca": "Victory",
    "effects": "Effects",
    "effect_data": "Effects",  # Merge effect_data with Effects
    "manual": "Manual",
    "orphans": "ORPHANS",
    "all": "All Frames",
}

# Order for displaying families
# User request: "Attacks" to top, "Orphans" to bottom
TABLE_ORDER = [
    "atca",  # Attacks (First)
    "nmca",
    "dmca",
    "btca",
    "caca",
    "cuca",
    "saca",
    "exca",
    "cbca",
    "yuca",
    "effects",
    "effect_data",
    "manual",
    "all",
    "orphans",  # Last
]


class SequenceBrowserWidget(QWidget):
    """Widget to display animation sequences organized by family/type.

    Uses a tree structure with collapsible family groups containing
    individual sequences with cropped thumbnail icons.
    """

    sequence_selected = pyqtSignal(int)  # sequence_index

    def __init__(self, parent=None):
        super().__init__(parent)
        self._family_items: dict[str, QTreeWidgetItem] = {}
        self._icon_size = 64
        self.setup_ui()

    def setup_ui(self):
        """Set up the UI components"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setIconSize(QSize(self._icon_size, self._icon_size))
        self.tree.setIndentation(16)
        self.tree.setAnimated(True)
        self.tree.setExpandsOnDoubleClick(True)

        # Style for dark theme
        self.tree.setStyleSheet("""
            QTreeWidget {
                background-color: #2d2d2d;
                color: #ffffff;
                border: none;
            }
            QTreeWidget::item {
                padding: 4px;
                border-bottom: 1px solid #3d3d3d;
            }
            QTreeWidget::item:selected {
                background-color: #0078d4;
            }
            QTreeWidget::item:hover {
                background-color: #3d3d3d;
            }
            QTreeWidget::branch:has-children:closed {
                image: none;
                border-image: none;
            }
            QTreeWidget::branch:has-children:open {
                image: none;
                border-image: none;
            }
        """)

        self.tree.itemClicked.connect(self._on_item_clicked)

        layout.addWidget(self.tree)

    def clear(self):
        """Clear all sequences from the browser"""
        self.tree.clear()
        self._family_items.clear()

    def _get_or_create_family_item(self, table_type: str) -> QTreeWidgetItem:
        """Get or create a parent item for a sequence family.

        Args:
            table_type: The animation table type (nmca, dmca, etc.)

        Returns:
            QTreeWidgetItem for the family group
        """
        if table_type in self._family_items:
            return self._family_items[table_type]

        # Check if we should merge based on label (e.g. effect_data -> Effects)
        label = TABLE_LABELS.get(table_type, table_type.upper())

        # Search for existing family with same label
        for existing_type, item in self._family_items.items():
            existing_label = TABLE_LABELS.get(existing_type, existing_type.upper())
            if existing_label == label:
                # Merge into existing folder
                # Map this type to existing item
                self._family_items[table_type] = item
                return item

        # Create new family item
        label = TABLE_LABELS.get(table_type, table_type.upper())
        family_item = QTreeWidgetItem([f"📁 {label}"])
        family_item.setFlags(family_item.flags() & ~Qt.ItemFlag.ItemIsSelectable)

        # Insert in correct order
        insert_pos = 0
        if table_type in TABLE_ORDER:
            target_idx = TABLE_ORDER.index(table_type)
            for i in range(self.tree.topLevelItemCount()):
                existing = self.tree.topLevelItem(i)
                if existing:
                    existing_type = existing.data(0, Qt.ItemDataRole.UserRole + 1)
                    if existing_type in TABLE_ORDER and TABLE_ORDER.index(existing_type) < target_idx:
                        insert_pos = i + 1

        self.tree.insertTopLevelItem(insert_pos, family_item)
        family_item.setData(0, Qt.ItemDataRole.UserRole + 1, table_type)
        family_item.setExpanded(False)  # Collapsed by default for performance

        self._family_items[table_type] = family_item
        return family_item

    def add_sequence(self, name: str, icon_pixmap: QPixmap | None, seq_index: int, table_type: str = "manual"):
        """Add a sequence to the browser under its family group.

        Args:
            name: Display name of the sequence
            icon_pixmap: Pixmap for the thumbnail (will be cropped)
            seq_index: Index in the sequences_data list
            table_type: Animation table type for grouping (nmca, dmca, etc.)
        """
        # Get or create family parent
        family_item = self._get_or_create_family_item(table_type)

        # Create sequence item
        item = QTreeWidgetItem([name])

        # Create icon from pixmap (auto-crop and scale)
        if icon_pixmap and not icon_pixmap.isNull():
            # Auto-crop to remove transparent borders
            cropped = auto_crop_pixmap(icon_pixmap, padding=2)

            # Scale to icon size maintaining aspect ratio
            if cropped.height() > self._icon_size or cropped.width() > self._icon_size:
                cropped = cropped.scaled(
                    self._icon_size,
                    self._icon_size,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )

            item.setIcon(0, QIcon(cropped))
        else:
            # Placeholder icon
            pix = QPixmap(self._icon_size, self._icon_size)
            pix.fill(QColor(60, 60, 60))
            item.setIcon(0, QIcon(pix))

        # Store sequence index for retrieval on click
        item.setData(0, Qt.ItemDataRole.UserRole, seq_index)

        family_item.addChild(item)

        # Update family count in label
        count = family_item.childCount()
        label = TABLE_LABELS.get(table_type, table_type.upper())
        family_item.setText(0, f"📁 {label} ({count})")

    def _on_item_clicked(self, item: QTreeWidgetItem, _column: int):
        """Handle item click - emit signal only for sequence items."""
        # Ignore clicks on family (parent) items
        if item.childCount() > 0:
            return

        idx = item.data(0, Qt.ItemDataRole.UserRole)
        if idx is not None:
            self.sequence_selected.emit(idx)

    def collapse_all(self):
        """Collapse all family groups."""
        self.tree.collapseAll()

    def expand_all(self):
        """Expand all family groups."""
        self.tree.expandAll()
