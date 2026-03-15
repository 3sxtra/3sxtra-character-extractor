"""AFS Preview Composer for real-time frame composition from binary sprite data.

Composes character frames on-the-fly from binary indexed sprite data + palette,
enabling instant preview for unextracted characters.
"""

import logging
import os
import struct
from typing import TYPE_CHECKING

import numpy as np
from PIL import Image

if TYPE_CHECKING:
    from numpy.typing import NDArray

logger = logging.getLogger(__name__)


class AfsPreviewComposer:
    """Composes frames from binary sprite data + palette.

    Unlike PreviewFrameComposer (which loads sprite PNGs from disk),
    this class accepts binary sprite data directly, enabling preview
    for unextracted characters.
    """

    def __init__(
        self,
        layout_file: str,
        sprites_data: dict[int, bytes],
        sprite_dims: dict[int, tuple[int, int]],
    ):
        """Initialize the composer.

        Args:
            layout_file: Path to character .bin file with frame layouts
            sprites_data: Dict mapping sprite index to raw indexed bytes
            sprite_dims: Dict mapping sprite index to (width, height) tuple
        """
        self.layout_file = layout_file
        self._sprites_data = sprites_data
        self._sprite_dims = sprite_dims

        # Caches
        self._sprite_cache: dict[int, NDArray[np.uint8]] = {}
        self._frame_layouts: dict[int, list[tuple[int, int, int, int]]] = {}
        self._frame_offsets: list[int] = []

        # Current palette
        self._palette: list[tuple[int, int, int]] = [(i, i, i) for i in range(256)]

        # Load frame offsets
        self._load_frame_offsets()

    @staticmethod
    def scan_required_sprites(
        layout_file: str,
        frame_indices: list[int],
    ) -> set[int]:
        """Pre-scan frame layouts to find required sprite codes.

        This should be called BEFORE creating the composer to determine
        which sprites need to be extracted.

        Args:
            layout_file: Path to character .bin file with frame layouts
            frame_indices: Frame indices to scan

        Returns:
            Set of sprite codes needed for the specified frames
        """
        required_codes: set[int] = set()

        if not os.path.exists(layout_file):
            return required_codes

        try:
            with open(layout_file, "rb") as f:
                # Read frame offset table
                first_bytes = f.read(4)
                if len(first_bytes) < 4:
                    return required_codes

                first_offset = struct.unpack("<I", first_bytes)[0]
                num_frames = first_offset // 4

                # Read all offsets
                f.seek(0)
                frame_offsets: list[int] = []
                for _ in range(num_frames):
                    offset_bytes = f.read(4)
                    if len(offset_bytes) < 4:
                        break
                    frame_offsets.append(struct.unpack("<I", offset_bytes)[0])

                # Scan each requested frame
                for frame_idx in frame_indices:
                    if frame_idx >= len(frame_offsets):
                        continue

                    offset = frame_offsets[frame_idx]
                    if offset == 0:
                        continue

                    f.seek(offset)
                    count_bytes = f.read(2)
                    if len(count_bytes) < 2:
                        continue

                    count = struct.unpack("<H", count_bytes)[0]
                    for _ in range(count):
                        entry_bytes = f.read(8)
                        if len(entry_bytes) < 8:
                            break
                        _, _, _, code = struct.unpack("<hhHH", entry_bytes)
                        required_codes.add(code)

        except (OSError, struct.error) as e:
            logger.warning("Failed to scan frame layouts: %s", e)

        logger.debug(
            "Scanned %d frames, found %d unique sprite codes",
            len(frame_indices),
            len(required_codes),
        )
        return required_codes

    def _load_frame_offsets(self) -> None:
        """Load frame offset table from layout file."""
        if not os.path.exists(self.layout_file):
            logger.warning("Layout file not found: %s", self.layout_file)
            return

        try:
            with open(self.layout_file, "rb") as f:
                # Read first offset to determine number of frames
                first_bytes = f.read(4)
                if len(first_bytes) < 4:
                    return

                first_offset = struct.unpack("<I", first_bytes)[0]
                num_frames = first_offset // 4

                # Read all offsets
                f.seek(0)
                for _ in range(num_frames):
                    offset_bytes = f.read(4)
                    if len(offset_bytes) < 4:
                        break
                    self._frame_offsets.append(struct.unpack("<I", offset_bytes)[0])

            logger.debug("Loaded %d frame offsets", len(self._frame_offsets))

        except (OSError, struct.error) as e:
            logger.warning("Failed to load frame offsets: %s", e)

    def _load_frame_layout(self, frame_idx: int) -> list[tuple[int, int, int, int]]:
        """Load layout for a specific frame (cached).

        Returns list of (x, y, attr, code) tuples for sprites in frame.
        """
        if frame_idx in self._frame_layouts:
            return self._frame_layouts[frame_idx]

        if frame_idx >= len(self._frame_offsets):
            return []

        offset = self._frame_offsets[frame_idx]
        if offset == 0:
            return []

        try:
            with open(self.layout_file, "rb") as f:
                f.seek(offset)
                count_bytes = f.read(2)
                if len(count_bytes) < 2:
                    return []

                count = struct.unpack("<H", count_bytes)[0]

                entries = []
                for _ in range(count):
                    entry_bytes = f.read(8)
                    if len(entry_bytes) < 8:
                        break
                    entries.append(struct.unpack("<hhHH", entry_bytes))

                self._frame_layouts[frame_idx] = entries
                return entries

        except (OSError, struct.error) as e:
            logger.warning("Failed to load frame %d layout: %s", frame_idx, e)
            return []

    def _load_sprite(self, code: int) -> "NDArray[np.uint8] | None":
        """Get indexed sprite as numpy array from binary data (cached).

        Returns 2D array of palette indices, or None if not found.
        """
        if code in self._sprite_cache:
            return self._sprite_cache[code]

        if code not in self._sprites_data:
            return None

        data = self._sprites_data[code]
        dims = self._sprite_dims.get(code, (8, 8))
        width, height = dims

        # Validate data size
        if len(data) != width * height:
            # Try to infer square dimensions
            size = int(len(data) ** 0.5)
            if size * size == len(data):
                width, height = size, size
            else:
                logger.warning("Sprite %d size mismatch: %d bytes, expected %dx%d", code, len(data), width, height)
                return None

        try:
            arr = np.frombuffer(data, dtype=np.uint8).reshape((height, width))
            self._sprite_cache[code] = arr
            return arr

        except ValueError as e:
            logger.warning("Failed to reshape sprite %d: %s", code, e)
            return None

    def set_palette(self, colors: list[tuple[int, int, int]]) -> None:
        """Set the current palette for composition.

        Args:
            colors: List of (R, G, B) tuples (at least 64 colors)
        """
        self._palette = colors.copy()
        # Pad to 256 if needed
        while len(self._palette) < 256:
            self._palette.append((0, 0, 0))

    def get_frame_count(self) -> int:
        """Return number of frames available."""
        return len(self._frame_offsets)

    def compose_frame(
        self,
        frame_idx: int,
        canvas_size: tuple[int, int] = (512, 512),
        center_offset: tuple[int, int] = (256, 356),
    ) -> Image.Image | None:
        """Compose a single frame with current palette.

        Args:
            frame_idx: Frame index to compose
            canvas_size: (width, height) of output canvas
            center_offset: (x, y) offset for character center

        Returns:
            RGBA PIL Image, or None if frame not found
        """
        entries = self._load_frame_layout(frame_idx)
        if not entries:
            logger.debug("No entries for frame %d", frame_idx)
            return None

        canvas_w, canvas_h = canvas_size
        center_x, center_y = center_offset

        # Create RGBA canvas
        canvas = np.zeros((canvas_h, canvas_w, 4), dtype=np.uint8)

        # Position accumulator
        curr_x, curr_y = 0, 0

        sprites_found = 0
        sprites_missing = []

        for x, y, attr, code in entries:
            # Accumulate position (inverted Y for image coords)
            curr_x -= x
            curr_y -= y

            # Load indexed sprite
            sprite_data = self._load_sprite(code)
            if sprite_data is None:
                sprites_missing.append(code)
                continue

            sprites_found += 1

            h, w = sprite_data.shape

            # Apply palette to sprite
            rgba = self._apply_palette(sprite_data, attr)

            # Calculate draw position
            draw_x = center_x + curr_x
            draw_y = center_y + curr_y

            # Clip to canvas bounds
            src_x, src_y = 0, 0
            if draw_x < 0:
                src_x = -draw_x
                w += draw_x
                draw_x = 0
            if draw_y < 0:
                src_y = -draw_y
                h += draw_y
                draw_y = 0
            if draw_x + w > canvas_w:
                w = canvas_w - draw_x
            if draw_y + h > canvas_h:
                h = canvas_h - draw_y

            if w <= 0 or h <= 0:
                continue

            # Alpha blend onto canvas
            src_region = rgba[src_y : src_y + h, src_x : src_x + w]
            dst_region = canvas[draw_y : draw_y + h, draw_x : draw_x + w]

            # Simple alpha composite
            alpha = src_region[:, :, 3:4] / 255.0
            dst_region[:, :, :3] = (src_region[:, :, :3] * alpha + dst_region[:, :, :3] * (1 - alpha)).astype(np.uint8)
            dst_region[:, :, 3] = np.maximum(dst_region[:, :, 3], src_region[:, :, 3])

        # Log sprite lookup results
        if sprites_missing:
            logger.debug(
                "Frame %d: found %d sprites, missing %d (codes: %s)",
                frame_idx,
                sprites_found,
                len(sprites_missing),
                sprites_missing[:5],  # First 5 missing codes
            )

        return Image.fromarray(canvas, "RGBA") if sprites_found > 0 else None

    def _apply_palette(
        self,
        indexed: "NDArray[np.uint8]",
        attr: int,
    ) -> "NDArray[np.uint8]":
        """Apply palette to indexed sprite data.

        Args:
            indexed: 2D array of palette indices
            attr: Sprite attribute (contains flip flags)

        Returns:
            RGBA numpy array
        """
        h, w = indexed.shape

        # Apply flips based on attr
        if attr & 0x8000:  # Horizontal flip
            indexed = np.fliplr(indexed)
        if attr & 0x4000:  # Vertical flip
            indexed = np.flipud(indexed)

        # Create RGBA output
        rgba = np.zeros((h, w, 4), dtype=np.uint8)

        # Build lookup table from palette
        lut = np.array(self._palette[:256], dtype=np.uint8)

        # Apply palette
        rgba[:, :, 0] = lut[indexed, 0]  # R
        rgba[:, :, 1] = lut[indexed, 1]  # G
        rgba[:, :, 2] = lut[indexed, 2]  # B

        # Index 0 is transparent
        rgba[:, :, 3] = np.where(indexed == 0, 0, 255)

        return rgba

    def clear_cache(self) -> None:
        """Clear sprite and layout caches."""
        self._sprite_cache.clear()
        self._frame_layouts.clear()
