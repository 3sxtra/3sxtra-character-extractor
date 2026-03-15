"""Texture Unpacker Module.

Unpacks compressed and swizzled texture files (TEX) into PNG images.
"""

import contextlib
import logging
import os
import shutil
import struct
import sys

from PIL import Image

from sf33rd.core.data_model import character_data
from sf33rd.core.lib import decompress_p6_fx
from sf33rd.lib.image import prepare_pil_palette
from sf33rd.lib.palette import CharacterPalette
from sf33rd.lib.swizzle import DCTEX_LINEAR, unswizzle_dreamcast
from sf33rd.utils.file_utils import read_pointers

# Configure logging (only if not already configured)
if not logging.getLogger().hasHandlers():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


# pylint: disable=too-many-positional-arguments, too-many-locals,
# redefined-outer-name
def unpack_character_sprites(
    character_name, afs_dir, output_dir, max_sprites=100000, override_palette_path=None, palette_index=0
):
    """Unpacks all sprites for a given character.

    This function reads the character's texture and palette files, and then
    calls `unpack_tex_file` to extract and save the individual sprites.

    Args:
        character_name (str): The name of the character.
        afs_dir (str): The path to the directory containing the extracted AFS
            files.
        output_dir (str): The directory to save the unpacked sprites to.
        max_sprites (int, optional): The maximum number of sprites to unpack.
            Defaults to 100000.
        override_palette_path (str, optional): The path to a custom palette
            file to use instead of the character's default palette. Defaults
            to None.
        palette_index (int, optional): The index of the sub-palette to use.
            Defaults to 0.
    """
    logging.info("Unpacking sprites for character: %s", character_name)

    if not os.path.exists(output_dir):
        try:
            os.makedirs(output_dir)
            logging.info("Created output directory: %s", output_dir)
        except OSError as e:
            logging.error("Failed to create output directory %s: %s", output_dir, e)
            return

    # Look up the file numbers for the character
    if character_name not in character_data:
        logging.error("Character not found in data model: %s", character_name)
        return

    char_files = character_data[character_name]
    tex_filepath = os.path.join(str(afs_dir), str(char_files["tex"]))

    col_filepath = override_palette_path or os.path.join(str(afs_dir), str(char_files["col"]))

    to_tex = char_files.get("to_tex", 0)

    logging.info("Texture file: %s", tex_filepath)
    logging.info("Color file: %s", col_filepath)
    logging.info("Texture offset: %s", to_tex)

    # Parse the character palette using new CharacterPalette class
    try:
        char_palette = CharacterPalette.from_file(col_filepath)
        logging.info("Loaded character palette: %s (%d styles available)", char_palette, char_palette.num_styles)
    except (OSError, ValueError) as e:
        logging.error("Failed to load palette: %s", e)
        return

    # Get the active palette for the selected style (0-27)
    # Clamp palette_index to valid style range
    style_index = palette_index % char_palette.num_styles
    if palette_index != style_index:
        logging.warning("Palette index %d out of range, using style %d instead.", palette_index, style_index)

    active_palette = char_palette.get_style_rgb_list(style_index)
    logging.info("Using style %d (variant 0): %d colors", style_index, len(active_palette))

    # Unpack the texture file
    unpack_tex_file(tex_filepath, active_palette, output_dir, max_sprites, to_tex)


def analyze_frame_palette_offsets(pl_file_path: str) -> set[int]:
    """
    Analyze which palette offsets are used in character frame data.

    Args:
        pl_file_path: Path to the character .bin file

    Returns:
        Set of unique palette offsets (attr & 0x1FF) found in frame data
    """
    palette_offsets: set[int] = set()

    try:
        with open(pl_file_path, "rb") as f:
            # Read frame offsets
            f.seek(0)
            first_offset_bytes = f.read(4)
            if len(first_offset_bytes) < 4:
                return palette_offsets

            first_offset = struct.unpack("<I", first_offset_bytes)[0]
            num_frames = first_offset // 4

            f.seek(0)
            offsets = []
            for _ in range(num_frames):
                offset_bytes = f.read(4)
                if len(offset_bytes) < 4:
                    break
                offsets.append(struct.unpack("<I", offset_bytes)[0])

            # Scan all frames for palette offsets
            for offset in offsets:
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

                    _, _, attr, _ = struct.unpack("<hhHH", entry_bytes)
                    palette_offset = attr & 0x1FF
                    palette_offsets.add(palette_offset)

    except (OSError, struct.error) as e:
        logging.warning("Error analyzing frame palette offsets: %s", e)

    return palette_offsets


def unpack_character_sprites_multi_palette(
    character_name: str,
    afs_dir: str,
    output_dir: str,
    max_sprites: int = 100000,
    override_palette_path: str | None = None,
) -> list[int]:
    """
    Unpacks sprites with multiple palettes based on frame data analysis.

    Analyzes the character's frame data to find which palette offsets are used,
    then extracts sprites with each required palette into subdirectories.

    Args:
        character_name: The name of the character
        afs_dir: Path to directory containing extracted AFS files
        output_dir: Base directory to save sprites (creates pal_N subdirs)
        max_sprites: Maximum sprites to extract
        override_palette_path: Optional custom palette file path

    Returns:
        List of palette offsets that were extracted
    """
    logging.info("Multi-palette extraction for character: %s", character_name)

    # Look up character files
    if character_name not in character_data:
        logging.error("Character not found in data model: %s", character_name)
        return []

    char_files = character_data[character_name]
    tex_filepath = os.path.join(str(afs_dir), str(char_files["tex"]))
    col_filepath = override_palette_path or os.path.join(str(afs_dir), str(char_files["col"]))
    to_tex = char_files.get("to_tex", 0)

    # Analyze frame data to find used palette offsets
    palette_offsets = analyze_frame_palette_offsets(tex_filepath)

    if not palette_offsets:
        logging.warning("No palette offsets found in frame data, using default (0)")
        palette_offsets = {0}

    logging.info("Found %d unique palette offsets: %s", len(palette_offsets), sorted(palette_offsets))

    # Load the full palette file
    try:
        char_palette = CharacterPalette.from_file(col_filepath)
    except (OSError, ValueError) as e:
        logging.error("Failed to load palette: %s", e)
        return []

    extracted_offsets: list[int] = []

    # Extract sprites for each palette offset
    for pal_offset in sorted(palette_offsets):
        # Map palette offset to style index
        # Character palettes: offsets 0-7 map to styles 0-7
        # Higher offsets may need special handling
        style_index = pal_offset % char_palette.num_styles

        palette_output_dir = os.path.join(output_dir, f"pal_{pal_offset}")

        logging.info("Extracting with palette offset %d (style %d) to %s", pal_offset, style_index, palette_output_dir)

        try:
            os.makedirs(palette_output_dir, exist_ok=True)

            active_palette = char_palette.get_style_rgb_list(style_index)

            unpack_tex_file(tex_filepath, active_palette, palette_output_dir, max_sprites, to_tex)

            extracted_offsets.append(pal_offset)

        except (OSError, ValueError) as e:
            logging.error("Failed to extract with palette %d: %s", pal_offset, e)

    logging.info("Multi-palette extraction complete. Extracted %d palette variants.", len(extracted_offsets))

    return extracted_offsets


# pylint: disable=too-many-positional-arguments, too-many-locals, redefined-outer-name
def unpack_tex_file(bin_filepath, palette, output_dir, max_sprites=9999, offset=0, start_sprite_index=0):
    """
    Unpacks a TEX file, which can contain multiple sprites.

    This function reads a TEX file, which is a container for multiple
    compressed and swizzled sprites. It reads the offset table at the
    beginning of the file to find the individual sprites, and then
    decompresses, unswizzles, and saves each one as a PNG image.

    Args:
        bin_filepath (str): The path to the TEX file.
        palette (list): A list of (r, g, b) tuples representing the palette.
        output_dir (str): The directory to save the unpacked sprites to.
        max_sprites (int, optional): The maximum number of sprites to unpack.
            Defaults to 9999.
        offset (int, optional): The offset within the file to start reading
            from. Defaults to 0.
        start_sprite_index (int, optional): The starting index for naming output
            files (e.g., sprite_{i + start_sprite_index}.png). Defaults to 0.
    """
    with contextlib.suppress(OSError):
        os.makedirs(output_dir)

    if not os.path.exists(bin_filepath):
        logging.error("TEX file not found: %s", bin_filepath)
        return

    file_size = os.path.getsize(bin_filepath)
    logging.info("TEX file size: %s bytes", file_size)

    try:
        with open(bin_filepath, "rb") as f:
            f.seek(offset)

            base_offset = f.tell()  # Store the start of the offset table

            first_offset_bytes = f.read(4)
            if len(first_offset_bytes) < 4:
                logging.error("Failed to read first offset")
                return

            first_offset = struct.unpack("<I", first_offset_bytes)[0]
            num_entries = first_offset // 4

            logging.info("First offset: %s, expecting %s entries.", first_offset, num_entries)

            offsets = [first_offset]
            f.seek(base_offset + 4)  # Reposition to read the second offset

            for i in range(num_entries - 1):
                offset_bytes = f.read(4)
                if len(offset_bytes) < 4:
                    logging.warning("End of file reached while reading offsets at index %s", i + 1)
                    break
                offset = struct.unpack("<I", offset_bytes)[0]
                offsets.append(offset)

                if i < 5:
                    logging.info("Offset %s: %s", i + 1, offset)

            logging.info("Read %s offsets.", len(offsets))

            dctex_linear = DCTEX_LINEAR

            sprites_extracted = 0
            for i in range(min(len(offsets), max_sprites)):
                current_rel_offset = offsets[i]
                f.seek(base_offset + current_rel_offset)

                # Read TEX struct
                wh_byte = struct.unpack("B", f.read(1))[0]
                tile_size = (wh_byte & 3) + 1  # 1, 2, 3, or 4

                texture_width = tile_size * 8
                texture_height = tile_size * 8

                data_size = (tile_size * tile_size) << 6

                logging.info(
                    "  Entry %s: wh=0x%02x, tile_size=%s, tex_size=%sx%s, data_size=%s",
                    i,
                    wh_byte,
                    tile_size,
                    texture_width,
                    texture_height,
                    data_size,
                )

                if texture_width == 0 or texture_height == 0:
                    continue

                compressed_data = f.read(data_size)

                if len(compressed_data) < data_size:
                    logging.warning("  Entry %s: Not enough data", i)
                    continue

                try:
                    # Decompress using P6/LZ77 (type 1)
                    decompressed_data = decompress_p6_fx(compressed_data, data_size)

                    if len(decompressed_data) != data_size:
                        logging.warning(
                            "  Entry %s: Decompressed size mismatch: %s vs %s", i, len(decompressed_data), data_size
                        )
                        # Pad or truncate
                        if len(decompressed_data) < data_size:
                            decompressed_data += b"\x00" * (data_size - len(decompressed_data))
                        else:
                            decompressed_data = decompressed_data[:data_size]

                    # Unswizzle
                    unswizzled_data = bytearray(data_size)

                    for y in range(texture_height):
                        for x in range(texture_width):
                            src_idx = dctex_linear[x + y * 32]
                            if src_idx < len(decompressed_data):
                                unswizzled_data[y * texture_width + x] = decompressed_data[src_idx]
                            else:
                                unswizzled_data[y * texture_width + x] = 0

                    # Create image with alpha channel
                    img = Image.new("RGBA", (texture_width, texture_height))
                    pixels = img.load()

                    # Apply palette (8-bit)
                    for y in range(texture_height):
                        for x in range(texture_width):
                            color_index = unswizzled_data[y * texture_width + x]
                            if color_index == 0:
                                # Make index 0 fully transparent
                                pixels[x, y] = (0, 0, 0, 0)
                            elif color_index < len(palette):
                                r, g, b = palette[color_index]
                                pixels[x, y] = (r, g, b, 255)
                            else:
                                # Out of bounds - magenta for debugging
                                pixels[x, y] = (255, 0, 255, 255)

                    output_filepath = os.path.join(output_dir, f"sprite_{i + start_sprite_index}.png")
                    img.save(output_filepath)
                    logging.info("    Saved to %s", output_filepath)
                    sprites_extracted += 1

                except (OSError, ValueError, struct.error) as e:
                    logging.exception("    Error processing entry %s: %s", i, e)

    except Exception as e:  # pylint: disable=broad-exception-caught
        logging.exception("Error unpacking TEX file: %s", e)


def _process_indexed_sprite(
    sprite_idx: int,
    wh_byte: int,
    compressed_data: bytes,
    output_dir: str,
    start_sprite_index: int,
) -> bool:
    """Process a single indexed sprite: decompress, unswizzle, save.

    Thread-safe — no shared mutable state. Each call is independent.

    Args:
        sprite_idx: Sprite index for filename
        wh_byte: TEX header byte encoding tile size
        compressed_data: Raw compressed sprite data
        output_dir: Output directory for PNGs
        start_sprite_index: Offset for output filename numbering

    Returns:
        True if sprite was saved successfully
    """
    dctex_linear = DCTEX_LINEAR

    tile_size = (wh_byte & 3) + 1
    texture_width = tile_size * 8
    texture_height = tile_size * 8
    data_size = (tile_size * tile_size) << 6

    if texture_width == 0 or texture_height == 0:
        return False

    try:
        decompressed_data = decompress_p6_fx(compressed_data, data_size)

        if len(decompressed_data) != data_size:
            if len(decompressed_data) < data_size:
                decompressed_data += b"\x00" * (data_size - len(decompressed_data))
            else:
                decompressed_data = decompressed_data[:data_size]

        # Unswizzle
        unswizzled_data = bytearray(data_size)
        for y in range(texture_height):
            for x in range(texture_width):
                src_idx = dctex_linear[x + y * 32]
                if src_idx < len(decompressed_data):
                    unswizzled_data[y * texture_width + x] = decompressed_data[src_idx]

        # Save as indexed grayscale PNG (mode "L" = 8-bit pixels)
        img = Image.new("L", (texture_width, texture_height))
        img.putdata(bytes(unswizzled_data))

        output_filepath = os.path.join(output_dir, f"sprite_{sprite_idx + start_sprite_index}.png")
        img.save(output_filepath)
        return True

    except (OSError, ValueError, struct.error) as e:
        logging.exception("Error processing entry %s: %s", sprite_idx, e)
        return False


def unpack_tex_file_indexed(
    bin_filepath: str, output_dir: str, max_sprites: int = 9999, offset: int = 0, start_sprite_index: int = 0
) -> int:
    """Unpacks a TEX file as indexed grayscale PNGs (raw pixel indices).

    Uses a two-phase approach for parallelism:
    - Phase 1: Sequential file read to collect all compressed sprite chunks
    - Phase 2: Parallel decompress + unswizzle + save via ThreadPoolExecutor

    Args:
        bin_filepath: Path to the TEX file
        output_dir: Directory to save indexed sprite PNGs
        max_sprites: Maximum number of sprites to unpack
        offset: Offset within file to start reading
        start_sprite_index: Starting index for naming output files

    Returns:
        Number of sprites extracted
    """
    with contextlib.suppress(OSError):
        os.makedirs(output_dir)

    if not os.path.exists(bin_filepath):
        logging.error("TEX file not found: %s", bin_filepath)
        return 0

    try:
        # Phase 1: Sequential read — collect all compressed chunks
        chunks: list[tuple[int, int, bytes]] = []  # (sprite_idx, wh_byte, data)

        with open(bin_filepath, "rb") as f:
            f.seek(offset)
            base_offset = f.tell()

            first_offset_bytes = f.read(4)
            if len(first_offset_bytes) < 4:
                logging.error("Failed to read first offset")
                return 0

            first_offset = struct.unpack("<I", first_offset_bytes)[0]
            num_entries = first_offset // 4

            offsets = [first_offset]
            f.seek(base_offset + 4)

            for _ in range(num_entries - 1):
                offset_bytes = f.read(4)
                if len(offset_bytes) < 4:
                    break
                offsets.append(struct.unpack("<I", offset_bytes)[0])

            for i in range(min(len(offsets), max_sprites)):
                current_rel_offset = offsets[i]
                f.seek(base_offset + current_rel_offset)

                wh_byte = struct.unpack("B", f.read(1))[0]
                tile_size = (wh_byte & 3) + 1
                data_size = (tile_size * tile_size) << 6

                compressed_data = f.read(data_size)
                if len(compressed_data) < data_size:
                    continue

                chunks.append((i, wh_byte, compressed_data))

        logging.info("Read %d sprite chunks from %s", len(chunks), bin_filepath)

        # Phase 2: Parallel decompress + unswizzle + save
        from concurrent.futures import ThreadPoolExecutor  # pylint: disable=import-outside-toplevel

        max_workers = min(os.cpu_count() or 4, 8)
        sprites_extracted = 0

        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = [
                pool.submit(
                    _process_indexed_sprite,
                    sprite_idx,
                    wh_byte,
                    compressed_data,
                    output_dir,
                    start_sprite_index,
                )
                for sprite_idx, wh_byte, compressed_data in chunks
            ]

            for future in futures:
                if future.result():
                    sprites_extracted += 1

    except Exception as e:  # pylint: disable=broad-exception-caught
        logging.exception("Error unpacking indexed TEX file: %s", e)
        return 0

    logging.info("Extracted %d indexed sprites to %s", sprites_extracted, output_dir)
    return sprites_extracted


def unpack_character_sprites_indexed(
    character_name: str,
    afs_dir: str | None = None,
    output_dir: str = "",
    max_sprites: int = 100000,
    override_palette_path: str | None = None,
    data_source=None,
) -> bool:
    """
    Unpacks character sprites as indexed images with palette saved separately.

    This enables runtime palette application based on per-sprite attr values.

    Args:
        character_name: Name of the character
        afs_dir: Path to extracted AFS files (legacy, optional if data_source provided)
        output_dir: Output directory for sprites and palette
        max_sprites: Maximum sprites to extract
        override_palette_path: Optional custom palette file
        data_source: Optional AfsDataSource for reading directly from archive

    Returns:
        True if successful
    """
    logging.info("Indexed extraction for character: %s", character_name)

    if character_name not in character_data:
        logging.error("Character not found: %s", character_name)
        return False

    char_files = character_data[character_name]
    tex_filename = str(char_files["tex"])
    col_filename = str(char_files["col"])
    to_tex = int(char_files.get("to_tex", 0))  # type: ignore[call-overload]

    # Resolve file access: prefer data_source if provided
    if data_source is not None:
        # Use AfsDataSource for file access
        tex_data = data_source.get_file_data(tex_filename)
        col_data = data_source.get_file_data(col_filename) if not override_palette_path else None

        # Write tex data to temp file for extraction (indexed extractor needs
        # file path)
        import tempfile  # pylint: disable=import-outside-toplevel

        temp_dir = tempfile.mkdtemp(prefix="sf33rd_extract_")
        tex_filepath = os.path.join(temp_dir, tex_filename)
        with open(tex_filepath, "wb") as f:
            f.write(tex_data)

        if override_palette_path:
            col_filepath = override_palette_path
        else:
            col_filepath = os.path.join(temp_dir, col_filename)
            with open(col_filepath, "wb") as f:
                f.write(col_data)  # type: ignore
    else:
        # Legacy mode: use afs_dir path
        if not afs_dir:
            logging.error("Either afs_dir or data_source must be provided")
            return False
        tex_filepath = os.path.join(str(afs_dir), tex_filename)
        col_filepath = override_palette_path or os.path.join(str(afs_dir), col_filename)

    # Extract sprites as indexed
    sprites_dir = output_dir
    sprites_extracted = unpack_tex_file_indexed(tex_filepath, sprites_dir, max_sprites, to_tex)

    if sprites_extracted == 0:
        logging.error("No sprites extracted")
        return False

    # Copy the palette file to output directory for runtime use
    palette_dest = os.path.join(output_dir, "palette.col")
    try:
        shutil.copy2(col_filepath, palette_dest)
        logging.info("Saved palette to %s", palette_dest)
    except (OSError, shutil.Error) as e:
        logging.error("Failed to copy palette: %s", e)
        return False

    logging.info("Indexed extraction complete: %d sprites + palette", sprites_extracted)
    return True


def extract_sprites_on_demand(
    tex_filepath: str,
    sprite_indices: list[int],
    tex_offset: int = 0,
) -> dict[int, bytes]:
    """Extract specific sprites from TEX file to in-memory indexed data.

    This function extracts only the requested sprites without writing to disk,
    enabling lazy preview for unextracted characters.

    Args:
        tex_filepath: Path to the TEX file
        sprite_indices: List of sprite indices to extract
        tex_offset: Offset within file to start reading

    Returns:
        Dict mapping sprite_idx -> bytes (indexed pixel data, 8-bit per pixel)
    """
    result: dict[int, bytes] = {}

    if not os.path.exists(tex_filepath):
        logging.error("TEX file not found: %s", tex_filepath)
        return result

    dctex_linear = DCTEX_LINEAR

    try:
        with open(tex_filepath, "rb") as f:
            f.seek(tex_offset)
            base_offset = f.tell()

            # Read offset table
            first_bytes = f.read(4)
            if len(first_bytes) < 4:
                return result

            first_offset = struct.unpack("<I", first_bytes)[0]
            num_entries = first_offset // 4

            # Read all offsets
            f.seek(base_offset)
            offsets = []
            for _ in range(num_entries):
                offset_bytes = f.read(4)
                if len(offset_bytes) < 4:
                    break
                offsets.append(struct.unpack("<I", offset_bytes)[0])

            # Extract only requested sprites
            for sprite_idx in sprite_indices:
                if sprite_idx >= len(offsets):
                    continue

                current_offset = offsets[sprite_idx]
                f.seek(base_offset + current_offset)

                # Read TEX struct
                wh_byte = struct.unpack("B", f.read(1))[0]
                tile_size = (wh_byte & 3) + 1
                texture_width = tile_size * 8
                texture_height = tile_size * 8
                data_size = (tile_size * tile_size) << 6

                if texture_width == 0 or texture_height == 0:
                    continue

                compressed_data = f.read(data_size)
                if len(compressed_data) < data_size:
                    continue

                try:
                    # Decompress
                    decompressed = decompress_p6_fx(compressed_data, data_size)

                    if len(decompressed) < data_size:
                        decompressed += b"\x00" * (data_size - len(decompressed))
                    elif len(decompressed) > data_size:
                        decompressed = decompressed[:data_size]

                    # Unswizzle
                    unswizzled = bytearray(data_size)
                    for y in range(texture_height):
                        for x in range(texture_width):
                            src_idx = dctex_linear[x + y * 32]
                            if src_idx < len(decompressed):
                                unswizzled[y * texture_width + x] = decompressed[src_idx]

                    result[sprite_idx] = bytes(unswizzled)

                except (OSError, ValueError) as e:
                    logging.warning("Error extracting sprite %d: %s", sprite_idx, e)

    except Exception as e:  # pylint: disable=broad-exception-caught
        logging.exception("Error in on-demand extraction: %s", e)

    return result


def main():
    """Main execution entry point."""
    if len(sys.argv) < 2:
        print(
            "Usage: python texture_unpacker.py <character_name> [afs_directory] "
            "[output_directory] [max_sprites] [palette_path] [palette_index]"
        )
        sys.exit(1)

    char_name_arg = sys.argv[1]
    afs_dir_arg = sys.argv[2] if len(sys.argv) > 2 else "afsextracted"
    output_dir_arg = sys.argv[3] if len(sys.argv) > 3 else "sprites_%s"

    # Ensure output directory exists - handled by function now, but good
    # hygiene here too
    if not os.path.exists(output_dir_arg):
        os.makedirs(output_dir_arg)

    max_sprites_arg = int(sys.argv[4]) if len(sys.argv) > 4 else 100000

    pal_path_arg = None
    if len(sys.argv) > 5:
        pal_path_arg = sys.argv[5]
        if pal_path_arg == "None":
            pal_path_arg = None

    pal_idx_arg = 0
    if len(sys.argv) > 6:
        pal_idx_arg = int(sys.argv[6])

    unpack_character_sprites(char_name_arg, afs_dir_arg, output_dir_arg, max_sprites_arg, pal_path_arg, pal_idx_arg)


if __name__ == "__main__":
    main()


# pylint: disable=too-many-locals, unused-argument, too-many-nested-blocks, redefined-outer-name
def unpack_tex_file_heuristic(bin_filepath, palette, output_dir, _prefix="sprite", palette_offset=0):
    """
    Unpacks a TEX file using a heuristic approach (Tail-based 8bpp).
    Useful for efXX.bin files where standard headers might be misleading or missing.
    """
    logging.info("Unpacking TEX file (Heuristic): %s", os.path.basename(bin_filepath))

    if not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)

    if not os.path.exists(bin_filepath):
        logging.error("File not found: %s", bin_filepath)
        return

    with open(bin_filepath, "rb") as f:
        data = f.read()

    # Extract chunks based on offsets
    if len(data) < 4:
        return

    unique_offsets = read_pointers(data)

    # Construct a valid 256-color palette for Pillow
    pil_palette = prepare_pil_palette(palette, palette_offset)

    sprites_extracted = 0

    for i, off in enumerate(unique_offsets):
        size = unique_offsets[i + 1] - off if i + 1 < len(unique_offsets) else len(data) - off

        chunk_data = data[off : off + size]

        try:
            decomp = decompress_p6_fx(chunk_data)
            if len(decomp) < 8:
                continue

            w_header = struct.unpack("<H", decomp[0:2])[0]

            # Heuristic Decision Tree
            pixels: bytes | None = None

            # 1. Check for Standard 8-pixel strip (Tail-based)
            # This is the most common case for standard tiles
            is_standard_strip = False
            if w_header in [8, 16, 32, 64, 128, 256]:
                expected_pixels = w_header * 8
                if len(decomp) >= expected_pixels:
                    # Check if using the tail makes sense (e.g. header size is
                    # reasonable)
                    header_size = len(decomp) - expected_pixels
                    if header_size < 64:  # Arbitrary threshold for header size
                        w = w_header
                        h = 8
                        pixels = decomp[-expected_pixels:]
                        is_standard_strip = True

            w = 0
            h = 0

            if is_standard_strip:
                w = w_header
                h = 8
                pixels = decomp[-(w * h) :]
            else:
                # 2. Try Fixed Width 16 (User feedback for Sprite 42)
                # If header W is weird (e.g. 11), try treating as raw 16-width
                # strip
                w_fixed = 16
                h_fixed = len(decomp) // w_fixed

                # Only use this if it covers most of the data
                remainder = len(decomp) % w_fixed

                if h_fixed > 0 and remainder < 16:  # Allow small header/padding
                    w = w_fixed
                    h = h_fixed
                    pixels = decomp[: w * h]
                else:
                    # 3. Fallback: Use Header W, infer H
                    w = w_header
                    if w > 0:
                        h = (len(decomp) - 4) // w
                        if h > 0:
                            pixels = decomp[4 : 4 + (w * h)]

            if pixels and w > 0 and h > 0:
                # Try swizzled if square
                final_pixels = pixels
                if w == h and w in [8, 16, 32, 64, 128, 256]:
                    try:
                        unswizzled_pixels = unswizzle_dreamcast(pixels, w, h, 1)
                        final_pixels = unswizzled_pixels
                    except Exception:  # pylint: disable=broad-exception-caught
                        pass

                output_filepath = os.path.join(output_dir, f"sprite_{i}.png")

                img = Image.new("P", (w, h))
                img.putpalette(pil_palette)
                img.putdata(final_pixels)
                img.save(output_filepath)

                sprites_extracted += 1

        except (OSError, ValueError) as e:
            logging.warning("Error processing chunk %s: %s", i, e)

    logging.info("Heuristic extraction complete. Extracted %s sprites.", sprites_extracted)
