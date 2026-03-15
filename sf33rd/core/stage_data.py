"""
Stage layout and texture mapping data.
Transcribed from bg_data.c
"""

from collections.abc import Callable

# Which bits in the 32-bit integer enable textures for a layer?
# [Stage Index][Layer Index (0-2)]
# Transcribed from bg_data.c: const u32 bgtex_stage_gbix[22][3]
bgtex_stage_gbix = [
    [0xF0F0F0F0, 0x7F7FFFFF, 0x0],
    [0xFFFFFFFF, 0x0, 0x0],
    [0x3078FCFF, 0xFF, 0x7E7E7E7E],
    [0xFFFFFFFF, 0xC0E0F1FF, 0x0],
    [0xFFFFFFFF, 0x0, 0x0],
    [0x7E7E7E7E, 0x424FEFFF, 0x0],
    [0xFFFFFFFF, 0x0, 0x0],
    [0x7E00007E, 0xF0FFF2FF, 0x7E7E7E00],
    [0x3C3C3C3C, 0xFF, 0x0],
    [0x7F7F7F3F, 0x80F4FF, 0x0],
    [0xFFFFFFFF, 0xFFFFFFFF, 0x0],
    [0xFFFFFFFF, 0x0, 0x0],
    [0x7F7F7F3F, 0x98FFFFF, 0x0],
    [0xFFFFFF38, 0x3FFFFFFF, 0x0],
    [0xFFFFFFFF, 0x6FEFEFFF, 0x18181818],
    [0xFFFFFFFF, 0x80E6FFFF, 0x0],
    [0x7E7E0000, 0x77FFFFF, 0x0],
    [0x7E7E0000, 0x77FFFFF, 0x0],
    [0x7E7E7E7E, 0x424FEFFF, 0x0],
    [0xFFFFFFFF, 0x0, 0x0],
    [0x3C3C3C1C, 0x20343C3C, 0x0],
    [0x3E3E3E3E, 0x0, 0x0],
]
"""A list of lists of integers representing the texture masks for each stage.

Each inner list corresponds to a stage, and each integer in the inner list
is a 32-bit mask that determines which textures are loaded for a particular
layer.
"""

use_scr = [2, 2, 3, 2, 2, 2, 2, 3, 2, 2, 2, 2, 2, 2, 3, 2, 2, 2, 2, 2, 2, 2, 2]
"""A list of integers representing the total number of layers used by each stage."""

use_real_scr = [2, 1, 3, 2, 1, 2, 1, 3, 2, 2, 2, 1, 2, 2, 3, 2, 2, 2, 2, 1, 2, 1, 1]
"""A list of integers representing the number of scrollable layers used by each stage."""


def get_layer_gbix_offset(layer_idx: int) -> int:
    """Calculates the Global Index (GBIX) offset for a given layer.

    In the game's engine, each texture is assigned a unique Global Index (GBIX).
    This function calculates the starting GBIX for the static textures of a
    given layer. Static textures are those that are not animated and are
    stored in the main `stageXX.ppg` file.

    Args:
        layer_idx (int): The index of the layer.

    Returns:
        int: The GBIX offset for the layer.
    """
    # Loading base for static textures
    return (layer_idx * 64) + 132


def get_layer_palette_base(stage_idx: int, layer_idx: int) -> int:
    """
    Get the base palette index (colcd) for a specific layer.

    Since we don't have the original bg_data.c, we use known values and defaults.
    Default seems to be 300 (0x12C).
    """
    # Known overrides
    if stage_idx == 2:  # Stage 2 (Castle)
        if layer_idx == 0:
            return 512  # Castle structure
        if layer_idx == 1:
            return 256  # Sky? (Guessing, need verification)

    # Default
    return 300


def get_stage_palette_map_func(stage_id: int) -> Callable[[int], int] | None:
    """
    Returns a function(offset) -> new_offset for remapping palette indices.
    Used for stages with complex palette mapping (e.g. Stage 2).
    """
    if stage_id == 2:
        # Stage 2 (Castle) uses a modulo 14 mapping for some reason.
        # Offset 22 -> 8 (Beige)
        # Offset 7 -> 7 (Teal)
        # DISABLE MAPPING: This causes color issues in the editor (WIP view).
        # The original game might use this, but our extracted palette/tiles seem to work without it.
        # def mod14_map(offset):
        #     return offset % 14
        # return mod14_map
        return None
    return None


def get_stage_palette_loading_offset(_stage_id: int) -> int:
    """
    Returns the base palette bank index for loading the stage's palette.
    Based on bgPalCodeOffset = 0x12C (300) in bg.c.
    This is a BANK index (multiply by 64 for color index).
    """
    # Most stages use 300
    return 300


def get_stage_file_name_prefix(stage_idx: int) -> str:
    """Returns the filename prefix for a stage (e.g., 'stage00' or 'Bonus00')."""
    if stage_idx < 20:
        return f"stage{stage_idx:02d}"
    return f"Bonus{stage_idx - 20:02d}"


def get_stage_id_from_name(basename: str) -> int:
    """Derives stage index from a filename (e.g., 'stage01.ppg' -> 1)."""
    try:
        # Strip extension if present
        if "." in basename:
            basename = basename.split(".")[0]

        lower_name = basename.lower()
        if lower_name.startswith("stage"):
            return int(basename[5:7])
        if lower_name.startswith("bonus"):
            bonus_num = int(basename[5:7])
            return 20 + bonus_num
    except (ValueError, IndexError):
        pass
    return -1


def get_stage_palette_bin_name(stage_idx: int) -> str:
    """Returns the filename for the stage's palette binary (e.g., 'bg000.bin' or 'bns000.bin')."""
    if stage_idx < 20:
        return f"bg{stage_idx:02d}0.bin"
    bonus_num = stage_idx - 20
    return f"bns{bonus_num:02d}0.bin"
