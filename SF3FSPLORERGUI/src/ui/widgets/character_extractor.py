#!/usr/bin/env python3
"""
Character sprite extraction and frame recomposition widget
"""

# pylint: disable=arguments-renamed

import os
from typing import Any

from PyQt6.QtCore import QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QWidget,
)

from SF3FSPLORERGUI.src.core.workers.character_extractor import CharacterExtractionWorker
from SF3FSPLORERGUI.src.utils.compatibility import SF33RD_AVAILABLE
from SF3FSPLORERGUI.src.utils.helpers import get_afs_data_source, get_project_root

from .base_extractor import BaseExtractorWidget
from .palette_viewer import PaletteViewerWidget

if SF33RD_AVAILABLE:
    from sf33rd.core.data_model import character_data
else:
    character_data = {}


class CharacterExtractorWidget(BaseExtractorWidget):
    """
    Widget for extracting character sprites.
    """

    asset_ready = pyqtSignal(str, str)  # char_name, output_path
    palette_changed = pyqtSignal(list)  # Emits list of (r, g, b) tuples
    # Emits character name when selection changes
    character_selection_changed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__("Character Sprite Extraction & Frame Recomposition", parent)
        self.char_combo = None
        self.palette_color_combo = None  # PalMod-style: LP/MP/HP/LK/MK/HK/EX
        # Effect state: Normal/Burned/Frozen/etc.
        self.effect_state_combo = None
        self.palette_mode_combo = None
        self.palette_index_spin = None
        self.palette_index_label = None
        self.custom_palette_widget = None
        self.custom_palette_path = None
        self.custom_palette_btn = None
        self.custom_palette_label = None
        self.output_path = None
        self.palette_viewer = None  # PalMod-style palette grid viewer
        self._current_char_palette = None  # Cached CharacterPalette object
        self.init_ui()
        # Hide the title label - not needed in this context
        if self.title_label:
            self.title_label.hide()
        self.setup_worker()

        # Populate character list
        self.populate_characters()

    def add_config_elements(self, config_layout):
        """Add configuration elements"""
        # Character Selection
        self.char_combo = QComboBox()
        self.char_combo.setPlaceholderText("Select Character")
        self.char_combo.currentTextChanged.connect(self.on_character_selection_changed)
        config_layout.addRow("Character:", self.char_combo)

        # Costume Color Selection (PalMod-style: LP, MP, HP, LK, MK, HK, EX)
        self.palette_color_combo = QComboBox()
        self.palette_color_combo.addItems(
            [
                "LP (Light Punch)",
                "MP (Medium Punch)",
                "HP (Heavy Punch)",
                "LK (Light Kick)",
                "MK (Medium Kick)",
                "HK (Heavy Kick)",
                "EX (Super Color)",
            ]
        )
        self.palette_color_combo.setToolTip("Select costume color matching PalMod's button labels")
        self.palette_color_combo.currentIndexChanged.connect(self.on_palette_color_changed)
        config_layout.addRow("Costume Color:", self.palette_color_combo)

        # Effect State Selection (for special palette effects)
        self.effect_state_combo = QComboBox()
        self.effect_state_combo.addItems(
            [
                "Normal",
                "Burned/Red Parry",
                "Frozen/Super Flash",
                "Grey Tint (Faded)",
                "SA Animation/Parry",
            ]
        )
        self.effect_state_combo.setToolTip("Apply palette effect transformation (optional)")
        self.effect_state_combo.currentIndexChanged.connect(self.on_effect_state_changed)
        config_layout.addRow("Effect State:", self.effect_state_combo)

        # Palette Mode (Built-in vs Custom File)
        self.palette_mode_combo = QComboBox()
        self.palette_mode_combo.addItems(["Built-in Palettes", "Custom File"])
        self.palette_mode_combo.currentIndexChanged.connect(self.on_palette_mode_changed)
        config_layout.addRow("Palette Source:", self.palette_mode_combo)

        # Legacy palette index spin (hidden, for backwards compatibility)
        self.palette_index_spin = QSpinBox()
        self.palette_index_spin.setRange(0, 27)
        self.palette_index_spin.setVisible(False)
        self.palette_index_label = QLabel("Palette Index:")
        self.palette_index_label.setVisible(False)
        config_layout.addRow(self.palette_index_label, self.palette_index_spin)

        # Custom Palette File (Hidden by default)
        self.custom_palette_widget = QWidget()
        custom_pal_layout = QHBoxLayout(self.custom_palette_widget)
        custom_pal_layout.setContentsMargins(0, 0, 0, 0)
        self.custom_palette_path = QLineEdit()
        self.custom_palette_btn = QPushButton("Browse...")
        self.custom_palette_btn.clicked.connect(self.browse_palette)
        custom_pal_layout.addWidget(self.custom_palette_path)
        custom_pal_layout.addWidget(self.custom_palette_btn)

        self.custom_palette_label = QLabel("Palette File:")
        self.custom_palette_widget.setVisible(False)
        self.custom_palette_label.setVisible(False)
        config_layout.addRow(self.custom_palette_label, self.custom_palette_widget)

        # Output Directory
        default_out = os.path.join(get_project_root(), "output", "characters")
        output_widget, self.output_path = self.create_path_widget(default_out, self.browse_output)
        config_layout.addRow("Output Directory:", output_widget)

        # Palette Viewer (PalMod-style color grid)
        self.palette_viewer = PaletteViewerWidget()
        self.palette_viewer.set_editable(False)  # View-only for now
        config_layout.addRow(self.palette_viewer)

    def add_action_buttons(self, layout):
        """Add action buttons"""
        self.setup_action_buttons(layout, "Extract Sprites", self.start_extraction)

    def create_worker(self):
        """Create the background worker"""
        return CharacterExtractionWorker()

    def connect_completion_signal(self):
        """Connect worker completion signal"""
        if self.worker and hasattr(self.worker, "extraction_complete"):
            self.worker.extraction_complete.connect(self.on_worker_complete)

    def populate_characters(self):
        """Populate character dropdown"""
        # Try to reload/import character_data if empty
        data_to_use = character_data
        if not data_to_use:
            try:
                # pylint: disable=import-outside-toplevel
                from sf33rd.core.data_model import (
                    character_data as dynamic_data,
                )

                data_to_use = dynamic_data
            except ImportError:
                pass

        if self.char_combo is not None:
            if data_to_use:
                chars = sorted(data_to_use.keys())
                self.char_combo.clear()
                self.char_combo.addItems(chars)
                self.char_combo.setEnabled(True)
            else:
                self.char_combo.clear()
                self.char_combo.addItem("No characters found")
                self.char_combo.setEnabled(False)
        else:
            self.logger.error("self.char_combo is None! UI not initialized correctly?")

    def on_character_selection_changed(self, text):
        """Handle character selection change."""
        self.character_selection_changed.emit(text)  # Notify listeners (e.g., preview panel)
        self.check_and_load_existing_assets(text)
        self._load_character_palette(text)

    def _load_character_palette(self, char_name: str) -> None:
        """Load character palette and update the viewer.

        Args:
            char_name: Name of the character to load palette for
        """
        if not char_name or char_name in ["Select Character", "No characters found"]:
            self._current_char_palette = None
            return

        if not SF33RD_AVAILABLE:
            return

        try:
            # pylint: disable=import-outside-toplevel
            from sf33rd.lib.palette import CharacterPalette

            # Get character info
            char_info = character_data.get(char_name)
            if not char_info or "col" not in char_info:
                self.logger.warning("No palette file for %s", char_name)
                return

            # Load palette file using AfsDataSource
            data_source = get_afs_data_source()
            col_file = str(char_info["col"])

            self.logger.info("Loading palette from %s (source: %s)", col_file, data_source.source_type)

            # Get palette data - works with both archive and folder
            if data_source.source_type == "folder":
                col_path = data_source.get_file_path(col_file)
                if not col_path or not os.path.exists(col_path):
                    self.logger.warning("Palette file not found: %s", col_file)
                    return
                self._current_char_palette = CharacterPalette.from_file(col_path)
            else:
                # Archive mode: read bytes directly
                col_data = data_source.get_file_data(col_file)
                self.logger.info("Got %d bytes for palette", len(col_data))
                self._current_char_palette = CharacterPalette(col_data)

            self.logger.info("Palette loaded: %s", self._current_char_palette)
            self._update_palette_viewer()

        except Exception as e:  # pylint: disable=broad-exception-caught
            self.logger.error("Failed to load palette for %s: %s", char_name, e)
            import traceback  # pylint: disable=import-outside-toplevel

            self.logger.error(traceback.format_exc())

    def _update_palette_viewer(self) -> None:
        """Update the palette viewer with current settings."""
        if not self._current_char_palette or not self.palette_viewer:
            return

        # Get current costume color index
        color_idx = 0
        if self.palette_color_combo:
            color_idx = self.palette_color_combo.currentIndex()

        # Get effect type
        effect_type = None
        if self.effect_state_combo:
            effect_text = self.effect_state_combo.currentText()
            if "Burned" in effect_text:
                effect_type = "burned"
            elif "Frozen" in effect_text:
                effect_type = "frozen"
            elif "Grey" in effect_text:
                effect_type = "grey_tint"
            elif "SA" in effect_text:
                effect_type = "sa_parry"

        # Get palette colors with effect
        colors = self._current_char_palette.get_style_with_effect(color_idx, effect_type)
        rgb_colors = [c.to_rgb_tuple() for c in colors]

        # Update viewer
        self.palette_viewer.set_colors(rgb_colors)

        # Emit signal for other widgets (like sprite preview)
        self.palette_changed.emit(rgb_colors)

        # Update label
        color_names = ["LP", "MP", "HP", "LK", "MK", "HK", "EX"]
        color_name = color_names[color_idx] if color_idx < len(color_names) else f"Style {color_idx}"
        effect_suffix = f" ({effect_type})" if effect_type else ""
        self.palette_viewer.set_palette_name(f"{color_name} Main{effect_suffix}")

    def on_palette_color_changed(self, _index: int) -> None:
        """Handle costume color selection change."""
        self._update_palette_viewer()

    def on_effect_state_changed(self, _index: int) -> None:
        """Handle effect state selection change."""
        self._update_palette_viewer()

    def check_and_load_existing_assets(self, char_name):
        """Check for existing assets and load them if found"""
        if not char_name or not self.output_path:
            return

        # Don't try to load if it's the placeholder text or "No characters
        # found"
        if char_name in ["Select Character", "No characters found"]:
            return

        output_dir = self.output_path.text()
        if not output_dir or not os.path.exists(output_dir):
            return

        full_output_path = os.path.join(output_dir, char_name)
        frames_dir = os.path.join(full_output_path, "frames")

        # Check if frames directory exists and is not empty
        if os.path.exists(frames_dir) and os.listdir(frames_dir):
            # Emit asset ready signal to load in viewer
            self.asset_ready.emit(char_name, full_output_path)

    def on_palette_mode_changed(self, index):
        """Handle palette mode change.

        Args:
            index: 0 = Built-in Palettes, 1 = Custom File
        """
        # Show/hide custom file widgets based on selection
        show_custom = index == 1

        if self.custom_palette_label:
            self.custom_palette_label.setVisible(show_custom)
        if self.custom_palette_widget:
            self.custom_palette_widget.setVisible(show_custom)

        # Enable/disable built-in palette controls
        if self.palette_color_combo:
            self.palette_color_combo.setEnabled(not show_custom)
        if self.effect_state_combo:
            self.effect_state_combo.setEnabled(not show_custom)

    def browse_palette(self):
        """Browse for custom palette file"""
        filename, _ = QFileDialog.getOpenFileName(
            self, "Select Palette File", "", "Palette Files (*.bin *.col);;All Files (*.*)"
        )
        if filename and self.custom_palette_path:
            self.custom_palette_path.setText(filename)

    def browse_output(self):
        """Browse for output directory"""
        self.browse_directory("Select Output Directory", self.output_path)

    def start_extraction(self):
        """Start the extraction process"""
        if not self.char_combo:
            return

        char_name = self.char_combo.currentText()
        if not char_name or not self.char_combo.isEnabled():
            QMessageBox.warning(self, "Warning", "Please select a character.")
            return

        if not self.output_path:
            return

        output_dir = self.output_path.text()
        if not self.validate_output_dir(output_dir):
            return

        # Get palette parameters from PalMod-style UI
        palette_idx = 0
        effect_mode = None
        custom_pal = None

        # Get costume color (LP=0, MP=1, HP=2, LK=3, MK=4, HK=5, EX=6)
        if self.palette_color_combo:
            palette_idx = self.palette_color_combo.currentIndex()

        # Get effect state
        if self.effect_state_combo:
            effect_text = self.effect_state_combo.currentText()
            # Map effect state to internal type
            if "Burned" in effect_text:
                effect_mode = "burned"
            elif "Frozen" in effect_text:
                effect_mode = "frozen"
            elif "Grey" in effect_text:
                effect_mode = "grey_tint"
            elif "SA" in effect_text:
                effect_mode = "sa_parry"
            # "Normal" = None

        # Check for custom palette file
        if self.palette_mode_combo and self.palette_mode_combo.currentIndex() == 1:
            if self.custom_palette_path:
                custom_pal = self.custom_palette_path.text()
            if not custom_pal or not os.path.exists(custom_pal):
                QMessageBox.warning(self, "Warning", "Please select a valid custom palette file.")
                return

        game_root = get_project_root()

        if self.worker:
            self.worker.set_params(
                character_name=char_name,
                output_dir=os.path.join(output_dir, char_name),
                palette_index=palette_idx,
                effect_mode=effect_mode,  # NEW: effect transformation
                custom_palette_path=custom_pal,
                game_root=game_root,
            )

        # Check for existing assets
        full_output_path = os.path.join(output_dir, char_name)
        frames_dir = os.path.join(full_output_path, "frames")
        if os.path.exists(frames_dir) and os.listdir(frames_dir):
            reply = QMessageBox.question(
                self,
                "Existing Assets Found",
                f"Assets for '{char_name}' already exist.\nDo you want to load them directly or re-extract?",
                QMessageBox.StandardButton.Open | QMessageBox.StandardButton.Reset,
                QMessageBox.StandardButton.Open,
            )

            if reply == QMessageBox.StandardButton.Open:
                # Load existing
                if self.action_btn:
                    self.action_btn.setText("Loaded")
                    QTimer.singleShot(
                        1000,
                        lambda: self.action_btn.setText("Extract Sprites and recreate frames")
                        if self.action_btn
                        else None,
                    )
                self.asset_ready.emit(char_name, full_output_path)
                return

        # Update UI state
        self.start_ui_state()

        # Start worker
        # Start worker
        if self.worker:
            self.worker.start()
        self.worker_started.emit()

    def on_worker_complete(self, char_name: str, out_path: str) -> None:
        """Handle worker completion"""
        self.asset_ready.emit(char_name, out_path)
        self.on_complete(char_name, out_path)

    def on_complete(self, *args: Any) -> None:
        """Handle completion"""
        if len(args) >= 2:
            char_name, out_path = args[0], args[1]
            super().on_complete(f"Extraction completed for {char_name}!\nSaved to: {out_path}")
        else:
            super().on_complete(*args)
