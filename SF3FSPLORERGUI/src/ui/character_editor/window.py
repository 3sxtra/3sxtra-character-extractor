"""
Character Extractor window for managing animation sequences and extractions.
"""

import json
import logging
import os

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QAction, QPixmap
from PyQt6.QtWidgets import (
    QDockWidget,
    QMainWindow,
    QMessageBox,
    QTabWidget,
)

from SF3FSPLORERGUI.src.core.workers.gif_exporter import GifExportWorker
from SF3FSPLORERGUI.src.core.workers.mosaic_loader import MosaicLoadWorker
from SF3FSPLORERGUI.src.core.workers.sequence_parser import SequenceParseWorker
from SF3FSPLORERGUI.src.ui.dialogs.progress_dialog import ProgressDialog

# Import the existing CharacterExtractorWidget
from SF3FSPLORERGUI.src.ui.widgets.character_extractor import CharacterExtractorWidget
from SF3FSPLORERGUI.src.ui.widgets.sprite_preview import SpritePreviewPanel

from .about import CharacterExtractorAboutDialog
from .animation_controls import AnimationCanvas, AnimationControlsWidget
from .mosaic_widgets import FrameMosaicWidget, OrganisedFrameMosaicWidget
from .sequence_editor_dialog import SequenceEditorDialog
from .sequences import SequenceBrowserWidget


# pylint: disable=too-many-instance-attributes,too-many-public-methods
class CharacterExtractorWindow(QMainWindow):
    """
    Dedicated window for Character Editing (Extraction + Animation).
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Character Extractor - SF3: 3rd Strike")
        self.resize(1000, 700)

        self.frames_dir = None
        self.current_char_name = None  # Track selected character
        self.total_frames = 0
        self.frame_cache = {}

        # Playback state
        self.is_playing = False
        self.current_frame_idx = 0
        # List of (frame_index, duration_ticks) tuples for current sequence
        self.current_seq_frames: list[tuple[int, int]] = []
        self.seq_play_idx = 0  # Index within current_seq_frames
        self.loop_start = 0
        self.loop_end = 0
        self.timer = QTimer()
        self.timer.timeout.connect(self.on_tick)
        # SF3: 3rd Strike runs at 60 FPS = ~16.67ms per game tick
        self.base_tick_ms = 16.67

        # List of dicts: [{'name': 'Seq 1', 'start': 0, 'end': 10, 'frames':
        # [0,1,2]}]
        self.sequences_data = []

        # Worker references
        self.gif_worker = None
        self.progress_dialog = None

        # Lazy loading for mosaic (defer until tab clicked)
        self._pending_mosaic_frames_dir: str | None = None
        self._pending_mosaic_total_frames: int = 0
        self._mosaic_loaded = False

        # Lazy loading for organised mosaic
        self._pending_organised_frames_dir: str | None = None
        self._organised_mosaic_loaded = False

        # Track current zoom level for lazy application to mosaic tabs
        self._current_zoom: float = 2.0
        self._mosaic_zoom_applied: float = 2.0  # Track last applied zoom
        self._organised_zoom_applied: float = 2.0

        # Background workers for async loading
        self._mosaic_worker: MosaicLoadWorker | None = None
        self._seq_parse_worker: SequenceParseWorker | None = None
        self._preloaded_mosaic_images: list = []  # (idx, QImage) tuples
        self._mosaic_preload_ready = False

        self.setup_ui()

    def setup_ui(self):
        """Set up the UI components for the Character Extractor"""
        # Central Widget: Tab widget with Animation and Mosaic views
        self.central_tabs = QTabWidget()
        self.setCentralWidget(self.central_tabs)

        # Tab 1: Animation Canvas
        self.canvas = AnimationCanvas()
        self.central_tabs.addTab(self.canvas, "Animation")

        # Tab 2: Frame Mosaic
        self.mosaic = FrameMosaicWidget()
        self.central_tabs.addTab(self.mosaic, "Mosaic")

        # Tab 3: Organised Mosaic (New)
        self.organised_mosaic = OrganisedFrameMosaicWidget()
        self.central_tabs.addTab(self.organised_mosaic, "Organised")

        # Connect mosaic frame click to show frame and switch to Animation tab
        self.mosaic.frame_clicked.connect(self._on_mosaic_frame_clicked)
        self.organised_mosaic.frame_clicked.connect(self._on_mosaic_frame_clicked)

        # Tab 4: Palette Preview
        self.sprite_preview = SpritePreviewPanel()
        self.central_tabs.addTab(self.sprite_preview, "Palette")

        # Connect tab change for lazy loading
        self.central_tabs.currentChanged.connect(self._on_tab_changed)

        # Left Dock: Extractor
        self.extractor_dock = QDockWidget("Extractor", self)
        self.extractor_widget = CharacterExtractorWidget()
        self.extractor_dock.setWidget(self.extractor_widget)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.extractor_dock)

        # Bottom Dock: Animation Controls
        self.anim_dock = QDockWidget("Animation Controls", self)
        self.anim_controls = AnimationControlsWidget()
        # Set loop default
        self.anim_controls.loop_chk.setChecked(True)
        self.anim_dock.setWidget(self.anim_controls)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.anim_dock)

        # Right Dock: Sequence Browser (hidden by default)
        self.seq_dock = QDockWidget("Sequences", self)
        self.seq_browser = SequenceBrowserWidget()
        self.seq_dock.setWidget(self.seq_browser)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.seq_dock)
        self.seq_dock.show()  # Visible by default

        # Create View menu for toggling dock widget visibility
        self._setup_view_menu()

        # Connect Signals
        self.extractor_widget.asset_ready.connect(self.on_extraction_complete)
        self.anim_controls.play_requested.connect(self.start_playback)
        self.anim_controls.stop_requested.connect(self.stop_playback)
        self.anim_controls.frame_selected.connect(self.show_frame)
        self.anim_controls.zoom_changed.connect(self._on_zoom_changed)
        self.anim_controls.bg_color_changed.connect(self._on_bg_color_changed)

        # Sequence Control Signals
        self.anim_controls.seq_add_requested.connect(self.add_sequence_manual)
        self.anim_controls.seq_remove_requested.connect(self.remove_sequence_manual)
        self.anim_controls.seq_save_requested.connect(self.save_sequences)
        self.anim_controls.seq_edit_requested.connect(self.open_sequence_editor)
        self.anim_controls.seq_update_requested.connect(self.update_current_sequence)
        self.anim_controls.seq_selected.connect(self.on_sequence_list_selected)
        self.anim_controls.gif_export_requested.connect(self.export_sequence_as_gif)
        self.anim_controls.smart_gif_export_requested.connect(self.export_smart_gif)

        # Unified Selection Logic: Browser now also emits index
        self.seq_browser.sequence_selected.connect(self.on_sequence_list_selected)

        # Connect palette changes to sprite preview for real-time updates
        self.extractor_widget.palette_changed.connect(self.sprite_preview.set_palette)

        # Load AFS preview when character selection changes (before extraction)
        self.extractor_widget.character_selection_changed.connect(self._on_character_selection_for_preview)

    def _setup_view_menu(self) -> None:
        """Set up the View menu for toggling dock widget visibility."""
        menubar = self.menuBar()
        if menubar is None:
            return

        view_menu = menubar.addMenu("&View")
        if view_menu is None:
            return

        # Add toggle actions for each dock widget
        # QDockWidget.toggleViewAction() returns a pre-configured QAction
        view_menu.addAction(self.extractor_dock.toggleViewAction())
        view_menu.addAction(self.anim_dock.toggleViewAction())
        view_menu.addAction(self.seq_dock.toggleViewAction())

        view_menu.addSeparator()

        # Add "Show All" and "Hide All" convenience actions
        show_all_action = QAction("Show All Panels", self)
        show_all_action.triggered.connect(self._show_all_docks)
        view_menu.addAction(show_all_action)

        hide_all_action = QAction("Hide All Panels", self)
        hide_all_action.triggered.connect(self._hide_all_docks)
        view_menu.addAction(hide_all_action)

        # Help menu with About action
        help_menu = menubar.addMenu("&Help")
        if help_menu is None:
            return
        about_action = QAction("&About", self)
        about_action.triggered.connect(self._on_help_about)
        help_menu.addAction(about_action)

    def _show_all_docks(self):
        """Show all dock widgets."""
        self.extractor_dock.show()
        self.anim_dock.show()
        self.seq_dock.show()

    def _hide_all_docks(self):
        """Hide all dock widgets."""
        self.extractor_dock.hide()
        self.anim_dock.hide()
        self.seq_dock.hide()

    def _on_help_about(self):
        """Show the About dialog."""
        try:
            dialog = CharacterExtractorAboutDialog(self)
            dialog.exec()
        except Exception:  # pylint: disable=broad-exception-caught
            QMessageBox.about(
                self,
                "About Character Extractor",
                "SF3:3rd Character Extractor\n\nVersion 1.0.0\n\n"
                "A tool for extracting and viewing character animations "
                "from Street Fighter III: 3rd Strike.",
            )

    def _on_mosaic_frame_clicked(self, frame_index):
        """Handle frame click in mosaic view - switch to Animation tab and show frame."""
        self.show_frame(frame_index)
        self.central_tabs.setCurrentIndex(0)  # Switch to Animation tab

    def _on_tab_changed(self, index):
        """Handle tab change - use preloaded frames if available, fallback to sync."""
        # Mosaic tab is at index 1
        if index == 1:
            if not self._mosaic_loaded:
                if self._mosaic_preload_ready and self._preloaded_mosaic_images:
                    # Background worker finished — apply instantly
                    self._apply_preloaded_mosaic()
                elif self._pending_mosaic_frames_dir and self._pending_mosaic_total_frames > 0:
                    # Worker still running or not started — sync fallback
                    self.mosaic.thumbnail_size = int(64 * self._current_zoom)
                    self.mosaic.load_frames(self._pending_mosaic_frames_dir, self._pending_mosaic_total_frames)
                    self._mosaic_loaded = True
                    self._mosaic_zoom_applied = self._current_zoom
                    logging.debug("Sync-loaded mosaic (worker not ready)")
            # Apply pending zoom if it changed while on another tab
            elif self._mosaic_zoom_applied != self._current_zoom:
                self.mosaic.set_zoom(self._current_zoom)
                self._mosaic_zoom_applied = self._current_zoom

        # Organised tab is at index 2 (inserted before Palette which is now 3)
        elif index == 2:
            if not self._organised_mosaic_loaded and self._pending_organised_frames_dir and self.sequences_data:
                # Set thumbnail size BEFORE loading to use correct zoom level
                self.organised_mosaic.thumbnail_size = int(64 * self._current_zoom)
                self.organised_mosaic.load_sequences(self.sequences_data, self._pending_organised_frames_dir)
                self._organised_mosaic_loaded = True
                self._organised_zoom_applied = self._current_zoom
                logging.debug("Lazy loaded organised mosaic at zoom %.1fx", self._current_zoom)
            # Apply pending zoom if it changed while on another tab
            elif self._organised_zoom_applied != self._current_zoom:
                self.organised_mosaic.set_zoom(self._current_zoom)
                self._organised_zoom_applied = self._current_zoom

    def _on_zoom_changed(self, zoom: float) -> None:
        """Handle zoom change - apply to active tab only for performance.

        Args:
            zoom: New zoom level (1-8)
        """
        self._current_zoom = zoom

        # Always update canvas (Animation tab)
        self.canvas.set_zoom(zoom)

        # Invalidate preloaded mosaic data (wrong thumbnail size now)
        self._mosaic_preload_ready = False
        self._preloaded_mosaic_images.clear()

        # Only update mosaic if it's currently visible (index 1)
        current_tab = self.central_tabs.currentIndex()
        if current_tab == 1 and self._mosaic_loaded:
            self.mosaic.set_zoom(zoom)
            self._mosaic_zoom_applied = zoom
        elif current_tab == 2 and self._organised_mosaic_loaded:
            self.organised_mosaic.set_zoom(zoom)
            self._organised_zoom_applied = zoom

        # Start background preload with new zoom for future tab switches
        if self._pending_mosaic_frames_dir and self._pending_mosaic_total_frames > 0:
            self._start_mosaic_preload(
                self._pending_mosaic_frames_dir, self._pending_mosaic_total_frames
            )

    def _on_bg_color_changed(self, color):
        """Update background color on all three tabs."""
        self.canvas.set_background_color(color)
        self.mosaic.set_background_color(color)
        self.organised_mosaic.set_background_color(color)
        # Update sprite preview background
        if hasattr(self.sprite_preview, "set_background_color"):
            self.sprite_preview.set_background_color(color)

    def on_extraction_complete(self, char_name, out_path):
        """Called when extraction finishes."""
        self.current_char_name = char_name

        frames_dir = os.path.join(out_path, "frames")
        if not os.path.exists(frames_dir) and os.path.basename(out_path) == "frames":
            frames_dir = out_path  # Just in case it passed the frames dir directly

        if os.path.exists(frames_dir):  # pylint: disable=too-many-nested-blocks
            self.load_frames(frames_dir)

            # Update sprite preview panel with real-time palette support
            if hasattr(self, "sprite_preview"):
                # Try to get layout file info for real-time composition
                layout_file = None
                tex_offset = 0
                try:
                    # Import character_data to get layout file path
                    # pylint: disable=import-outside-toplevel
                    from SF3FSPLORERGUI.src.utils.helpers import get_afs_data_source
                    from sf33rd.core.data_model import character_data
                    # pylint: enable=import-outside-toplevel

                    if char_name in character_data:
                        char_info = character_data[char_name]
                        data_source = get_afs_data_source()
                        tex_file = char_info.get("tex", "")
                        if tex_file:
                            # Get layout file path based on source type
                            if data_source.source_type == "folder":
                                layout_file = data_source.get_file_path(str(tex_file))
                            else:
                                # Archive mode: extract to temp
                                import tempfile  # pylint: disable=import-outside-toplevel

                                tex_data = data_source.get_file_data(str(tex_file))
                                temp_dir = tempfile.mkdtemp(prefix="sf33rd_layout_")
                                layout_file = os.path.join(temp_dir, str(tex_file))
                                with open(layout_file, "wb") as f:
                                    f.write(tex_data)
                            to_tex = char_info.get("to_tex", 0)
                            tex_offset = int(str(to_tex)) if to_tex else 0
                except (ImportError, OSError, ValueError) as e:
                    logging.debug("Could not get layout file for real-time: %s", e)

                self.sprite_preview.set_character(
                    char_name,
                    frames_dir,
                    layout_file=layout_file,
                    tex_offset=tex_offset,
                )
                # Get current palette from extractor if available
                # pylint: disable=protected-access
                if hasattr(self.extractor_widget, "_current_char_palette"):
                    pal = self.extractor_widget._current_char_palette
                    if pal:
                        color_idx = 0
                        if self.extractor_widget.palette_color_combo:
                            color_idx = self.extractor_widget.palette_color_combo.currentIndex()
                        colors = pal.get_style_rgb_list(color_idx)
                        self.sprite_preview.set_palette(colors)
        else:
            QMessageBox.warning(self, "Warning", f"Could not find frames directory at: {frames_dir}")

    def _on_character_selection_for_preview(self, char_name: str) -> None:
        """Handle character selection for AFS preview.

        If character hasn't been extracted yet, load a limited preview
        directly from AFS data.
        """
        # Check if this character has already been extracted
        output_path_widget = getattr(self.extractor_widget, "output_path", None)
        output_base = output_path_widget.text() if output_path_widget else ""
        if output_base:
            frames_dir = os.path.join(output_base, char_name, "frames")
            if os.path.exists(frames_dir):
                # Already extracted - don't show AFS preview, extraction will
                # update it
                self.sprite_preview.clear()
                return

        # Try to load AFS preview for unextracted character
        try:
            # pylint: disable=import-outside-toplevel
            from SF3FSPLORERGUI.src.utils.helpers import get_afs_data_source
            from sf33rd.core.data_model import character_data
            # pylint: enable=import-outside-toplevel

            if char_name in character_data:
                char_info = character_data[char_name]
                data_source = get_afs_data_source()
                tex_file = char_info.get("tex", "")
                to_tex = char_info.get("to_tex", 0)
                tex_offset = int(str(to_tex)) if to_tex else 0

                if tex_file:
                    # Get tex_path based on source type
                    if data_source.source_type == "folder":
                        tex_path = data_source.get_file_path(str(tex_file))
                    else:
                        # Archive mode: extract to temp for preview
                        import tempfile  # pylint: disable=import-outside-toplevel

                        tex_data = data_source.get_file_data(str(tex_file))
                        temp_dir = tempfile.mkdtemp(prefix="sf33rd_preview_")
                        tex_path = os.path.join(temp_dir, str(tex_file))
                        with open(tex_path, "wb") as f:
                            f.write(tex_data)
                        logging.info("Extracted %s to temp for preview", tex_file)

                    if tex_path and os.path.exists(tex_path):
                        # tex file contains both sprites and frame layouts
                        self.sprite_preview.set_character_for_afs_preview(char_name, tex_path, tex_offset, tex_path)
                        return
        except (ImportError, OSError, ValueError) as e:
            logging.debug("Could not load AFS preview: %s", e)

        # Fallback: just clear
        self.sprite_preview.clear()

    def load_frames(self, frames_dir):
        """Load frames from the specified directory"""
        self.frames_dir = frames_dir
        self.frame_cache.clear()

        # Count frames
        valid_files = [f for f in os.listdir(frames_dir) if f.lower().endswith(".png") and f.startswith("frame_")]

        # Extract indices
        indices = []
        for f in valid_files:
            try:
                # expected frame_X.png
                parts = f.replace(".png", "").split("_")
                idx = int(parts[-1])
                indices.append(idx)
            except (ValueError, IndexError):
                pass

        if not indices:
            self.total_frames = 0
            self.anim_controls.update_frames_list(0)
            return

        self.total_frames = max(indices) + 1
        self.anim_controls.update_frames_list(self.total_frames)

        # Defer mosaic loading until user clicks Mosaic tab (lazy loading)
        self._pending_mosaic_frames_dir = frames_dir
        self._pending_mosaic_total_frames = self.total_frames
        self._mosaic_loaded = False

        # Reset organised mosaic lazy load
        self._pending_organised_frames_dir = frames_dir
        self._organised_mosaic_loaded = False

        # Start background mosaic preload (eager — loads before user clicks tab)
        self._start_mosaic_preload(frames_dir, self.total_frames)

        # Detect/Load Sequences
        self.load_sequences(frames_dir)

        # Reset default show
        if self.total_frames > 0:
            self.show_frame(0)
            self.loop_start = 0
            self.loop_end = self.total_frames - 1
            # Default: all frames with duration=4 ticks each (~67ms at game
            # speed)
            self.current_seq_frames = [(i, 4) for i in range(self.total_frames)]

            # Init Spinboxes
            self.anim_controls.start_spin.setRange(0, self.total_frames - 1)
            self.anim_controls.end_spin.setRange(0, self.total_frames - 1)

    def load_sequences(self, frames_dir):
        """Loads sequences from JSON (user-saved) or ROM binary (game data).

        Priority order:
        1. User-saved sequences.json (if exists)
        2. ROM binary parsing from game animation tables (nmca, dmca, atca, etc.)

        Note: Visual similarity detection was removed as it's fundamentally flawed
        for fighting game animations where frames within a sequence are visually
        very different (e.g., walk cycles, attack animations).
        """
        self.sequences_data = []

        # 1. Try JSON (User Saved Data) - highest priority
        json_path = os.path.join(frames_dir, "sequences.json")
        if os.path.exists(json_path):
            try:
                with open(json_path, encoding="utf-8") as f:
                    data = json.load(f)
                    for item in data:
                        if "start" in item and "end" in item:
                            if "frames" not in item:
                                item["frames"] = list(range(item["start"], item["end"] + 1))
                            self.sequences_data.append(item)
                logging.info("Loaded %s sequences from JSON", len(self.sequences_data))
            except Exception as e:  # pylint: disable=broad-exception-caught
                logging.error("Failed to load JSON: %s", e)

        # 2. Load ROM sequences from binary (async — on background thread)
        if self.current_char_name:
            self._start_async_sequence_parse(self.current_char_name)

        # 3. If still no sequences, create a simple "All Frames" fallback
        if not self.sequences_data:
            valid_files = [f for f in os.listdir(frames_dir) if f.lower().endswith(".png") and f.startswith("frame_")]
            indices = []
            for f in valid_files:
                try:
                    parts = f.replace(".png", "").split("_")
                    indices.append(int(parts[-1]))
                except (ValueError, IndexError):
                    pass

            if indices:
                sorted_indices = sorted(indices)
                self.sequences_data.append(
                    {
                        "name": "All Frames",
                        "start": sorted_indices[0],
                        "end": sorted_indices[-1],
                        "frames": sorted_indices,
                    }
                )
                logging.info("Created fallback 'All Frames' sequence with %d frames", len(sorted_indices))

        self.refresh_sequence_ui()

    # -----------------------------------------------------------------
    # Background Worker Handlers
    # -----------------------------------------------------------------

    def _start_mosaic_preload(self, frames_dir: str, total_frames: int) -> None:
        """Start background loading of mosaic frames (eager — before tab click)."""
        # Cancel any running worker
        if self._mosaic_worker and self._mosaic_worker.isRunning():
            self._mosaic_worker.cancel()
            self._mosaic_worker.wait(2000)

        self._mosaic_preload_ready = False
        self._preloaded_mosaic_images.clear()

        thumbnail_size = int(64 * self._current_zoom)

        self._mosaic_worker = MosaicLoadWorker()
        self._mosaic_worker.set_params(frames_dir, total_frames, thumbnail_size)
        self._mosaic_worker.frames_loaded.connect(self._on_mosaic_preload_complete)
        self._mosaic_worker.start()

        logging.info("Started background mosaic loading for %d frames", total_frames)

    def _on_mosaic_preload_complete(self, frames: list) -> None:
        """Handle mosaic background loading completion."""
        self._preloaded_mosaic_images = frames
        self._mosaic_preload_ready = True

        logging.info("Mosaic preload complete: %d frames ready", len(frames))

        # If user is already on the mosaic tab, apply immediately
        current_tab = self.central_tabs.currentIndex()
        if current_tab == 1 and not self._mosaic_loaded:
            self._apply_preloaded_mosaic()

        # Pre-warm organised mosaic cache too
        if self._pending_organised_frames_dir:
            image_cache = dict(frames)
            self.organised_mosaic.set_image_cache(image_cache)

    def _apply_preloaded_mosaic(self) -> None:
        """Apply preloaded mosaic frames to the mosaic widget."""
        if not self._mosaic_preload_ready or not self._preloaded_mosaic_images:
            return

        self.mosaic.set_preloaded_frames(
            self._pending_mosaic_frames_dir or "",
            self._pending_mosaic_total_frames,
            self._preloaded_mosaic_images,
        )
        self._mosaic_loaded = True
        self._mosaic_zoom_applied = self._current_zoom
        logging.info(
            "Applied preloaded mosaic with %d frames",
            len(self._preloaded_mosaic_images),
        )

    def _start_async_sequence_parse(self, char_name: str) -> None:
        """Start background parsing of ROM binary sequences."""
        if self._seq_parse_worker and self._seq_parse_worker.isRunning():
            self._seq_parse_worker.cancel()
            self._seq_parse_worker.wait(2000)

        self._seq_parse_worker = SequenceParseWorker()
        self._seq_parse_worker.set_params(char_name)
        self._seq_parse_worker.sequences_parsed.connect(self._on_sequences_parsed)
        self._seq_parse_worker.start()

        logging.info("Started background sequence parsing for %s", char_name)

    def _on_sequences_parsed(self, rom_sequences: list) -> None:
        """Handle background sequence parsing completion."""
        if rom_sequences:
            logging.info(
                "Received %d ROM sequences from background parser",
                len(rom_sequences),
            )
            for seq in rom_sequences:
                self.sequences_data.append(seq)
            self.refresh_sequence_ui()

    def closeEvent(self, event) -> None:  # noqa: N802
        """Cancel any running workers before closing."""
        if self._mosaic_worker and self._mosaic_worker.isRunning():
            self._mosaic_worker.cancel()
            self._mosaic_worker.wait(1000)
        if self._seq_parse_worker and self._seq_parse_worker.isRunning():
            self._seq_parse_worker.cancel()
            self._seq_parse_worker.wait(1000)
        super().closeEvent(event)

    def refresh_sequence_ui(self):
        """Updates both the Bottom List and Right Visual Browser."""

        # 1. Update Visual Browser
        self.seq_browser.clear()

        # 2. Update Control List
        self.anim_controls.seq_list.clear()

        for i, seq in enumerate(self.sequences_data):
            # Get frames - can be list of ints or list of (idx, duration)
            # tuples
            frames = seq.get("frames", [])

            # Handle both formats: int or (frame_idx, duration) tuple
            if frames:
                first_frame = frames[0]
                start = first_frame[0] if isinstance(first_frame, tuple) else first_frame
            else:
                start = 0

            name = seq.get("name", f"Seq {i + 1}")

            # Calc length
            length = len(frames)
            display_name = f"{name} ({length} fr)"

            # Get table type for grouping (from ROM parsing), default to
            # "manual"
            table_type = seq.get("table", "manual")
            # Handle "All Frames" fallback sequence
            if name == "All Frames":
                table_type = "all"

            # Visual Browser - pass table_type for family grouping
            icon_pix = self.get_frame_pixmap(start)
            self.seq_browser.add_sequence(display_name, icon_pix, i, table_type)

            # Bottom List
            self.anim_controls.seq_list.addItem(display_name)

        # Update organised mosaic if it's already loaded or visible
        if (self._organised_mosaic_loaded or self.central_tabs.currentIndex() == 2) and self.frames_dir:
            self.organised_mosaic.load_sequences(self.sequences_data, self.frames_dir)
            self._organised_mosaic_loaded = True

    def add_sequence_manual(self):
        """Manually add a sequence from the current range"""
        start = self.anim_controls.start_spin.value()
        end = self.anim_controls.end_spin.value()

        if start > end:
            start, end = end, start

        frames = list(range(start, end + 1))

        new_seq = {"name": f"Seq {len(self.sequences_data) + 1}", "start": start, "end": end, "frames": frames}
        self.sequences_data.append(new_seq)
        self.refresh_sequence_ui()
        # Select last
        self.anim_controls.seq_list.setCurrentRow(len(self.sequences_data) - 1)

    def remove_sequence_manual(self):
        """Manually remove the selected sequence"""
        row = self.anim_controls.seq_list.currentRow()
        if 0 <= row < len(self.sequences_data):
            del self.sequences_data[row]
            self.refresh_sequence_ui()

    def open_sequence_editor(self):
        """Open the sequence editor dialog for the selected sequence."""
        row = self.anim_controls.seq_list.currentRow()
        if row < 0 or row >= len(self.sequences_data):
            QMessageBox.warning(self, "No Sequence Selected", "Please select a sequence to edit.")
            return

        if not self.frames_dir:
            QMessageBox.warning(self, "No Frames", "No frames directory loaded.")
            return

        seq_data = self.sequences_data[row]
        dialog = SequenceEditorDialog(
            sequence_data=seq_data,
            frames_dir=self.frames_dir,
            total_frames=self.total_frames,
            parent=self,
        )

        if dialog.exec():
            # User clicked OK - update the sequence with edited data
            result = dialog.get_result()
            self.sequences_data[row] = result

            # Preserve table info if it existed
            if "table" in seq_data:
                self.sequences_data[row]["table"] = seq_data["table"]
            if "index" in seq_data:
                self.sequences_data[row]["index"] = seq_data["index"]

            self.refresh_sequence_ui()
            self.anim_controls.seq_list.setCurrentRow(row)

            logging.info("Sequence '%s' updated with %d frames", result.get("name"), len(result.get("frames", [])))

    def update_current_sequence(self, start, end):
        """Update the selected sequence with a new range"""
        row = self.anim_controls.seq_list.currentRow()
        if 0 <= row < len(self.sequences_data):
            self.sequences_data[row]["start"] = start
            self.sequences_data[row]["end"] = end
            self.sequences_data[row]["frames"] = list(range(start, end + 1))

            self.refresh_sequence_ui()
            self.anim_controls.seq_list.setCurrentRow(row)

    def on_sequence_list_selected(self, row):
        """Handle sequence list selection (from both widgets now)"""
        if 0 <= row < len(self.sequences_data):
            seq = self.sequences_data[row]
            # Update spinboxes (block signals to prevent loop)
            self.anim_controls.start_spin.blockSignals(True)
            self.anim_controls.end_spin.blockSignals(True)

            self.anim_controls.start_spin.setValue(seq["start"])
            self.anim_controls.end_spin.setValue(seq["end"])

            self.anim_controls.start_spin.blockSignals(False)
            self.anim_controls.end_spin.blockSignals(False)

            # Sync selection in both widgets if not already
            if self.anim_controls.seq_list.currentRow() != row:
                self.anim_controls.seq_list.setCurrentRow(row)

            # Play
            self.play_sequence_from_data(seq)

            # Ensure "Loop" is respected implies starting play will Loop if checked.
            # play_sequence_from_data calls start_playback.

    def save_sequences(self):
        """Save sequences to sequences.json"""
        if not self.frames_dir:
            return
        json_path = os.path.join(self.frames_dir, "sequences.json")
        try:
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(self.sequences_data, f, indent=4)
            QMessageBox.information(self, "Saved", "Sequences saved successfully.")
        except Exception as e:  # pylint: disable=broad-exception-caught
            QMessageBox.critical(self, "Error", f"Failed to save sequences: {e}")

    def get_frame_pixmap(self, idx):
        """Get the pixmap for a specific frame index (cached)"""
        if idx in self.frame_cache:
            return self.frame_cache[idx]

        if not self.frames_dir:
            return None

        path = os.path.join(self.frames_dir, f"frame_{idx}.png")
        if os.path.exists(path):
            pix = QPixmap(path)
            if not pix.isNull():
                self.frame_cache[idx] = pix
                return pix
        return None

    def show_frame(self, idx):
        """Display a specific frame index"""
        pix = self.get_frame_pixmap(idx)
        self.canvas.set_frame(pix)
        self.anim_controls.frame_lbl.setText(f"Frame: {idx}")
        self.anim_controls.filename_lbl.setText(f"File: frame_{idx}.png")

    def start_playback(self):
        """Start animation playback"""
        if self.total_frames == 0:
            return
        self.is_playing = True
        self.anim_controls.set_playing(True)

        # Start with the duration of the first frame
        self._schedule_next_frame()

    def stop_playback(self):
        """Stop animation playback"""
        self.is_playing = False
        self.anim_controls.set_playing(False)
        self.timer.stop()

    def play_sequence_from_data(self, seq_data):
        """Play using full sequence data"""
        frames = seq_data.get("frames", [])
        # Handle both old format (list of ints) and new format (list of tuples)
        if frames and not isinstance(frames[0], (list, tuple)):
            # Old format: convert to (index, duration=4) tuples (~67ms per
            # frame)
            self.current_seq_frames = [(f, 4) for f in frames]
            logging.debug("Using OLD format (plain indices), default duration=4")
        else:
            self.current_seq_frames = frames if frames else [(0, 4)]
            logging.debug("Using NEW format (tuples with duration)")

        # Debug: Log first few frame durations
        if self.current_seq_frames:
            sample = self.current_seq_frames[:5]
            logging.info("Sequence frames sample: %s", sample)

        self.seq_play_idx = 0
        first_frame_idx = self.current_seq_frames[0][0]
        self.show_frame(first_frame_idx)
        self.start_playback()

    def _schedule_next_frame(self):
        """Calculate and schedule the timer for the current frame's duration."""
        if not self.current_seq_frames or self.seq_play_idx >= len(self.current_seq_frames):
            return

        # Get current frame's duration in game ticks
        _, duration_ticks = self.current_seq_frames[self.seq_play_idx]
        duration_ticks = max(duration_ticks, 1)

        # Calculate actual delay: duration_ticks × base_tick_ms × (100 /
        # speed%)
        speed_percent = self.anim_controls.speed_spin.value()
        speed_percent = max(speed_percent, 10)

        delay_ms = int(duration_ticks * self.base_tick_ms * (100.0 / speed_percent))
        delay_ms = max(1, delay_ms)  # Minimum 1ms

        self.timer.start(delay_ms)

    def on_tick(self):
        """Timer tick for animation playback"""
        if not self.is_playing:
            return

        if not self.current_seq_frames:
            # Fallback: all frames with duration=4 ticks
            self.current_seq_frames = [(i, 4) for i in range(self.total_frames)]

        # Move to next frame in SEQUENCE LIST
        range_len = len(self.current_seq_frames)

        next_idx = self.seq_play_idx + 1

        if next_idx >= range_len:
            # Check Loop Logic
            if self.anim_controls.loop_chk.isChecked():
                next_idx = 0
            else:
                # Stop at end
                self.stop_playback()
                return

        self.seq_play_idx = next_idx
        frame_idx, _ = self.current_seq_frames[self.seq_play_idx]
        self.current_frame_idx = frame_idx
        self.show_frame(self.current_frame_idx)

        # Schedule next frame with its duration
        self._schedule_next_frame()

    def export_sequence_as_gif(self):
        """Export current sequence as GIF"""
        if not self.frames_dir or self.total_frames == 0:
            QMessageBox.warning(self, "Warning", "No frames loaded.")
            return

        # Get current sequence info
        row = self.anim_controls.seq_list.currentRow()

        frames_to_export = []
        seq_name = "custom_sequence"

        if row < 0:
            # Fallback to current tick buffer?
            frames_to_export = self.current_seq_frames
        else:
            seq_data = self.sequences_data[row]
            frames_to_export = seq_data.get("frames", [])
            seq_name = seq_data.get("name", f"sequence_{row}")

        # sanitize filename
        safe_name = "".join([c for c in seq_name if c.isalnum() or c in (" ", "_", "-")]).strip()
        safe_name = safe_name.replace(" ", "_").lower()
        if not safe_name:
            safe_name = "sequence"

        # Determine output path: .../characters/{CharName}/animations/{SeqName}.gif
        # frames_dir is typically .../output/characters/{CharName}/frames
        char_dir = os.path.dirname(self.frames_dir)
        anim_dir = os.path.join(char_dir, "animations")

        if not os.path.exists(anim_dir):
            os.makedirs(anim_dir)

        output_path = os.path.join(anim_dir, f"{safe_name}.gif")

        # Collect frames and durations in a single pass to handle duplicates correctly
        speed_pct = self.anim_controls.speed_spin.value() / 100.0
        frame_paths = []
        valid_durations = []
        for frame_item in frames_to_export:
            frame_idx = frame_item[0] if isinstance(frame_item, (list, tuple)) else frame_item
            path = os.path.join(self.frames_dir, f"frame_{frame_idx}.png")
            if not os.path.exists(path):
                continue
            frame_paths.append(path)
            # Compute duration from game ticks
            if isinstance(frame_item, (list, tuple)) and len(frame_item) >= 2:
                ticks = frame_item[1]
            else:
                ticks = 4  # Default 4 ticks
            ms = int(ticks * (1000.0 / 60.0) / speed_pct)
            valid_durations.append(max(20, ms))  # GIF min is ~20ms

        if not frame_paths:
            QMessageBox.warning(self, "Warning", "No valid frames found in range.")
            return

        self.gif_worker = GifExportWorker(frame_paths, output_path, durations=valid_durations)
        self.gif_worker.gif_created.connect(self.on_gif_export_complete)
        self.gif_worker.export_error.connect(self.on_gif_export_error)

        # Show progress
        self.progress_dialog = ProgressDialog("Exporting GIF", "Initializing...", self, show_details=False)
        self.gif_worker.export_progress.connect(self.progress_dialog.set_progress)
        self.progress_dialog.cancelled.connect(self.gif_worker.cancel)

        self.gif_worker.start()
        self.progress_dialog.show()

    def on_gif_export_complete(self, output_path):
        """Handle GIF export success"""
        if self.progress_dialog is not None:
            self.progress_dialog.close()

        QMessageBox.information(self, "Export Complete", f"GIF exported successfully to:\n{output_path}")

    def on_gif_export_error(self, message):
        """Handle GIF export error"""
        if self.progress_dialog is not None:
            self.progress_dialog.close()

        QMessageBox.critical(self, "Export Error", f"Failed to export GIF:\n{message}")

    def export_smart_gif(self, scale_factor: int) -> None:
        """Export current sequence as a smart-cropped, upscaled GIF."""
        if not self.frames_dir or self.total_frames == 0:
            QMessageBox.warning(self, "Warning", "No frames loaded.")
            return

        row = self.anim_controls.seq_list.currentRow()
        frames_to_export = []
        seq_name = "custom_sequence"

        if row < 0:
            frames_to_export = self.current_seq_frames
        else:
            seq_data = self.sequences_data[row]
            frames_to_export = seq_data.get("frames", [])
            seq_name = seq_data.get("name", f"sequence_{row}")

        safe_name = "".join([c for c in seq_name if c.isalnum() or c in (" ", "_", "-")]).strip()
        safe_name = safe_name.replace(" ", "_").lower()
        if not safe_name:
            safe_name = "sequence"

        char_dir = os.path.dirname(self.frames_dir)
        anim_dir = os.path.join(char_dir, "animations")
        if not os.path.exists(anim_dir):
            os.makedirs(anim_dir)

        suffix = f"_smart_{scale_factor}x" if scale_factor > 1 else "_smart"
        output_path = os.path.join(anim_dir, f"{safe_name}{suffix}.gif")

        frame_paths = []
        for frame_item in frames_to_export:
            frame_idx = frame_item[0] if isinstance(frame_item, (list, tuple)) else frame_item
            path = os.path.join(self.frames_dir, f"frame_{frame_idx}.png")
            if os.path.exists(path):
                frame_paths.append(path)

        if not frame_paths:
            QMessageBox.warning(self, "Warning", "No valid frames found in range.")
            return

        # Compute per-frame durations from game ticks (60 FPS base)
        speed_pct = self.anim_controls.speed_spin.value() / 100.0
        valid_durations = []
        for frame_item in frames_to_export:
            frame_idx = frame_item[0] if isinstance(frame_item, (list, tuple)) else frame_item
            path = os.path.join(self.frames_dir, f"frame_{frame_idx}.png")
            if not os.path.exists(path):
                continue
            if isinstance(frame_item, (list, tuple)) and len(frame_item) >= 2:
                ticks = frame_item[1]
            else:
                ticks = 4
            ms = int(ticks * (1000.0 / 60.0) / speed_pct)
            valid_durations.append(max(20, ms))

        self.gif_worker = GifExportWorker(
            frame_paths, output_path, durations=valid_durations,
            smart_crop=True, scale_factor=scale_factor,
        )
        self.gif_worker.gif_created.connect(self.on_gif_export_complete)
        self.gif_worker.export_error.connect(self.on_gif_export_error)

        self.progress_dialog = ProgressDialog(
            "Exporting Smart GIF", "Computing crop region...", self, show_details=False
        )
        self.gif_worker.export_progress.connect(self.progress_dialog.set_progress)
        self.progress_dialog.cancelled.connect(self.gif_worker.cancel)

        self.gif_worker.start()
        self.progress_dialog.show()
