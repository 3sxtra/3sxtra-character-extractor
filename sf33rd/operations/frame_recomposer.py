"""Frame Recomposer Module.

Recomposes individual sprite tiles into full animation frames.
"""

import os
import struct
import sys
import traceback
from typing import TYPE_CHECKING

from PIL import Image

if TYPE_CHECKING:
    from typing import BinaryIO

    from sf33rd.lib.virtual_colorram import VirtualColorRAM

# Lazy import for CharacterPalette to avoid circular imports
_character_palette_cache: dict[str, tuple] = {}


def _load_palette_for_recomposition(
    sprite_dir: str,
    base_style: int = 0,
) -> tuple[list[list[tuple[int, int, int]]] | None, list[tuple[int, int, int]] | None, "VirtualColorRAM | None"]:
    """
    Load palette from sprites directory for runtime application.

    Looks for palette.col in sprite_dir.

    Args:
        sprite_dir: Directory containing sprites and palette.col

    Returns:
        Tuple of:
        - List of 28 style palettes, each a list of 64 (r, g, b) tuples, or None if not found
        - Extended 256-color effect palette (combining styles 22-25), or None
        - VirtualColorRAM with all slots populated, or None
    """
    # Check cache first - cache key includes base_style
    cache_key = f"{sprite_dir}:{base_style}"
    if cache_key in _character_palette_cache:
        cached = _character_palette_cache[cache_key]
        if len(cached) == 3:
            return cached
        # Old cache format - rebuild

    palette_path = os.path.join(sprite_dir, "palette.col")
    if not os.path.exists(palette_path):
        return (None, None, None)

    try:
        # Import at runtime only when needed to avoid circular imports
        # pylint: disable=import-outside-toplevel
        from sf33rd.lib.palette import CharacterPalette
        from sf33rd.lib.virtual_colorram import VirtualColorRAM
        # pylint: enable=import-outside-toplevel

        char_pal = CharacterPalette.from_file(palette_path)

        # Build list of all 28 style palettes (64 colors each)
        palettes = []
        for style in range(char_pal.num_styles):
            rgb_list = char_pal.get_style_rgb_list(style)
            palettes.append(rgb_list)

        # Build extended 256-color effect palette from styles 22-25
        # The game loads col[0][22] (256 colors = 4 styles) to ColorRAM[502]
        effect_palette_256: list[tuple[int, int, int]] = []
        for style in range(22, min(26, char_pal.num_styles)):
            effect_palette_256.extend(char_pal.get_style_rgb_list(style))

        # Pad to 256 if needed
        while len(effect_palette_256) < 256:
            effect_palette_256.append((0, 0, 0))

        # Build VirtualColorRAM with all slots populated using selected
        # base_style
        vram = VirtualColorRAM()
        vram.load_character_palette(char_pal, player_id=0, costume_style=base_style)

        result = (palettes, effect_palette_256, vram)
        _character_palette_cache[cache_key] = result
        return result

    except (ImportError, OSError, ValueError) as e:
        print(f"Warning: Failed to load palette from {palette_path}: {e}")
        return (None, None, None)


# pylint: disable=too-many-return-statements
def _map_palette_offset_to_style(pal_offset: int, base_style: int = 0) -> tuple[int, bool]:
    """
    Map game palette offset (attr & 0x1FF) to COL file style index.

    The game calculates: palt = (attr & 0x1FF) + palo
    Where palo is the character's base ColorRAM slot (0 for P1, 16 for P2).

    ColorRAM layout (for P1, palo=0):
    - Slot 0: col[0][Player_Color] (main character)
    - Slots 1-6: col[0][16-21] (effect palettes)
    - Slot 7, 15, 23, 31: hitmark palettes (special)
    - Slot 8: col[1][Player_Color] (character variant)
    - Slots 9-14: col[1][16-21] (effect variant)
    - Slots 502-505: col[0][22-25] (256-color effect block for P1)
    - Slots 506-509: col[0][22-25] (256-color effect block for P2)

    Args:
        pal_offset: Palette offset = (attr & 0x1FF) - this is the raw offset from sprite data
        base_style: The Player_Color index (0-5 for costume selection)

    Returns:
        Tuple of (style_index, use_effect_palette_256):
        - style_index: COL file style index (0-27)
        - use_effect_palette_256: True if this sprite should use the 256-color effect palette
    """
    # Check for 256-color effect palette slots (502-509)
    # These map to styles 22-25
    if 502 <= pal_offset <= 509:
        # Use the 256-color effect palette for all pixel indices
        return (22, True)

    # Normalize offset for P2 characters (offsets 16-31 mirror 0-15)
    normalized_offset = pal_offset % 16 if pal_offset < 32 else pal_offset

    if normalized_offset == 0:
        # Main character palette - use base style (costume)
        return (base_style, False)
    if 1 <= normalized_offset <= 6:
        # Effect palettes: offsets 1-6 map to styles 16-21
        return (15 + normalized_offset, False)  # 16, 17, 18, 19, 20, 21
    if normalized_offset == 7:
        # Hitmark slot - use style 0 as fallback (hitmarks not in COL file)
        return (base_style, False)
    if normalized_offset == 8:
        # Variant of main palette
        return (base_style, False)
    if 9 <= normalized_offset <= 14:
        # Effect variant palettes: mirror 1-6
        return (15 + (normalized_offset - 8), False)  # 16, 17, 18, 19, 20, 21
    # Higher offsets: cycle through available styles
    return (pal_offset % 28, False)


# pylint: disable=too-many-positional-arguments
def _load_indexed_sprite_with_palette(
    sprite_path: str,
    attr: int,
    palettes: list[list[tuple[int, int, int]]] | None,
    effect_palette_256: list[tuple[int, int, int]] | None = None,
    display_dims: tuple[int, int] | None = None,
    verbose: bool = True,
    base_style: int = 0,
    vram: "VirtualColorRAM | None" = None,
    parts_colcd_slot: int | None = None,
) -> Image.Image | None:
    """
    Load indexed sprite and apply palette based on attr value.

    Args:
        sprite_path: Path to indexed (grayscale) sprite PNG
        attr: Sprite attribute containing palette offset in bits 0-8
        palettes: List of style palettes (each 64 colors)
        effect_palette_256: Extended 256-color effect palette (styles 22-25)
        display_dims: Optional (dw, dh) for cropping
        verbose: Print debug info
        base_style: The Player_Color index (0-5) for base costume
        vram: Optional VirtualColorRAM for slot-based lookup
        parts_colcd_slot: Optional ColorRAM slot from ovct parts_colcd override

    Returns:
        RGBA image with palette applied, or None on error
    """
    try:
        with Image.open(sprite_path) as img:
            # Check if this is an indexed/grayscale sprite
            if img.mode == "L":
                # Indexed grayscale - apply palette
                indexed_data = list(img.getdata())
                width, height = img.size

                # Get palette offset from attr
                # Use lower 4 bits (0xF) for palette, as the higher bits
                # encode other data (dimensions, flags) in trans_table format
                pal_offset = attr & 0xF

                # Determine palette to use
                palette: list[tuple[int, int, int]] | None = None

                # Check if sprite uses high color indices (>63)
                max_index = max(indexed_data) if indexed_data else 0

                if max_index > 63 and effect_palette_256 is not None:
                    # Use the 256-color effect palette from styles 22-25
                    palette = effect_palette_256
                elif vram is not None:
                    # Use VirtualColorRAM for slot-based lookup
                    # If parts_colcd_slot is provided (from ovct table), it
                    # overrides the attr-derived pal_offset for effect sprites
                    slot = parts_colcd_slot if parts_colcd_slot is not None else pal_offset
                    slot_palette = vram.get_slot_palette(slot)
                    if slot_palette:
                        palette = slot_palette

                if palette is None:
                    # Fallback to style-based lookup
                    style_idx, use_effect_palette = _map_palette_offset_to_style(pal_offset, base_style)

                    if use_effect_palette and effect_palette_256 is not None:
                        palette = effect_palette_256
                    elif palettes and len(palettes) > 0:
                        if style_idx >= len(palettes):
                            style_idx = 0
                        palette = palettes[style_idx]
                    else:
                        # No palette available - use grayscale
                        palette = [(i, i, i) for i in range(256)]

                # Create RGBA image
                rgba_img = Image.new("RGBA", (width, height))
                pixels = rgba_img.load()

                for y in range(height):
                    for x in range(width):
                        color_index = indexed_data[y * width + x]
                        if color_index == 0:
                            # Index 0 is transparent
                            pixels[x, y] = (0, 0, 0, 0)
                        elif color_index < len(palette):
                            r, g, b = palette[color_index]
                            pixels[x, y] = (r, g, b, 255)
                        else:
                            # Out of bounds - magenta for debug
                            pixels[x, y] = (255, 0, 255, 255)

                sprite = rgba_img
            else:
                # Already RGBA - use as-is (legacy support)
                sprite = img.convert("RGBA")

        # Crop to display dimensions
        if display_dims is not None:
            dw, dh = display_dims
            if dw < sprite.width or dh < sprite.height:
                sprite = sprite.crop((0, 0, min(dw, sprite.width), min(dh, sprite.height)))

        # Apply flips
        if attr & 0x8000:
            sprite = sprite.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        if attr & 0x4000:
            sprite = sprite.transpose(Image.Transpose.FLIP_TOP_BOTTOM)

        return sprite

    except (OSError, ValueError) as e:
        if verbose:
            print(f"    Error loading sprite ({sprite_path}): {e}", flush=True)
        return None


def _read_frame_offsets(f: "BinaryIO", verbose: bool = True) -> list[int]:
    """Read frame offsets from the file header."""
    f.seek(0)
    first_offset_bytes = f.read(4)
    if len(first_offset_bytes) < 4:
        if verbose:
            print("Error: File too small.")
        return []

    first_offset = struct.unpack("<I", first_offset_bytes)[0]
    num_frames = first_offset // 4

    if verbose:
        print(f"Found {num_frames} frames (based on first offset {first_offset}).")

    f.seek(0)
    offsets = []
    for _ in range(num_frames):
        offset_bytes = f.read(4)
        if len(offset_bytes) < 4:
            break
        offsets.append(struct.unpack("<I", offset_bytes)[0])
    return offsets


def _load_and_transform_sprite(
    sprite_path: str, attr: int, display_dims: tuple[int, int] | None = None, verbose: bool = True
) -> Image.Image | None:
    """Load, crop to display dimensions, and apply transformations (flips) to a sprite.

    Game's UV flip happens WITHIN the display region (dw x dh), not the full cache block.
    So we must: 1) Load, 2) Crop to display dims, 3) Flip.
    """
    try:
        with Image.open(sprite_path) as img:
            sprite = img.convert("RGBA")

        # Crop to display dimensions FIRST (before flipping)
        # Game renders only dw x dh portion from top-left of cache block
        if display_dims is not None:
            dw, dh = display_dims
            if dw < sprite.width or dh < sprite.height:
                sprite = sprite.crop((0, 0, min(dw, sprite.width), min(dh, sprite.height)))

        # Apply flips AFTER cropping - UV flip happens within display region
        if attr & 0x8000:
            sprite = sprite.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        if attr & 0x4000:
            sprite = sprite.transpose(Image.Transpose.FLIP_TOP_BOTTOM)

        return sprite
    except (OSError, ValueError) as e:
        if verbose:
            print(f"    Error loading sprite ({sprite_path}): {e}", flush=True)
        return None


def _get_display_dimensions(tex_file: "BinaryIO", tex_offset: int, code: int) -> tuple[int, int]:
    """Get display dimensions (dw, dh) for a sprite from its texture header.

    The game's mlt_obj_trans reads dimensions from the texture header wh byte:
    - dw = (wh & 0xE0) >> 2  (display width)
    - dh = (wh & 0x1C) * 2   (display height)

    These can be non-square and smaller than the cached sprite block.
    For example, a 32x32 cache block may only display as 16x32.
    """
    # Read offset table entry for this code
    tex_file.seek(tex_offset + code * 4)
    sprite_offset_bytes = tex_file.read(4)
    if len(sprite_offset_bytes) < 4:
        return 32, 32  # Fallback

    sprite_offset = struct.unpack("<I", sprite_offset_bytes)[0]

    # Read wh byte from texture header
    tex_file.seek(tex_offset + sprite_offset)
    wh_byte = tex_file.read(1)
    if len(wh_byte) < 1:
        return 32, 32  # Fallback

    wh = wh_byte[0]

    # Game's formula for display dimensions
    dw = (wh & 0xE0) >> 2  # bits 5-7
    dh = (wh & 0x1C) * 2  # bits 2-4

    # Handle edge case where dw or dh is 0
    if dw == 0:
        dw = 8
    if dh == 0:
        dh = 8

    return dw, dh


# pylint: disable=too-many-locals,too-many-positional-arguments
def _process_frame(
    f: "BinaryIO",
    i: int,
    offset: int,
    *,
    sprite_dir: str,
    output_dir: str,
    tex_offset: int = 0,
    verbose: bool = True,
    use_multi_palette: bool = False,
    use_runtime_palette: bool = False,
    palettes: list[list[tuple[int, int, int]]] | None = None,
    effect_palette_256: list[tuple[int, int, int]] | None = None,
    vram: "VirtualColorRAM | None" = None,
    _default_effect_slot: int | None = None,
    ovct_entries: list | None = None,
    frame_olc_map: dict[int, int] | None = None,
) -> None:
    """Process a single frame and save the recomposed image.

    Args:
        f: Open file handle for character .bin file
        i: Frame index
        offset: Offset in file to frame data
        sprite_dir: Base directory for sprites (or containing pal_N subdirs)
        output_dir: Output directory for recomposed frames
        tex_offset: Offset to texture table for display dimension lookup
        verbose: Whether to print progress messages
        use_multi_palette: If True, look for sprites in pal_N subdirectories (deprecated)
        use_runtime_palette: If True, apply palette at runtime based on attr
        palettes: Pre-loaded palettes for runtime application
        effect_palette_256: Extended 256-color effect palette from styles 22-25
        vram: Optional VirtualColorRAM for slot-based palette lookup
        default_effect_slot: Override slot for effect sprites (e.g., 5 for purple instead of 1 for yellow)
    """
    if offset == 0:
        if verbose:
            print(f"Frame {i}: Offset is 0, skipping.", flush=True)
        return

    f.seek(offset)
    count_bytes = f.read(2)
    if len(count_bytes) < 2:
        return

    count = struct.unpack("<H", count_bytes)[0]
    if verbose:
        print(f"Frame {i}: Found {count} sprites.", flush=True)

    canvas_width, canvas_height = 512, 512
    center_x, center_y = canvas_width // 2, canvas_height // 2 + 100
    canvas = Image.new("RGBA", (canvas_width, canvas_height), (0, 0, 0, 0))

    curr_x, curr_y = 0, 0
    draw_list: list[tuple[Image.Image, int, int]] = []

    # Read all entries first, then process (to avoid file seek conflicts)
    entries = []
    for _ in range(count):
        entry_bytes = f.read(8)
        if len(entry_bytes) < 8:
            break
        entries.append(struct.unpack("<hhHH", entry_bytes))

    for x, y, attr, code in entries:
        # Position accumulation for non-flipped character:
        # Game uses Y-up coordinates: x -= delta, y += delta
        # We use Y-down (image coords): x -= delta, y -= delta (inverted Y)
        curr_x -= x
        curr_y -= y  # Inverted from game's Y-up to our Y-down

        # Resolve sprite path
        if use_multi_palette:
            pal_offset = attr & 0x1FF
            pal_sprite_dir = os.path.join(sprite_dir, f"pal_{pal_offset}")
            sprite_path = os.path.join(pal_sprite_dir, f"sprite_{code}.png")
            if not os.path.exists(sprite_path):
                pal_sprite_dir = os.path.join(sprite_dir, "pal_0")
                sprite_path = os.path.join(pal_sprite_dir, f"sprite_{code}.png")
        else:
            sprite_path = os.path.join(sprite_dir, f"sprite_{code}.png")

        if not os.path.exists(sprite_path):
            continue

        # Get display dimensions from texture header
        display_dims = None
        if tex_offset > 0:
            display_dims = _get_display_dimensions(f, tex_offset, code)

        # Load sprite with appropriate method
        if use_runtime_palette and palettes is not None:
            # Runtime palette application - use indexed sprite loader
            pal_offset = attr & 0xF
            parts_colcd_slot_override = None

            # Full OVCT integration: lookup parts_colcd for this frame
            if frame_olc_map is not None and ovct_entries is not None and vram is not None and i in frame_olc_map:
                olc_ix = frame_olc_map[i]
                if 0 <= olc_ix < len(ovct_entries):
                    parts_colcd = ovct_entries[olc_ix].parts_colcd
                    if parts_colcd > 0:
                        # Resolve parts_colcd to ColorRAM slot
                        resolved_slot, _ = vram.resolve_parts_colcd(parts_colcd, base_slot=0)
                        parts_colcd_slot_override = resolved_slot

            sprite = _load_indexed_sprite_with_palette(
                sprite_path,
                attr,
                palettes,
                effect_palette_256,
                display_dims,
                verbose,
                vram=vram,
                parts_colcd_slot=parts_colcd_slot_override,
            )
        else:
            # Legacy mode - sprites already have palette applied
            sprite = _load_and_transform_sprite(sprite_path, attr, display_dims, verbose)

        if not sprite:
            continue

        draw_x = center_x + curr_x
        draw_y = center_y + curr_y

        # Per-sprite flip flags (0x8000, 0x4000) only affect UV/texture rendering,
        # NOT the position. The position is calculated using x/y deltas independent
        # of flip state. No compensation is needed.

        draw_list.append((sprite, int(draw_x), int(draw_y)))

    for sprite_to_draw, dx, dy in draw_list:
        canvas.paste(sprite_to_draw, (dx, dy), sprite_to_draw)

    output_path = os.path.join(output_dir, f"frame_{i}.png")
    canvas.save(output_path)
    if verbose and i % 100 == 0:
        print(f"Saved frame {i} to {output_path}", flush=True)


# pylint: disable=too-many-positional-arguments
def _compose_frame_parallel(
    frame_idx: int,
    entries: list[tuple[int, int, int, int]],
    *,
    pl_file_path: str,
    sprite_dir: str,
    output_dir: str,
    tex_offset: int = 0,
    verbose: bool = True,
    use_multi_palette: bool = False,
    use_runtime_palette: bool = False,
    palettes: list[list[tuple[int, int, int]]] | None = None,
    effect_palette_256: list[tuple[int, int, int]] | None = None,
    vram: "VirtualColorRAM | None" = None,
    _default_effect_slot: int | None = None,
    ovct_entries: list | None = None,
    frame_olc_map: dict[int, int] | None = None,
) -> bool:
    """Compose a single frame from pre-read sprite entries. Thread-safe.

    Each call opens its own file handle for display dimension lookups,
    avoiding shared-state issues with the main file handle.

    Args:
        frame_idx: Frame index for output filename
        entries: List of (x, y, attr, code) tuples pre-read from the file
        pl_file_path: Path to character .bin file (for display dimension lookup)
        sprite_dir: Base directory for sprites
        output_dir: Output directory for recomposed frames
        tex_offset: Offset to texture table for display dimension lookup
        verbose: Whether to print progress messages
        use_multi_palette: If True, look for sprites in pal_N subdirectories
        use_runtime_palette: If True, apply palette at runtime based on attr
        palettes: Pre-loaded palettes for runtime application
        effect_palette_256: Extended 256-color effect palette from styles 22-25
        vram: Optional VirtualColorRAM for slot-based palette lookup
        _default_effect_slot: Override slot for effect sprites
        ovct_entries: List of OvctEntry objects for parts_colcd lookup
        frame_olc_map: Mapping from frame index to olc_ix for ovct lookup

    Returns:
        True if frame was saved successfully
    """
    if not entries:
        return False

    canvas_width, canvas_height = 512, 512
    center_x, center_y = canvas_width // 2, canvas_height // 2 + 100
    canvas = Image.new("RGBA", (canvas_width, canvas_height), (0, 0, 0, 0))

    curr_x, curr_y = 0, 0
    draw_list: list[tuple[Image.Image, int, int]] = []

    # Open own file handle for display dimension lookups (thread-safe)
    tex_file_handle = None
    if tex_offset > 0:
        try:
            tex_file_handle = open(pl_file_path, "rb")  # noqa: SIM115
        except OSError:
            tex_file_handle = None

    try:
        for x, y, attr, code in entries:
            curr_x -= x
            curr_y -= y

            # Resolve sprite path
            if use_multi_palette:
                pal_offset = attr & 0x1FF
                pal_sprite_dir = os.path.join(sprite_dir, f"pal_{pal_offset}")
                sprite_path = os.path.join(pal_sprite_dir, f"sprite_{code}.png")
                if not os.path.exists(sprite_path):
                    pal_sprite_dir = os.path.join(sprite_dir, "pal_0")
                    sprite_path = os.path.join(pal_sprite_dir, f"sprite_{code}.png")
            else:
                sprite_path = os.path.join(sprite_dir, f"sprite_{code}.png")

            if not os.path.exists(sprite_path):
                continue

            # Get display dimensions from texture header
            display_dims = None
            if tex_file_handle is not None:
                display_dims = _get_display_dimensions(tex_file_handle, tex_offset, code)

            # Load sprite with appropriate method
            if use_runtime_palette and palettes is not None:
                pal_offset = attr & 0xF
                parts_colcd_slot_override = None

                if frame_olc_map is not None and ovct_entries is not None and vram is not None and frame_idx in frame_olc_map:
                    olc_ix = frame_olc_map[frame_idx]
                    if 0 <= olc_ix < len(ovct_entries):
                        parts_colcd = ovct_entries[olc_ix].parts_colcd
                        if parts_colcd > 0:
                            resolved_slot, _ = vram.resolve_parts_colcd(parts_colcd, base_slot=0)
                            parts_colcd_slot_override = resolved_slot

                sprite = _load_indexed_sprite_with_palette(
                    sprite_path, attr, palettes, effect_palette_256,
                    display_dims, verbose, vram=vram,
                    parts_colcd_slot=parts_colcd_slot_override,
                )
            else:
                sprite = _load_and_transform_sprite(sprite_path, attr, display_dims, verbose)

            if not sprite:
                continue

            draw_x = center_x + curr_x
            draw_y = center_y + curr_y
            draw_list.append((sprite, int(draw_x), int(draw_y)))

        for sprite_to_draw, dx, dy in draw_list:
            canvas.paste(sprite_to_draw, (dx, dy), sprite_to_draw)

        output_path = os.path.join(output_dir, f"frame_{frame_idx}.png")
        canvas.save(output_path)
        if verbose and frame_idx % 100 == 0:
            print(f"Saved frame {frame_idx} to {output_path}", flush=True)
        return True

    finally:
        if tex_file_handle is not None:
            tex_file_handle.close()


# pylint: disable=too-many-positional-arguments
def recompose_frames(
    pl_file_path: str,
    sprite_dir: str,
    output_dir: str,
    verbose: bool = True,
    tex_offset: int = 0,
    use_multi_palette: bool = False,
    use_runtime_palette: bool = False,
    default_effect_slot: int | None = None,
    ovct_entries: list | None = None,
    frame_olc_map: dict[int, int] | None = None,
    base_style: int = 0,
) -> None:
    """Recomposes sprites into frames using layout data from the character file.

    Uses a two-phase approach for parallelism:
    - Phase 1: Sequential read of frame offset table and sprite entries
    - Phase 2: Parallel frame composition via ThreadPoolExecutor

    Args:
        pl_file_path: Path to the character .bin file
        sprite_dir: Directory containing extracted sprite PNGs
        output_dir: Directory to save composed frame PNGs
        verbose: Whether to print progress messages
        tex_offset: Offset to texture table within the file
        use_multi_palette: If True, look for sprites in pal_N subdirectories
        use_runtime_palette: If True, apply palette at runtime based on per-sprite attr
        default_effect_slot: Fallback override slot for effect sprites
        ovct_entries: List of OvctEntry objects for parts_colcd lookup
        frame_olc_map: Mapping from frame index to olc_ix for ovct lookup
        base_style: Costume/palette style index (0-5 for LP-EX costumes)
    """
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # Load palettes for runtime application if requested
    palettes = None
    effect_palette_256 = None
    vram = None
    if use_runtime_palette:
        palettes, effect_palette_256, vram = _load_palette_for_recomposition(sprite_dir, base_style)
        if palettes is None:
            print(f"Warning: No palette.col found in {sprite_dir}. Using legacy mode.")
            use_runtime_palette = False
        else:
            vram_info = f", VirtualColorRAM with {len(vram.loaded_slots)} slots" if vram else ""
            print(f"Loaded {len(palettes)} palette styles + 256-color effect palette{vram_info}.")

    try:
        # Phase 1: Sequential read — collect all frame entries
        frame_jobs: list[tuple[int, list[tuple[int, int, int, int]]]] = []

        with open(pl_file_path, "rb") as f:
            offsets = _read_frame_offsets(f, verbose)

            for i, offset in enumerate(offsets):
                if offset == 0:
                    continue

                f.seek(offset)
                count_bytes = f.read(2)
                if len(count_bytes) < 2:
                    continue

                count = struct.unpack("<H", count_bytes)[0]
                if verbose and i % 100 == 0:
                    print(f"Frame {i}: Found {count} sprites.", flush=True)

                entries = []
                for _ in range(count):
                    entry_bytes = f.read(8)
                    if len(entry_bytes) < 8:
                        break
                    entries.append(struct.unpack("<hhHH", entry_bytes))

                if entries:
                    frame_jobs.append((i, entries))

        if verbose:
            print(f"Read {len(frame_jobs)} frame jobs, starting parallel composition...", flush=True)

        # Phase 2: Parallel frame composition
        from concurrent.futures import ThreadPoolExecutor  # pylint: disable=import-outside-toplevel

        max_workers = min(os.cpu_count() or 4, 8)

        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = [
                pool.submit(
                    _compose_frame_parallel,
                    frame_idx,
                    entries,
                    pl_file_path=pl_file_path,
                    sprite_dir=sprite_dir,
                    output_dir=output_dir,
                    tex_offset=tex_offset,
                    verbose=verbose,
                    use_multi_palette=use_multi_palette,
                    use_runtime_palette=use_runtime_palette,
                    palettes=palettes,
                    effect_palette_256=effect_palette_256,
                    vram=vram,
                    _default_effect_slot=default_effect_slot,
                    ovct_entries=ovct_entries,
                    frame_olc_map=frame_olc_map,
                )
                for frame_idx, entries in frame_jobs
            ]

            # Wait for all to complete, propagating any exceptions
            for future in futures:
                future.result()

    except (OSError, ValueError, struct.error) as e:
        print(f"Error processing file: {e}")
        traceback.print_exc()


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: python -m sf33rd.tools.frame_recomposer <pl_file> <sprite_dir> <output_dir>")
    else:
        recompose_frames(sys.argv[1], sys.argv[2], sys.argv[3])
