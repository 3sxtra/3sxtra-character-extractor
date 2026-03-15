"""
Sprite Preview Panel for displaying character frames with palette preview.

Inspired by PalMod's sprite preview, displays a grid of representative
character frames with the currently selected palette applied.
"""

import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
from PyQt6.QtCore import QEvent, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QImage, QPainter, QPixmap
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLayout,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from PIL import Image

logger = logging.getLogger(__name__)

# Lazy import to avoid circular dependencies
_composer_class = None  # pylint: disable=invalid-name


def _get_composer_class():  # type: ignore[return]
    """Lazy load PreviewFrameComposer to avoid import issues."""
    global _composer_class  # noqa: PLW0603  # pylint: disable=global-statement
    if _composer_class is None:
        try:
            # pylint: disable=import-outside-toplevel
            from sf33rd.operations.preview_composer import PreviewFrameComposer

            _composer_class = PreviewFrameComposer
        except ImportError:
            _composer_class = None
    return _composer_class


from SF3FSPLORERGUI.src.utils.image_crop import auto_crop_pixmap


def _auto_crop_pixmap(pixmap: QPixmap, padding: int = 4) -> QPixmap:
    """Wrapper preserving the original padding=4 default for sprite preview."""
    return auto_crop_pixmap(pixmap, padding=padding)


class SpritePreviewPanel(QWidget):
    """PalMod-style sprite preview panel.

    Displays a grid of representative character frames with the
    currently selected palette applied. Updates in real-time when
    palette selection changes.
    """

    frame_clicked = pyqtSignal(int)  # Emitted when a frame is clicked

    # Representative frame indices to show (can be customized)
    # These are typically: idle, walk, punch, kick, special, etc.
    DEFAULT_PREVIEW_FRAMES = [0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100, 110]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.frames_dir: str | None = None
        self.character_name: str = ""
        self.preview_frame_indices: list[int] = []
        self.current_palette: list[tuple[int, int, int]] = []
        self.frame_widgets: list[QLabel] = []
        self.indexed_frames: dict[int, QImage] = {}  # Cache of indexed frames
        self._strip_label: QLabel | None = None

        # Real-time palette support
        self._composer = None  # PreviewFrameComposer instance
        self._use_realtime_palette = False
        self._layout_file: str | None = None
        self._tex_offset: int = 0

        # AFS preview mode (for unextracted characters)
        self._afs_preview_mode = False
        self._afs_sprites: dict[int, bytes] = {}  # Cached raw sprite bytes
        self._afs_sprite_dims: dict[int, tuple[int, int]] = {}  # Sprite dimensions
        self._afs_composer = None  # AfsPreviewComposer instance

        self.setup_ui()

    def setup_ui(self) -> None:
        """Initialize the UI components."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # Header: palette strip + character name
        header = QHBoxLayout()
        header.setSpacing(8)

        # Character name label (first for better visibility)
        self.name_label = QLabel("")
        self.name_label.setStyleSheet("font-weight: bold; font-size: 14px; color: #ffffff;")
        header.addWidget(self.name_label)

        # Palette strip (shows all 64 colors)
        self._strip_label = QLabel()
        self._strip_label.setFixedHeight(16)
        self._strip_label.setMinimumWidth(256)
        self._strip_label.setStyleSheet("background-color: #333333;")
        header.addWidget(self._strip_label)
        header.addStretch()

        layout.addLayout(header)

        # Scroll area for frame grid
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setMinimumHeight(120)
        scroll.setStyleSheet("QScrollArea { border: none; background: #1e1e1e; }")

        # Container for frame grid (flow layout)
        self.grid_container = QWidget()
        self.grid_container.setStyleSheet("background: #1e1e1e;")
        self.flow_layout = QVBoxLayout(self.grid_container)
        self.flow_layout.setContentsMargins(4, 4, 4, 4)
        self.flow_layout.setSpacing(4)
        self.flow_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        scroll.setWidget(self.grid_container)
        layout.addWidget(scroll)

        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        # Store scroll ref for background color changes
        self._scroll_area = scroll

    def set_background_color(self, color: QColor) -> None:
        """Set the background color of the preview panel."""
        color_name = color.name()
        self._scroll_area.setStyleSheet(f"QScrollArea {{ border: none; background: {color_name}; }}")
        self.grid_container.setStyleSheet(f"background: {color_name};")

    def set_character(
        self,
        name: str,
        frames_dir: str,
        layout_file: str | None = None,
        tex_offset: int = 0,
    ) -> None:
        """Set the character to preview.

        Args:
            name: Character display name
            frames_dir: Directory containing extracted frame/sprite data
            layout_file: Path to character .bin file (for real-time mode)
            tex_offset: Offset to texture table in layout file
        """
        self.character_name = name
        self.frames_dir = frames_dir
        self._layout_file = layout_file
        self._tex_offset = tex_offset
        self.name_label.setText(name)
        self.indexed_frames.clear()
        self._composer = None
        self._use_realtime_palette = False

        # Clear existing preview (important for unextracted characters)
        for widget in self.frame_widgets:
            widget.deleteLater()
        self.frame_widgets.clear()
        self.preview_frame_indices = []

        # Check if frames_dir exists
        if not frames_dir or not os.path.exists(frames_dir):
            logger.debug("Frames directory not found: %s", frames_dir)
            return

        # Check if we can use real-time palette mode
        # Requires: sprites/ dir with indexed sprites + layout file
        sprites_dir = Path(frames_dir).parent / "sprites" if frames_dir else None
        if sprites_dir and sprites_dir.exists() and layout_file:
            self._init_realtime_mode(str(sprites_dir), layout_file, tex_offset)

        # Discover available frames and select representative ones
        self._discover_preview_frames()
        self._update_preview_grid()

    def _init_realtime_mode(
        self,
        sprites_dir: str,
        layout_file: str,
        tex_offset: int,
    ) -> None:
        """Initialize real-time palette mode with PreviewFrameComposer."""
        composer_class = _get_composer_class()
        if composer_class is None:
            logger.warning("PreviewFrameComposer not available")
            return

        try:
            self._composer = composer_class(
                sprite_dir=sprites_dir,
                layout_file=layout_file,
                tex_offset=tex_offset,
            )
            self._use_realtime_palette = True
            logger.info(
                "Real-time palette mode enabled for %s (%d frames)",
                self.character_name,
                self._composer.get_frame_count(),
            )
        except (OSError, ValueError) as e:
            logger.warning("Failed to init real-time mode: %s", e)
            self._composer = None
            self._use_realtime_palette = False

    def _discover_preview_frames(self) -> None:
        """Find representative frames to display."""
        if not self.frames_dir or not os.path.exists(self.frames_dir):
            self.preview_frame_indices = []
            return

        # Find all available frame indices
        available = []
        for filename in os.listdir(self.frames_dir):
            if filename.startswith("frame_") and filename.endswith(".png"):
                try:
                    idx = int(filename.replace("frame_", "").replace(".png", ""))
                    available.append(idx)
                except ValueError:
                    continue

        if not available:
            self.preview_frame_indices = []
            return

        available.sort()
        total = len(available)

        # Select ~12 evenly spaced frames for preview
        if total <= 12:
            self.preview_frame_indices = available
        else:
            step = total // 12
            self.preview_frame_indices = [available[i * step] for i in range(12)]

        logger.info("Selected %d preview frames for %s", len(self.preview_frame_indices), self.character_name)

    def _load_indexed_frames(self) -> None:
        """Load indexed frame images for palette application.

        Note: Currently disabled because the sprites/ directory contains raw
        sprite tiles with different indexing than composed frames. For real-time
        palette swapping, we would need indexed versions of the composed frames.
        """
        # Disabled: sprites have different numbering than composed frames
        # For now, we always use pre-rendered frames from frames/ directory
        logger.debug("Indexed frame loading disabled, using pre-rendered frames")

    def set_palette(self, colors: list[tuple[int, int, int]]) -> None:
        """Set the palette and update preview.

        Args:
            colors: List of (r, g, b) tuples (64 colors)
        """
        self.current_palette = list(colors)

        # Update composer palette for real-time rendering
        if self._composer and self._use_realtime_palette:
            self._composer.set_palette(colors)

        # Update AFS composer palette
        if self._afs_composer:
            self._afs_composer.set_palette(colors)

        self._update_palette_strip()

        # Update preview based on mode
        if self._afs_preview_mode:
            self._refresh_afs_preview()
        else:
            self._update_preview_grid()

    def _refresh_afs_preview(self) -> None:
        """Refresh AFS preview sprites with current palette."""
        # Clear existing widgets
        for widget in self.frame_widgets:
            widget.deleteLater()
        self.frame_widgets.clear()

        # Re-render with new palette (use correct method based on mode)
        if self._afs_composer:
            self._update_afs_frame_grid()
        else:
            self._update_afs_preview_grid()

    def _update_palette_strip(self) -> None:
        """Update the palette strip display."""
        if not self.current_palette or not self._strip_label:
            return

        # Create pixmap showing all 64 colors (16x16 per color)
        num_colors = min(64, len(self.current_palette))
        color_width = 12
        strip_height = 16
        strip_width = num_colors * color_width
        strip = QPixmap(strip_width, strip_height)
        strip.fill(QColor(51, 51, 51))

        painter = QPainter(strip)
        for i, (r, g, b) in enumerate(self.current_palette[:64]):
            painter.fillRect(i * color_width, 0, color_width, strip_height, QColor(r, g, b))
        painter.end()

        self._strip_label.setFixedSize(strip_width, strip_height)
        self._strip_label.setPixmap(strip)

    def _update_preview_grid(self) -> None:
        """Update the sprite preview grid with current palette (flow layout)."""
        # Clear existing widgets and layouts
        self._clear_flow_layout()

        if not self.frames_dir or not self.preview_frame_indices:
            return

        num_frames = len(self.preview_frame_indices)
        if num_frames == 0:
            return

        # Get viewport dimensions with fallback
        viewport = self._scroll_area.viewport()
        viewport_width = viewport.width() if viewport else 100
        viewport_height = viewport.height() if viewport else 100

        # Use sensible defaults if viewport not ready
        if viewport_width <= 100:
            viewport_width = 800
        if viewport_height <= 100:
            viewport_height = 400

        viewport_width -= 16  # Margins
        viewport_height -= 16

        # Calculate target height based on frame count
        # Fewer frames = larger size to fill viewport
        if num_frames <= 4:
            target_sprite_height = max(150, viewport_height - 50)
        elif num_frames <= 8:
            target_sprite_height = max(120, viewport_height // 2)
        else:
            target_sprite_height = max(100, viewport_height // 3)

        # Create row layouts and place widgets
        current_row = QHBoxLayout()
        current_row.setSpacing(4)
        current_row.setContentsMargins(0, 0, 0, 0)
        current_row_width = 0

        for idx in self.preview_frame_indices:
            frame_label = QLabel()
            frame_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            frame_label.setCursor(Qt.CursorShape.PointingHandCursor)
            frame_label.setToolTip(f"Frame {idx}")

            # Try to get palettized sprite, otherwise use pre-rendered frame
            pixmap = self._render_frame_with_palette(idx)
            sprite_width = 80  # Default
            if pixmap and not pixmap.isNull():
                # Scale to target height (both up and down for consistent
                # sizing)
                if pixmap.height() != target_sprite_height and pixmap.height() > 0:
                    scaled = pixmap.scaledToHeight(target_sprite_height, Qt.TransformationMode.FastTransformation)
                else:
                    scaled = pixmap
                sprite_width = scaled.width()
                frame_label.setPixmap(scaled)

            # Make clickable using installEventFilter
            frame_label.setProperty("frame_idx", idx)
            frame_label.installEventFilter(self)

            # Check if we need to start a new row
            if current_row_width + sprite_width > viewport_width and current_row_width > 0:
                # Finalize current row
                current_row.addStretch()
                self.flow_layout.addLayout(current_row)
                # Start new row
                current_row = QHBoxLayout()
                current_row.setSpacing(4)
                current_row.setContentsMargins(0, 0, 0, 0)
                current_row_width = 0

            current_row.addWidget(frame_label)
            self.frame_widgets.append(frame_label)
            current_row_width += sprite_width + 4

        # Add the last row
        if current_row.count() > 0:
            current_row.addStretch()
            self.flow_layout.addLayout(current_row)

        # Add stretch at bottom
        self.flow_layout.addStretch()

    def _clear_flow_layout(self) -> None:
        """Clear all widgets from the flow layout."""
        for frame_widget in self.frame_widgets:
            frame_widget.deleteLater()
        self.frame_widgets.clear()

        # Clear row layouts
        while self.flow_layout.count():
            item = self.flow_layout.takeAt(0)
            if item is None:
                continue
            child_widget = item.widget()
            if child_widget:
                child_widget.deleteLater()
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

    def showEvent(self, event) -> None:  # noqa: N802
        """Handle show event to reflow when tab becomes visible."""
        super().showEvent(event)
        if self.preview_frame_indices:
            # Deferred to ensure geometry is ready
            from PyQt6.QtCore import QTimer  # pylint: disable=import-outside-toplevel

            if self._afs_preview_mode and self._afs_composer:
                QTimer.singleShot(0, self._update_afs_frame_grid)
            elif self._afs_preview_mode and self._afs_sprites:
                QTimer.singleShot(0, self._update_afs_preview_grid)
            else:
                QTimer.singleShot(0, self._update_preview_grid)

    def resizeEvent(self, event) -> None:  # noqa: N802
        """Handle resize to reflow the grid."""
        super().resizeEvent(event)
        if self.frame_widgets and self.preview_frame_indices:
            if self._afs_preview_mode and self._afs_composer:
                self._update_afs_frame_grid()
            elif self._afs_preview_mode and self._afs_sprites:
                self._update_afs_preview_grid()
            else:
                self._update_preview_grid()

    def eventFilter(self, obj, event) -> bool:  # noqa: N802
        """Handle click events on frame labels."""
        if event.type() == QEvent.Type.MouseButtonPress:
            frame_idx = obj.property("frame_idx")
            if frame_idx is not None:
                self.frame_clicked.emit(frame_idx)
                return True
        return super().eventFilter(obj, event)

    def _render_frame_with_palette(self, frame_idx: int) -> QPixmap | None:
        """Render a frame with the current palette applied.

        Uses PreviewFrameComposer for real-time composition when available,
        otherwise falls back to pre-rendered frames.

        Args:
            frame_idx: Frame index to render

        Returns:
            QPixmap with palette applied, or None if failed
        """
        if not self.frames_dir:
            return None

        # Real-time composition mode: use PreviewFrameComposer
        if self._use_realtime_palette and self._composer and self.current_palette:
            pil_image = self._composer.compose_frame(frame_idx)
            if pil_image is not None:
                # Convert PIL Image to QPixmap
                pixmap = self._pil_to_qpixmap(pil_image)
                if pixmap and not pixmap.isNull():
                    return _auto_crop_pixmap(pixmap)

        # Try legacy indexed frame method
        if frame_idx in self.indexed_frames and self.current_palette:
            return self._apply_palette_to_indexed(frame_idx)

        # Fall back to pre-rendered frame
        frame_path = os.path.join(self.frames_dir, f"frame_{frame_idx}.png")
        if os.path.exists(frame_path):
            pixmap = QPixmap(frame_path)
            # Auto-crop to remove transparent margins
            return _auto_crop_pixmap(pixmap)

        return None

    def _pil_to_qpixmap(self, pil_image: "Image.Image") -> QPixmap | None:
        """Convert a PIL Image to QPixmap."""
        if pil_image is None:
            return None
        try:
            # Ensure RGBA format
            if pil_image.mode != "RGBA":
                pil_image = pil_image.convert("RGBA")

            width, height = pil_image.size
            data = pil_image.tobytes("raw", "RGBA")

            qimage = QImage(
                data,
                width,
                height,
                width * 4,
                QImage.Format.Format_RGBA8888,
            ).copy()  # .copy() to own the data

            return QPixmap.fromImage(qimage)
        except (OSError, ValueError) as e:
            logger.warning("Failed to convert PIL to QPixmap: %s", e)
            return None

    def _apply_palette_to_indexed(self, frame_idx: int) -> QPixmap | None:
        """Apply current palette to an indexed frame using numpy for speed.

        Args:
            frame_idx: Frame index to render

        Returns:
            QPixmap with palette applied
        """
        indexed_img = self.indexed_frames.get(frame_idx)
        if indexed_img is None or not self.current_palette:
            return None

        width = indexed_img.width()
        height = indexed_img.height()

        # Convert QImage to numpy array (grayscale)
        indexed = indexed_img.convertToFormat(QImage.Format.Format_Grayscale8)
        ptr = indexed.bits()
        if ptr is None:
            return None
        ptr.setsize(height * indexed.bytesPerLine())
        indices = (
            np.frombuffer(
                bytes(ptr),  # type: ignore[call-overload]
                dtype=np.uint8,
            )
            .reshape((height, indexed.bytesPerLine()))[:, :width]
            .copy()
        )

        # Build palette lookup table (256 entries for 8-bit indices)
        # RGBA format: [R, G, B, A]
        lut = np.zeros((256, 4), dtype=np.uint8)
        for i, (r, g, b) in enumerate(self.current_palette[:64]):
            lut[i] = [r, g, b, 255 if i > 0 else 0]  # Index 0 = transparent

        # Apply palette using lookup
        rgba = lut[indices]  # Shape: (height, width, 4)

        # Create QImage from RGBA data
        output = QImage(
            rgba.data, width, height, width * 4, QImage.Format.Format_RGBA8888
        ).copy()  # .copy() to own the data

        return QPixmap.fromImage(output)

    def clear(self) -> None:
        """Clear the preview panel."""
        for widget in self.frame_widgets:
            widget.deleteLater()
        self.frame_widgets.clear()
        self.indexed_frames.clear()
        self.preview_frame_indices = []
        self.character_name = ""
        self.name_label.setText("")
        # Reset AFS preview state
        self._afs_preview_mode = False
        self._afs_sprites.clear()
        self._afs_sprite_dims.clear()

    def set_character_for_afs_preview(
        self,
        name: str,
        tex_filepath: str,
        tex_offset: int = 0,
        layout_file: str | None = None,
    ) -> None:
        """Load preview directly from AFS for unextracted characters.

        Args:
            name: Character display name
            tex_filepath: Path to character TEX file in AFS
            tex_offset: Offset to texture data
            layout_file: Path to character layout (.bin) file for frame composition
        """
        # Clear existing state
        self.clear()

        self.character_name = name
        self._afs_preview_mode = True
        self.frames_dir = "afs_preview"  # Dummy for rendering logic

        # Try frame composition with AfsPreviewComposer
        # The layout file (tex file) contains frame offsets at byte 0
        if (
            layout_file
            and os.path.exists(layout_file)
            and self._try_compose_afs_frames(name, tex_filepath, tex_offset, layout_file)
        ):
            return

        # Fallback to raw sprite preview
        self._load_fallback_sprite_preview(name, tex_filepath, tex_offset)

    def _load_fallback_sprite_preview(
        self,
        name: str,
        tex_filepath: str,
        tex_offset: int,
    ) -> None:
        """Load raw sprite preview when frame composition fails."""
        self.name_label.setText(f"{name} (Sprite Preview)")
        try:
            from sf33rd.parsers.texture_unpacker import (  # pylint: disable=import-outside-toplevel
                extract_sprites_on_demand,
            )

            # Extract just 12 sample sprites (indices 0-11)
            sample_indices = list(range(12))
            self._afs_sprites = extract_sprites_on_demand(tex_filepath, sample_indices, tex_offset)

            if self._afs_sprites:
                # Default dimensions (8x8 tile, will be overridden if we can
                # detect)
                for idx in self._afs_sprites:
                    # Estimate dimension from data size (assuming square)
                    data_len = len(self._afs_sprites[idx])
                    size = int(data_len**0.5)
                    if size * size == data_len:
                        self._afs_sprite_dims[idx] = (size, size)
                    else:
                        self._afs_sprite_dims[idx] = (8, 8)

                self.preview_frame_indices = list(self._afs_sprites.keys())
                self._update_afs_preview_grid()
                logger.info("AFS preview loaded for %s: %d sprites", name, len(self._afs_sprites))
            else:
                logger.warning("No sprites extracted for AFS preview: %s", name)

        except (ImportError, OSError, ValueError) as e:
            logger.warning("Failed to load AFS preview for %s: %s", name, e)

    def _try_compose_afs_frames(
        self,
        name: str,
        tex_filepath: str,
        tex_offset: int,
        layout_file: str,
    ) -> bool:
        """Attempt to compose frames using AfsPreviewComposer.

        Returns True if successful, False otherwise.
        """
        try:
            # Lazy imports to avoid circular dependencies
            import struct  # pylint: disable=import-outside-toplevel

            from sf33rd.operations.afs_preview_composer import (  # pylint: disable=import-outside-toplevel
                AfsPreviewComposer,
            )
            from sf33rd.parsers.texture_unpacker import (  # pylint: disable=import-outside-toplevel
                extract_sprites_on_demand,
            )

            # Determine frame count from layout file
            with open(layout_file, "rb") as f:
                first_bytes = f.read(4)
                if len(first_bytes) < 4:
                    return False
                first_offset = struct.unpack("<I", first_bytes)[0]
                frame_count = first_offset // 4

            # Early exit for invalid frame count or empty sample frames
            if frame_count <= 0:
                return False

            # Select sample frames: pick frames that are likely to have good poses
            sample_frames = [f for f in range(7) if f < frame_count]

            # Scan frame layouts to find required sprite codes (returns early if no samples)
            required_codes = (
                AfsPreviewComposer.scan_required_sprites(layout_file, sample_frames) if sample_frames else set()
            )
            logger.debug(
                "AFS preview: need %d sprites for %s (codes: %s)",
                len(required_codes),
                name,
                sorted(list(required_codes))[:10],
            )

            if not required_codes:
                return False

            # Extract only the sprites we need
            sprites_data = extract_sprites_on_demand(
                tex_filepath,
                sorted(list(required_codes)),
                tex_offset,
            )
            logger.debug(
                "AFS preview: extracted %d/%d sprites for %s",
                len(sprites_data) if sprites_data else 0,
                len(required_codes),
                name,
            )

            if not sprites_data:
                return False

            # Calculate sprite dimensions
            sprite_dims: dict[int, tuple[int, int]] = {}
            for idx, data in sprites_data.items():
                data_len = len(data)
                size = int(data_len**0.5)
                if size * size == data_len:
                    sprite_dims[idx] = (size, size)
                else:
                    sprite_dims[idx] = (8, 8)

            # Create composer
            self._afs_composer = AfsPreviewComposer(
                layout_file=layout_file,
                sprites_data=sprites_data,
                sprite_dims=sprite_dims,
            )

            # Set palette if we have one
            if self.current_palette:
                self._afs_composer.set_palette(self.current_palette)

            self.preview_frame_indices = sample_frames
            self.name_label.setText(f"{name} (Frame Preview)")
            self._update_afs_frame_grid()
            logger.info(
                "AFS frame composition for %s: %d frames",
                name,
                len(sample_frames),
            )
            return True

        except (ImportError, OSError, ValueError) as e:
            logger.warning("AFS frame composition failed for %s: %s", name, e)
            return False

    def _update_afs_preview_grid(self) -> None:
        """Update preview grid with AFS sprites."""
        if not self._afs_sprites:
            return

        viewport = self._scroll_area.viewport()
        viewport_width = viewport.width() if viewport else 100
        if viewport_width <= 100:
            viewport_width = 800
        viewport_width -= 16

        current_row = QHBoxLayout()
        current_row.setSpacing(4)
        current_row.setContentsMargins(0, 0, 0, 0)
        current_row_width = 0

        for idx in self.preview_frame_indices[:12]:
            frame_label = QLabel()
            frame_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            frame_label.setToolTip(f"Sprite {idx} (AFS Preview)")

            pixmap = self._render_afs_sprite(idx)
            sprite_width = 80
            if pixmap and not pixmap.isNull():
                # Scale up small sprites
                if pixmap.height() < 40:
                    pixmap = pixmap.scaled(
                        pixmap.width() * 4,
                        pixmap.height() * 4,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.FastTransformation,
                    )
                sprite_width = pixmap.width()
                frame_label.setPixmap(pixmap)

            # Check if we need to start a new row
            if current_row_width + sprite_width > viewport_width and current_row_width > 0:
                current_row.addStretch()
                self.flow_layout.addLayout(current_row)
                current_row = QHBoxLayout()
                current_row.setSpacing(4)
                current_row.setContentsMargins(0, 0, 0, 0)
                current_row_width = 0

            current_row.addWidget(frame_label)
            self.frame_widgets.append(frame_label)
            current_row_width += sprite_width + 4

        # Add the last row
        if current_row.count() > 0:
            current_row.addStretch()
            self.flow_layout.addLayout(current_row)

    def _update_afs_frame_grid(self) -> None:
        """Update preview grid with composed frames from AfsPreviewComposer."""
        if not self._afs_composer:
            return

        # Clear existing
        self._clear_flow_layout()

        viewport = self._scroll_area.viewport()
        viewport_width = viewport.width() if viewport else 100
        viewport_height = viewport.height() if viewport else 100
        if viewport_width <= 100:
            viewport_width = 800
        if viewport_height <= 100:
            viewport_height = 400
        viewport_width -= 16
        viewport_height -= 16

        # Calculate target height based on number of valid frames
        # Fewer frames = larger size to fill viewport
        num_frames = (
            len([idx for idx in self.preview_frame_indices if self._afs_composer.compose_frame(idx) is not None])
            if self._afs_composer
            else len(self.preview_frame_indices)
        )

        if num_frames <= 4:
            # Few frames - use most of viewport height
            target_height = max(150, viewport_height - 50)
        elif num_frames <= 8:
            # Medium frames - use half viewport
            target_height = max(120, viewport_height // 2)
        else:
            # Many frames - aim for 2-3 rows
            target_height = max(100, viewport_height // 3)

        current_row = QHBoxLayout()
        current_row.setSpacing(4)
        current_row.setContentsMargins(0, 0, 0, 0)
        current_row_width = 0

        for frame_idx in self.preview_frame_indices:
            frame_label = QLabel()
            frame_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            frame_label.setToolTip(f"Frame {frame_idx}")
            frame_label.setCursor(Qt.CursorShape.PointingHandCursor)
            frame_label.setMinimumSize(50, 50)  # Ensure label has size

            # Compose frame using AfsPreviewComposer
            pil_image = self._afs_composer.compose_frame(frame_idx)
            sprite_width = 100
            if pil_image is not None:
                # Convert PIL to QPixmap
                pixmap = self._pil_to_qpixmap(pil_image)
                if pixmap and not pixmap.isNull():
                    # Auto-crop
                    pixmap = _auto_crop_pixmap(pixmap)
                    # Scale to target height (both up and down for consistent
                    # sizing)
                    if pixmap.height() != target_height and pixmap.height() > 0:
                        pixmap = pixmap.scaledToHeight(target_height, Qt.TransformationMode.FastTransformation)
                    sprite_width = pixmap.width()
                    frame_label.setPixmap(pixmap)

            # Make clickable
            frame_label.setProperty("frame_idx", frame_idx)
            frame_label.installEventFilter(self)

            # Check if we need to start a new row
            if current_row_width + sprite_width > viewport_width and current_row_width > 0:
                current_row.addStretch()
                self.flow_layout.addLayout(current_row)
                current_row = QHBoxLayout()
                current_row.setSpacing(4)
                current_row.setContentsMargins(0, 0, 0, 0)
                current_row_width = 0

            current_row.addWidget(frame_label)
            self.frame_widgets.append(frame_label)
            current_row_width += sprite_width + 4

        # Add the last row
        if current_row.count() > 0:
            current_row.addStretch()
            self.flow_layout.addLayout(current_row)

        # Add stretch at bottom
        self.flow_layout.addStretch()

        # Force update
        self.grid_container.updateGeometry()
        self.grid_container.update()

    def _render_afs_sprite(self, sprite_idx: int) -> QPixmap | None:
        """Render an AFS sprite with current palette."""
        if sprite_idx not in self._afs_sprites:
            return None

        sprite_data = self._afs_sprites[sprite_idx]
        width, height = self._afs_sprite_dims.get(sprite_idx, (8, 8))

        # Validate data size
        if len(sprite_data) != width * height:
            return None

        # Convert indexed bytes to numpy array
        indices = np.frombuffer(sprite_data, dtype=np.uint8).reshape((height, width))

        # Build palette LUT with fallback to grayscale
        lut = np.zeros((256, 4), dtype=np.uint8)
        if self.current_palette:
            for i, (r, g, b) in enumerate(self.current_palette[:64]):
                lut[i] = [r, g, b, 255 if i > 0 else 0]
        else:
            # Fallback: grayscale palette
            for i in range(256):
                gray = min(255, i * 4)
                lut[i] = [gray, gray, gray, 255 if i > 0 else 0]

        # Apply palette
        rgba = lut[indices]

        # Create QImage
        output = QImage(rgba.data, width, height, width * 4, QImage.Format.Format_RGBA8888).copy()

        return QPixmap.fromImage(output)
