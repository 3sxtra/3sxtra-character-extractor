"""
Image processing and tile management for SF3:3rd Strike stage editing.

This module provides utilities for slicing images into 128×128 tiles,
resizing images to fit stage constraints, and managing tile data.
"""

import logging
import os
from typing import Any, cast

from PIL import Image

from sf33rd.lib.layout import calculate_active_bounding_box

logger = logging.getLogger(__name__)


def prepare_pil_palette(palette: Any, offset: int = 0) -> list[int]:
    """Helper to prepare flattened RGB palette data for PIL."""
    pil_palette = []
    if palette:
        colors = palette
        if hasattr(palette, "colors"):
            colors = palette.colors

        # Handle offset
        if 0 < offset < len(colors):
            colors = colors[offset:]

        count = min(len(colors), 256)
        for i in range(count):
            c = colors[i]
            if hasattr(c, "r"):
                pil_palette.extend([c.r, c.g, c.b])
            elif isinstance(c, (list, tuple)):
                pil_palette.extend([c[0], c[1], c[2]])
            else:
                pil_palette.extend([0, 0, 0])

        while len(pil_palette) < 768:
            pil_palette.extend([0, 0, 0])
    else:
        for i in range(256):
            pil_palette.extend([i, i, i])
    return pil_palette


class Tile:
    """
    Represents a single 128×128 texture tile.

    Attributes:
        image: PIL Image object (128×128 RGBA) - Cached render
        indexed_data: Raw indexed byte data (optional)
        palette_offset: Which 64-color palette offset to use (from attr)
        trans_data: List of sub-tile palette regions [(pal_offset, i_point, cofs_xy), ...]
    """

    def __init__(self, image: Image.Image | None = None, indexed_data: bytes | None = None, palette_offset: int = 0):
        """
        Initialize a tile from an image or indexed data.

        Args:
            image: PIL Image (should be 128×128, will be resized if not)
            indexed_data: Raw bytes of indexed image data
            palette_offset: Palette offset index (default=0)
        """
        self.indexed_data = indexed_data
        self.palette_offset = palette_offset
        self.trans_data: list[tuple[int, int, int]] = []
        self.ppgw: int = 8  # Width in 16x16 blocks (default 8 for 128px)
        self.image: Image.Image | None = None

        if image:
            # Ensure RGBA mode
            if image.mode != "RGBA":
                image = image.convert("RGBA")

            # Ensure 128×128 or 256x256 size
            if image.size == (256, 256):
                # Valid large tile
                self.ppgw = 16
            elif image.size != (128, 128):
                logger.warning("Tile image is %s, resizing to 128×128", image.size)
                image = image.resize((128, 128), Image.Resampling.LANCZOS)

            self.image = image

    def _render_with_trans_data(
        self, palette: Any, base_palette_index: int, palette_map_func: Any | None
    ) -> Image.Image:
        """Helper to render tile using trans_data sub-regions."""
        # Check buffer size relative to dimensions
        expected_size = self.image.size[0] * self.image.size[1] if self.image else 128 * 128

        if not self.indexed_data or len(self.indexed_data) != expected_size:
            # If we don't have indexed data matching the image size, we can't render
            # But legacy behavior might rely on 128x128 assumption.
            # If ppgw=16 (256x256), we expect 65536 bytes.
            pass  # Let validation in loop handle it or just proceed

        w, h = self.image.size if self.image else (128, 128)
        canvas = Image.new("RGBA", (w, h))
        src_img = Image.frombytes("P", (w, h), self.indexed_data)
        ppgw = self.ppgw

        for entry in self.trans_data:
            self._render_trans_entry(
                canvas,
                src_img,
                ppgw,
                entry,
                palette=palette,
                base_palette_index=base_palette_index,
                palette_map_func=palette_map_func,
            )

        return cast(Image.Image, canvas)

    # pylint: disable=too-many-arguments
    def _render_trans_entry(
        self,
        canvas: Image.Image,
        src_img: Image.Image,
        ppgw: int,
        entry: tuple[int, int, int],
        *,
        palette: Any,
        base_palette_index: int,
        palette_map_func: Any | None,
    ) -> None:
        """Helper to render a single trans entry onto the canvas."""
        pal_offset, i_point, cofs_xy = entry
        if palette_map_func:
            pal_offset = palette_map_func(pal_offset)

        # Calculate coordinates inline to reduce local variables
        x, y = (i_point % ppgw) * 16, (i_point // ppgw) * 16
        region = src_img.crop((x, y, x + ((cofs_xy >> 4) + 1) * 16, y + ((cofs_xy & 0xF) + 1) * 16))

        region_rgba = self._apply_sub_palette(region, palette, base_palette_index + pal_offset)
        canvas.paste(region_rgba, (x, y))

    def _apply_sub_palette(self, region_img: Image.Image, palette: Any, effective_bank: int) -> Image.Image:
        """Helper to apply a 256-color sub-palette to a region."""
        effective_index = effective_bank * 64
        palette_data = []

        for i in range(256):
            idx = effective_index + i
            if idx < len(palette.colors):
                color = palette.colors[idx]
                alpha = 0 if i == 0 else (255 if color.a else 0)
                palette_data.extend([color.r, color.g, color.b, alpha])
            else:
                palette_data.extend([0, 0, 0, 0])

        region_img.putpalette(palette_data, rawmode="RGBA")
        return cast(Image.Image, region_img.convert("RGBA"))

    def render(self, palette: Any, base_palette_index: int = 0, palette_map_func: Any | None = None) -> Image.Image:
        """
        Render the tile using the provided palette and base index.
        """
        if not self.indexed_data:
            return self.image if self.image else cast(Image.Image, Image.new("RGBA", (128, 128)))

        if self.trans_data and len(self.trans_data) > 0:
            return self._render_with_trans_data(palette, base_palette_index, palette_map_func)

        # Fallback for no trans_data
        pal_offset = self.palette_offset
        if palette_map_func:
            pal_offset = palette_map_func(pal_offset)

        if not self.indexed_data or len(self.indexed_data) != 128 * 128:
            logger.warning("Unexpected indexed data size: %s", len(self.indexed_data))
            return cast(Image.Image, Image.new("RGBA", (128, 128), (255, 0, 255, 255)))

        img = Image.frombytes("P", (128, 128), self.indexed_data)
        return self._apply_sub_palette(img, palette, base_palette_index + pal_offset)

    def _get_pil_palette_rgb(self, colors: list[Any]) -> list[int]:
        """Helper to get flattened RGB palette data for PIL."""
        data: list[int] = []
        for color in colors:
            data.extend(color.to_rgb_tuple())
        while len(data) < 256 * 3:
            data.extend([0, 0, 0])
        return data

    def apply_palette(self, palette: Any) -> Image.Image:
        """
        Legacy method for applying palette to generate an indexed image.
        """
        # Get the sub-palette for this tile
        sub_palette = palette.get_sub_palette(self.palette_offset, 64)
        palette_data = self._get_pil_palette_rgb(sub_palette)

        # Create palette image
        pal_img = Image.new("P", (1, 1))
        pal_img.putpalette(palette_data)

        if not self.image:
            return Image.new("P", (128, 128))

        # Quantize to this palette
        img_rgb = self.image.convert("RGB")
        quantized = img_rgb.quantize(palette=pal_img, dither=0)

        # Preserve transparency if source has alpha
        if self.image.mode == "RGBA":
            # Create a mask of transparent pixels (alpha < 128)
            alpha = self.image.split()[3]
            # 1 where transparent, 0 where opaque
            mask = alpha.point(lambda p: 1 if p < 128 else 0, mode="1")

            # Apply mask to set transparent pixels to index 0
            # Since 128x128 is small, pixel access is fast enough
            q_pixels = quantized.load()
            mask_pixels = mask.load()
            width, height = quantized.size

            for y in range(height):
                for x in range(width):
                    if mask_pixels[x, y]:
                        q_pixels[x, y] = 0

        return quantized


class TileSlicer:
    """
    Utilities for slicing images into 128×128 tiles and managing stage layouts.
    """

    @staticmethod
    def slice_image(image: Image.Image, active_slots: list[int]) -> list[Tile]:
        """
        Slice an image into tiles based on active slot mask.

        The image is treated as an 8×8 grid of 128×128 tiles. Only tiles
        corresponding to active slots are extracted.

        Args:
            image: Source PIL Image (should be 1024×1024 or will be padded)
            active_slots: List of active slot indices (0-63)

        Returns:
            List of Tile objects, one per active slot
        """
        # Ensure RGBA
        if image.mode != "RGBA":
            image = image.convert("RGBA")

        # Pad to 1024×1024 if needed
        if image.size != (1024, 1024):
            canvas = Image.new("RGBA", (1024, 1024), (0, 0, 0, 0))
            canvas.paste(image, (0, 0))
            image = canvas

        tiles = []

        for slot_idx in active_slots:
            row = slot_idx // 8
            col = slot_idx % 8

            x = col * 128
            y = row * 128

            tile_img = image.crop((x, y, x + 128, y + 128))
            tile = Tile(tile_img, palette_offset=0)
            tiles.append(tile)

        return tiles

    @staticmethod
    def _smart_resize(image: Image.Image, target_size: tuple[int, int]) -> tuple[Image.Image, int, int]:
        """Internal helper to resize image ensuring it covers target_size."""
        tw, th = target_size
        iw, ih = image.size
        scale = max(tw / iw, th / ih)
        nw, nh = int(iw * scale), int(ih * scale)
        resized = image.resize((nw, nh), Image.Resampling.LANCZOS)
        return resized, nw, nh

    @staticmethod
    def smart_resize_top_crop(image: Image.Image, target_size: tuple[int, int]) -> Image.Image:
        """
        Resize image to cover target size, maintaining aspect ratio.
        Crops from TOP (anchors at top).
        """
        tw, th = target_size
        resized, nw, _ = TileSlicer._smart_resize(image, target_size)

        # Horizontal: center crop if wider than needed
        left = (nw - tw) // 2 if nw > tw else 0
        right = left + tw
        # Use simple cast if typing is available, else rely on typing.cast behavior (which is just x)
        # But we need to import cast
        return cast(Image.Image, resized.crop((left, 0, right, th)))

    @staticmethod
    def smart_resize_center_crop(image: Image.Image, target_size: tuple[int, int]) -> Image.Image:
        """
        Resize image to cover target size, maintaining aspect ratio, cropping center.
        """
        tw, th = target_size
        resized, nw, nh = TileSlicer._smart_resize(image, target_size)

        left = (nw - tw) // 2
        top = (nh - th) // 2
        return cast(Image.Image, resized.crop((left, top, left + tw, top + th)))

    @staticmethod
    def calculate_active_bounding_box(stage_id: int, constraint_db: Any) -> tuple[int, int]:
        """
        Calculate the bounding box that contains all active texture slots.
        """
        return calculate_active_bounding_box(stage_id, db=constraint_db)

    @staticmethod
    def _prepare_source_image(image_path: str) -> Image.Image:
        """Load and convert image to RGBA."""
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Image not found: {image_path}")

        image = Image.open(image_path)
        if image.mode != "RGBA":
            image = image.convert("RGBA")

        logger.info("Processing image: %s×%s from %s", image.size[0], image.size[1], os.path.basename(image_path))
        return image

    @staticmethod
    def _resize_and_pad_image(image: Image.Image, target_size: tuple[int, int], resize_mode: str) -> Image.Image:
        """Resize image and pad to 1024x1024 canvas."""
        if resize_mode == "stretch":
            resized = image.resize(target_size, Image.Resampling.LANCZOS)
        elif resize_mode == "center":
            resized = TileSlicer.smart_resize_center_crop(image, target_size)
        else:  # 'cover' (default)
            resized = TileSlicer.smart_resize_top_crop(image, target_size)

        canvas = Image.new("RGBA", (1024, 1024), (0, 0, 0, 0))
        canvas.paste(resized, (0, 0))
        return canvas

    @staticmethod
    def _get_active_slots_ordered(stage_id: int, constraint_db: Any) -> list[tuple[int, int]]:
        """Get ordered list of active slots for a stage."""
        layout = constraint_db.load_stage_layout(stage_id)
        all_active_slots_ordered: list[tuple[int, int]] = []

        if layout:
            for layer in layout["layers"]:
                mask = constraint_db.parse_texture_mask(layer["texture_mask"])
                slots = constraint_db.get_active_slots_from_mask(mask)
                for slot in slots:
                    all_active_slots_ordered.append((layer["layer_idx"], slot))
        else:
            all_active_slots_ordered = [(0, i) for i in range(64)]

        return all_active_slots_ordered

    @staticmethod
    def process_image_to_tiles(
        image_path: str, stage_id: int, constraint_db: Any, resize_mode: str = "cover"
    ) -> tuple[list[tuple[Tile, int, int]], tuple[int, int]]:
        """
        Process an image into tiles for a specific stage.
        """
        image = TileSlicer._prepare_source_image(image_path)
        target_size = TileSlicer.calculate_active_bounding_box(stage_id, constraint_db)
        logger.info("Target size for Stage %02d: %s×%s", stage_id, target_size[0], target_size[1])

        canvas = TileSlicer._resize_and_pad_image(image, target_size, resize_mode)
        all_active_slots_ordered = TileSlicer._get_active_slots_ordered(stage_id, constraint_db)

        tiles_with_meta = []
        for layer_idx, slot in all_active_slots_ordered:
            x, y = (slot % 8) * 128, (slot // 8) * 128
            tile_img = canvas.crop((x, y, x + 128, y + 128))
            tiles_with_meta.append((Tile(tile_img), layer_idx, slot))

        logger.info("Generated %s tiles from image", len(tiles_with_meta))
        return tiles_with_meta, target_size
