"""
Palette management for SF3:3rd Strike stage editing.

This module provides classes for working with Dreamcast ARGB1555 palettes,
including color conversion, multi-offset palette management, and color quantization.
"""

import logging
import os
import struct
from typing import Any, cast

import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)


class Color:
    """Represents a single RGBA color with ARGB1555 conversion support."""

    def __init__(self, r: int, g: int, b: int, a: int = 255):
        """
        Initialize a color from RGB888 values.

        Args:
            r: Red component (0-255)
            g: Green component (0-255)
            b: Blue component (0-255)
            a: Alpha component (0-255). Values < 128 are treated as transparent (0), >= 128 as opaque (1).
        """
        self.r = max(0, min(255, r))
        self.g = max(0, min(255, g))
        self.b = max(0, min(255, b))
        # Handle alpha threshold (SF3 uses 1-bit alpha with 128 threshold)
        self.a = 1 if a >= 128 else 0

    def to_argb1555(self) -> int:
        """
        Convert to 16-bit ARGB1555 format (Dreamcast native format).

        Format: A RRRRR GGGGG BBBBB (1-5-5-5 bits)

        Returns:
            16-bit integer in ARGB1555 format
        """
        r5 = self.r >> 3  # 8-bit to 5-bit
        g5 = self.g >> 3
        b5 = self.b >> 3
        return (self.a << 15) | (r5 << 10) | (g5 << 5) | b5

    @staticmethod
    def from_argb1555(value: int) -> "Color":
        """
        Create Color from 16-bit ARGB1555 value.

        Args:
            value: 16-bit ARGB1555 color value

        Returns:
            Color instance
        """
        a = (value >> 15) & 0x01
        r5 = (value >> 10) & 0x1F
        g5 = (value >> 5) & 0x1F
        b5 = value & 0x1F

        # Scale 5-bit to 8-bit (multiply by 255/31)
        r = int(r5 * 255 / 31)
        g = int(g5 * 255 / 31)
        b = int(b5 * 255 / 31)

        # Convert 1-bit alpha back to 0-255 range
        # Heuristic: If A is 0 but color contains data (R/G/B != 0), treat as Opaque (X1555 format).
        # This prevents valid colors from being treated as transparent.
        alpha_8bit = 255 if a == 0 and (r > 0 or g > 0 or b > 0) else 255 if a else 0

        return Color(r, g, b, alpha_8bit)

    def to_tuple(self) -> tuple[int, int, int, int]:
        """Return (r, g, b, a) tuple."""
        # Convert 1-bit alpha to 255/0 for consistency with init logic, or just return stored
        # self.a is 0 or 1.
        # But users expect 0-255 usually?
        # Let's check init: a is stored as 0 or 1.
        # Let's return 0-255 scale for compatibility with PIL/UI
        return (self.r, self.g, self.b, 255 if self.a else 0)

    def to_rgb_tuple(self) -> tuple[int, int, int]:
        """Return (r, g, b) tuple."""
        return (self.r, self.g, self.b)

    def __repr__(self) -> str:
        return f"Color({self.r}, {self.g}, {self.b}, {self.a})"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Color):
            return False
        return self.r == other.r and self.g == other.g and self.b == other.b and self.a == other.a


class Palette:
    """
    Manages a multi-offset palette (up to 2048 colors for SF3:3rd Strike).

    The palette is structured as multiple 64-color sub-palettes at different offsets.
    Each offset represents a separate 64-color palette that can be referenced by tiles.
    """

    def __init__(self, size: int = 256):
        """
        Initialize a palette with the given size.

        Args:
            size: Total number of colors (must be multiple of 64, default=256)
        """
        if size % 64 != 0:
            raise ValueError(f"Palette size must be multiple of 64, got {size}")

        self.colors: list[Color] = [Color(0, 0, 0, 0) for _ in range(size)]
        self.size = size

    def get_sub_palette(self, offset: int, size: int = 64) -> list[Color]:
        """
        Extract a sub-palette at a specific offset.

        Args:
            offset: Palette offset index (e.g., 0, 1, 2... for 64-color chunks)
            size: Number of colors to extract (default=64)

        Returns:
            List of Color objects

        Raises:
            IndexError: If offset is out of range
        """
        start_idx = offset * 64
        end_idx = start_idx + size

        if end_idx > len(self.colors):
            raise IndexError(f"Sub-palette offset {offset} with size {size} exceeds palette size {len(self.colors)}")

        return self.colors[start_idx:end_idx]

    def set_sub_palette(self, offset: int, colors: list[Color]) -> None:
        """
        Replace colors at a specific offset.

        Args:
            offset: Palette offset index
            colors: List of Color objects to set

        Raises:
            IndexError: If offset + len(colors) exceeds palette size
        """
        start_idx = offset * 64
        end_idx = start_idx + len(colors)

        if end_idx > len(self.colors):
            raise IndexError(f"Setting {len(colors)} colors at offset {offset} exceeds palette size {len(self.colors)}")

        self.colors[start_idx:end_idx] = colors

    def set_color(self, index: int, color: Color) -> None:
        """
        Set a single color at a specific index.

        Args:
            index: Color index (0 to size-1)
            color: Color object to set

        Raises:
            IndexError: If index is out of range
        """
        if index < 0 or index >= len(self.colors):
            raise IndexError(f"Color index {index} out of range (0-{len(self.colors) - 1})")

        self.colors[index] = color

    def is_swizzled(self) -> bool:
        """
        Heuristic to check if the palette is likely Swizzled.
        Checks for the characteristic "Empty Block Swap" pattern of swizzling.
        In a Linear palette, colors fill from index 0. So block 8-15 is filled before 16-23.
        In a Swizzled palette, 8-15 swaps with 16-23. So we might see 8-15 Empty and 16-23 Filled.
        """
        if len(self.colors) < 32:
            return False

        def is_uniform(colors: list[Color]) -> bool:
            """Check if color block is uniform."""
            if not colors:
                return True
            # Check if all colors are effectively close to the first one (or
            # zero)
            first = colors[0].to_argb1555()
            return all(c.to_argb1555() == first for c in colors[1:])

        votes_swizzled = 0
        votes_linear = 0

        # Check every 32-color block
        num_blocks = len(self.colors) // 32
        for i in range(num_blocks):
            base = i * 32
            block = self.colors[base : base + 32]

            # Sub-blocks of interest
            chunk_b = block[8:16]
            chunk_c = block[16:24]

            b_uniform = is_uniform(chunk_b)
            c_uniform = is_uniform(chunk_c)

            if b_uniform and not c_uniform:
                # B (8-15) is empty/uniform, C (16-23) is detailed.
                # Use of higher indices without lower indices indicates
                # Swizzling.
                votes_swizzled += 1

            elif not b_uniform and c_uniform:
                # B (8-15) is detailed, C (16-23) is empty.
                # Standard Linear pattern (Sequential filling).
                votes_linear += 1

        # logging.debug("Palette Swizzle Votes: Swizzled=%s, Linear=%s", votes_swizzled, votes_linear)

        return votes_swizzled > 0 and votes_swizzled > votes_linear

    def swizzle(self) -> None:
        """
        Apply the game's palette swizzle (palConvRowTim2CI8Clut).
        Swaps indices 8-15 with 16-23 in every 32-color block.

        This mimics the hardware upload process where the palette is scrambled.
        """
        clut_tbl = [
            0,
            1,
            2,
            3,
            4,
            5,
            6,
            7,
            16,
            17,
            18,
            19,
            20,
            21,
            22,
            23,
            8,
            9,
            10,
            11,
            12,
            13,
            14,
            15,
            24,
            25,
            26,
            27,
            28,
            29,
            30,
            31,
        ]

        new_colors = list(self.colors)
        for i, color in enumerate(self.colors):
            base = i & ~0x1F  # Round down to nearest 32
            offset = i & 0x1F
            new_offset = clut_tbl[offset]
            new_colors[base + new_offset] = color

        self.colors = new_colors

    def unswizzle(self) -> None:
        """
        Reverse the palette swizzle.
        Since the swizzle operation is symmetric (swaps 8-15 with 16-23),
        calling swizzle() again reverses it.
        """
        self.swizzle()

    @staticmethod
    def get_swizzle_map(size: int) -> list[int]:
        """
        Returns a mapping where map[old_index] = new_index
        based on the Dreamcast swizzle algorithm.
        """
        clut_tbl = [
            0,
            1,
            2,
            3,
            4,
            5,
            6,
            7,
            16,
            17,
            18,
            19,
            20,
            21,
            22,
            23,
            8,
            9,
            10,
            11,
            12,
            13,
            14,
            15,
            24,
            25,
            26,
            27,
            28,
            29,
            30,
            31,
        ]
        mapping = [0] * size
        for i in range(size):
            base = i & ~0x1F
            offset = i & 0x1F
            new_offset = clut_tbl[offset]
            mapping[i] = base + new_offset
        return mapping

    def to_bin(self, swizzle: bool = False, big_endian: bool = False) -> bytes:
        """
        Export to binary ARGB1555 format.

        Args:
            swizzle: If True, swizzle the palette (Dreamcast requirement for textures)
            big_endian: If True, use Big-Endian format (Dreamcast standard).
                        If False, use Little-Endian (Editor/PC standard).

        Returns:
            Binary data suitable for writing to .bin file
        """
        export_palette = self
        if swizzle:
            # Create a copy to avoid modifying this instance
            export_palette = Palette(size=self.size)
            export_palette.colors = list(self.colors)
            export_palette.swizzle()

        data = bytearray()
        fmt = ">H" if big_endian else "<H"

        for color in export_palette.colors:
            argb1555 = color.to_argb1555()
            data.extend(struct.pack(fmt, argb1555))
        return bytes(data)

    @staticmethod
    def from_bin(data: bytes) -> "Palette":
        """
        Load palette from binary ARGB1555 data.

        Args:
            data: Binary data in ARGB1555 format (little-endian)

        Returns:
            Palette instance
        """
        num_colors = len(data) // 2
        palette = Palette(size=num_colors)

        for i in range(num_colors):
            color_val = struct.unpack("<H", data[i * 2 : (i + 1) * 2])[0]
            palette.colors[i] = Color.from_argb1555(color_val)

        return palette

    @staticmethod
    def from_file(filepath: str) -> "Palette":
        """
        Load palette from a binary file.

        Args:
            filepath: Path to .bin palette file

        Returns:
            Palette instance

        Raises:
            FileNotFoundError: If file doesn't exist
        """
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Palette file not found: {filepath}")

        with open(filepath, "rb") as f:
            data = f.read()

        logger.info("Loaded palette from %s: %s colors", filepath, len(data) // 2)
        return Palette.from_bin(data)

    def save(self, filepath: str, swizzle: bool = False, big_endian: bool = False) -> None:
        """
        Save palette to a binary file.

        Args:
            filepath: Path to output .bin file
            swizzle: If True, apply Dreamcast swizzle
            big_endian: If True, use Big-Endian format
        """
        with open(filepath, "wb") as f:
            f.write(self.to_bin(swizzle=swizzle, big_endian=big_endian))

        logger.info(
            "Saved palette to %s: %s colors (Swizzle=%s, BE=%s)", filepath, len(self.colors), swizzle, big_endian
        )

    def to_rgb_list(self) -> list[tuple[int, int, int]]:
        """
        Export as list of RGB tuples (no alpha).

        Returns:
            List of (r, g, b) tuples
        """
        return [c.to_rgb_tuple() for c in self.colors]

    def to_tuple_list(self) -> list[tuple[int, int, int, int]]:
        """
        Export as list of RGBA tuples (for compatibility with existing code).

        Returns:
            List of (r, g, b, a) tuples
        """
        return [c.to_tuple() for c in self.colors]

    @staticmethod
    def from_rgb_list(rgb_list: list[tuple[int, int, int]]) -> "Palette":
        """
        Create palette from list of RGB tuples.

        Args:
            rgb_list: List of (r, g, b) tuples

        Returns:
            Palette instance
        """
        size = len(rgb_list)
        # Round up to nearest multiple of 64
        size = ((size + 63) // 64) * 64

        palette = Palette(size=size)
        for i, (r, g, b) in enumerate(rgb_list):
            if i < len(palette.colors):
                palette.colors[i] = Color(r, g, b, 255)

        return palette


class Quantizer:
    """
    Color quantization utilities for reducing images to palette constraints.

    Provides methods for generating optimal palettes and quantizing image regions
    to fit within the 64-color sub-palette limitation.
    """

    @staticmethod
    def _create_quantization_image(opaque_pixels: list[tuple[int, int, int, int]]) -> Image.Image:
        """Helper to create a PIL image from pixels for quantization."""
        width = int(np.sqrt(len(opaque_pixels))) + 1
        height = (len(opaque_pixels) + width - 1) // width
        img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        img.putdata(cast(Any, opaque_pixels + [(0, 0, 0, 0)] * (width * height - len(opaque_pixels))))
        return img.convert("RGB")

    @staticmethod
    def _extract_colors_from_pil_palette(palette_list: list[int], count: int, reserve_index_0: bool) -> list[Color]:
        """Helper to convert PIL palette list to Color objects."""
        colors: list[Color] = []
        if reserve_index_0:
            colors.append(Color(0, 0, 0, 0))

        for i in range(count):
            if (i * 3 + 2) < len(palette_list):
                colors.append(Color(palette_list[i * 3], palette_list[i * 3 + 1], palette_list[i * 3 + 2], 255))
            else:
                colors.append(Color(0, 0, 0, 255))
        return colors

    @staticmethod
    def generate_optimal_palette(
        pixels: list[tuple[int, int, int, int]], num_colors: int = 64, reserve_index_0: bool = True
    ) -> list[Color]:
        """
        Generate an optimal palette from pixel data using median cut algorithm.
        """
        if not pixels:
            return [Color(0, 0, 0, 0) for _ in range(num_colors)]

        opaque_pixels = [p for p in pixels if p[3] >= 128]
        if not opaque_pixels:
            return [Color(0, 0, 0, 0) for _ in range(num_colors)]

        img_rgb = Quantizer._create_quantization_image(opaque_pixels)
        target_colors = num_colors - 1 if reserve_index_0 else num_colors
        quantized = img_rgb.quantize(colors=target_colors, method=2)

        p_list = quantized.getpalette() or []
        colors = Quantizer._extract_colors_from_pil_palette(p_list, target_colors, reserve_index_0)

        while len(colors) < num_colors:
            colors.append(Color(0, 0, 0, 0))
        return colors[:num_colors]

    @staticmethod
    def quantize_region_to_palette(
        image: Image.Image, region: tuple[int, int, int, int], palette_colors: list[Color], num_colors: int = 64
    ) -> Image.Image:
        """
        Quantize a region of an image to a specific palette.

        Args:
            image: Source PIL Image
            region: (x, y, width, height) tuple defining the region
            palette_colors: List of Color objects to use as palette
            num_colors: Number of colors to use (default=64)

        Returns:
            Quantized PIL Image (same size as input)
        """
        x, y, width, height = region

        # Extract region
        region_img = image.crop((x, y, x + width, y + height))

        # Create palette image
        pal_img = Image.new("P", (1, 1))
        palette_data: list[int] = []
        for color in palette_colors[:num_colors]:
            palette_data.extend(color.to_rgb_tuple())

        # Pad to 256 colors (PIL requirement)
        while len(palette_data) < 256 * 3:
            palette_data.extend([0, 0, 0])

        pal_img.putpalette(palette_data)

        # Quantize to this palette
        region_rgb = region_img.convert("RGB")
        quantized = region_rgb.quantize(palette=pal_img, dither=0)

        # Convert back to RGBA
        result = quantized.convert("RGBA")

        # Paste back into full image
        output = image.copy()
        output.paste(result, (x, y))

        return output


class CharacterPalette:
    """
    Parses character COL files matching game's COL struct.

    The game's color3rd.c defines:
        typedef struct { u16 col[2][28][64]; } COL;

    Structure breakdown:
    - 2 variants (normal palette, alternate/lighting variant)
    - 28 styles (LP, MP, HP, LK, MK, HK, + specials)
    - 64 colors per style

    Style indices:
    - 0-5: Main button colors (LP, MP, HP, LK, MK, HK)
    - 6-7: 2P variations
    - 8-15: Reserved/additional colors
    - 16-21: Effect palettes (projectiles, etc.)
    - 22-27: Special effects (Gill resurrection, metamorphosis, etc.)
    """

    # Possible file sizes:
    # - 1 variant × 28 styles × 64 colors × 2 bytes = 3584 (actual game files)
    # - 2 variants × 28 styles × 64 colors × 2 bytes = 7168 (full structure)
    EXPECTED_SIZE_1V = 1 * 28 * 64 * 2  # 3584 bytes
    EXPECTED_SIZE_2V = 2 * 28 * 64 * 2  # 7168 bytes
    NUM_STYLES = 28
    COLORS_PER_STYLE = 64

    def __init__(self, data: bytes):
        """
        Initialize from raw COL file data.

        Args:
            data: Raw binary data from .col file

        Raises:
            ValueError: If data size doesn't match expected COL structure
        """
        # Determine number of variants from file size
        if len(data) == self.EXPECTED_SIZE_2V:
            num_variants = 2
        elif len(data) == self.EXPECTED_SIZE_1V:
            num_variants = 1
        else:
            logger.warning(
                "COL file size %d doesn't match expected sizes (%d or %d bytes). Attempting to parse as flat palette.",
                len(data),
                self.EXPECTED_SIZE_1V,
                self.EXPECTED_SIZE_2V,
            )
            # Fall back to flat palette interpretation
            self._fallback_mode = True
            self._flat_palette = Palette.from_bin(data)
            self._num_variants = 0
            return

        self._fallback_mode = False
        self._num_variants = num_variants
        self._styles: list[list[list[Color]]] = []

        # Parse: col[variant][style][color_idx]
        offset = 0
        for _variant in range(num_variants):
            variant_styles: list[list[Color]] = []
            for _style in range(self.NUM_STYLES):
                colors: list[Color] = []
                for _ in range(self.COLORS_PER_STYLE):
                    color_val = struct.unpack("<H", data[offset : offset + 2])[0]
                    colors.append(Color.from_argb1555(color_val))
                    offset += 2
                variant_styles.append(colors)
            self._styles.append(variant_styles)

        logger.info(
            "Loaded CharacterPalette: %d variants × %d styles × %d colors",
            num_variants,
            self.NUM_STYLES,
            self.COLORS_PER_STYLE,
        )

    @staticmethod
    def from_file(filepath: str) -> "CharacterPalette":
        """
        Load CharacterPalette from a .col file.

        Args:
            filepath: Path to the COL palette file

        Returns:
            CharacterPalette instance

        Raises:
            FileNotFoundError: If file doesn't exist
        """
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"COL file not found: {filepath}")

        with open(filepath, "rb") as f:
            data = f.read()

        return CharacterPalette(data)

    def get_style(self, style_index: int, variant: int = 0) -> list[Color]:
        """
        Get 64-color palette for a specific style.

        This matches the game's logic:
            plcol[id]->col[variant][Player_Color[id]]

        Args:
            style_index: Style index 0-27 (clamped if out of range)
            variant: 0 for normal, 1 for alternate (default: 0)

        Returns:
            List of 64 Color objects
        """
        if self._fallback_mode:
            # Fallback: extract 64 colors at style_index * 64
            start = (style_index % 4) * 64  # Limit to 4 chunks for 256-color
            return self._flat_palette.colors[start : start + 64]

        # Clamp indices to valid range
        style_index = max(0, min(self.NUM_STYLES - 1, style_index))
        variant = max(0, min(self._num_variants - 1, variant))

        return list(self._styles[variant][style_index])

    def get_style_rgb_list(self, style_index: int, variant: int = 0) -> list[tuple[int, int, int]]:
        """
        Get style palette as list of RGB tuples (for texture unpacker).

        Args:
            style_index: Style index 0-27
            variant: 0 for normal, 1 for alternate

        Returns:
            List of 64 (r, g, b) tuples
        """
        colors = self.get_style(style_index, variant)
        return [c.to_rgb_tuple() for c in colors]

    def get_effect_palette(self, _style_index: int) -> list[Color]:
        """
        Get special effect palette (game uses styles 16-21 for effects).

        The game loads plcol[id]->col[0][22] into ColorRAM[502/506]
        for character-specific effect colors.

        Args:
            style_index: Base style index (0-27)

        Returns:
            List of 64 Color objects from style 22 (effect slot)
        """
        # Special effect palette is always style 22 in the game
        return self.get_style(22, 0)

    @property
    def num_styles(self) -> int:
        """Return number of available styles."""
        return self.NUM_STYLES if not self._fallback_mode else 4

    @property
    def available_styles(self) -> list[str]:
        """Return list of available style names for UI.

        Returns PalMod-style button labels: LP, MP, HP, LK, MK, HK, EX
        """
        # Import here to avoid circular dependency
        # pylint: disable=import-outside-toplevel
        from sf33rd.lib.palette_constants import BUTTON_LABELS

        return BUTTON_LABELS

    def get_style_by_name(self, style_name: str, variant: int = 0) -> list[Color]:
        """Get palette by PalMod-style button name.

        This provides a user-friendly interface matching PalMod's naming.

        Args:
            style_name: One of "LP", "MP", "HP", "LK", "MK", "HK", "EX"
            variant: 0 for normal, 1 for alternate

        Returns:
            List of 64 Color objects
        """
        # pylint: disable=import-outside-toplevel
        from sf33rd.lib.palette_constants import BUTTON_TO_STYLE, PaletteStyle

        style_idx = BUTTON_TO_STYLE.get(style_name.upper(), PaletteStyle.LP)
        return self.get_style(style_idx, variant)

    def get_burned_palette(self, base_style: int = 0) -> list[Color]:
        """Get burned/red parry palette variant.

        Returns the pre-defined burned palette from style slot 18,
        or generates one from the base style if not available.

        Args:
            base_style: Base style index (0-6 for LP-EX)

        Returns:
            List of 64 Color objects with burned effect
        """
        # Try to get the pre-defined burned palette (style 18)
        if not self._fallback_mode and self.NUM_STYLES > 18:
            return self.get_style(18, 0)
        # Generate from base style
        # pylint: disable=import-outside-toplevel
        from sf33rd.lib.effect_palette_generator import generate_burned_palette

        return generate_burned_palette(self.get_style(base_style, 0))

    def get_frozen_palette(self, base_style: int = 0) -> list[Color]:
        """Get frozen/super flash palette variant.

        Returns the pre-defined frozen palette from style slot 19,
        or generates one from the base style if not available.

        Args:
            base_style: Base style index (0-6 for LP-EX)

        Returns:
            List of 64 Color objects with frozen effect
        """
        # Try to get the pre-defined frozen palette (style 19)
        if not self._fallback_mode and self.NUM_STYLES > 19:
            return self.get_style(19, 0)
        # Generate from base style
        # pylint: disable=import-outside-toplevel
        from sf33rd.lib.effect_palette_generator import generate_frozen_palette

        return generate_frozen_palette(self.get_style(base_style, 0))

    def generate_grey_tint(self, base_style: int = 0) -> list[Color]:
        """Generate grey-tinted (faded) version of a palette.

        Matches PalMod's MOD_BLEND with rgb(124,124,124).
        Used for hit stun, freeze frames, etc.

        Args:
            base_style: Base style index (0-6 for LP-EX)

        Returns:
            List of 64 Color objects with grey tint effect
        """
        # pylint: disable=import-outside-toplevel
        from sf33rd.lib.effect_palette_generator import generate_grey_tint_palette

        return generate_grey_tint_palette(self.get_style(base_style, 0))

    def get_style_with_effect(self, style_index: int, effect_type: str | None = None, variant: int = 0) -> list[Color]:
        """Get palette with optional effect transformation.

        Convenience method combining style selection with effect application.

        Args:
            style_index: Style index (0-6 for LP-EX)
            effect_type: One of "grey_tint", "burned", "frozen", "sa_parry", or None
            variant: 0 for normal, 1 for alternate

        Returns:
            List of 64 Color objects, transformed if effect specified
        """
        base_colors = self.get_style(style_index, variant)
        if effect_type is None:
            return base_colors

        # pylint: disable=import-outside-toplevel
        from sf33rd.lib.effect_palette_generator import apply_effect_to_palette

        return apply_effect_to_palette(base_colors, effect_type)

    def __repr__(self) -> str:
        if self._fallback_mode:
            return f"CharacterPalette(fallback, {len(self._flat_palette.colors)} colors)"
        return f"CharacterPalette({self._num_variants}×{self.NUM_STYLES}×{self.COLORS_PER_STYLE})"
