"""Virtual ColorRAM module.

Provides a 512-slot ColorRAM mirror matching the game's palette system.
This allows universal effect palette selection without character-specific hardcoding.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sf33rd.lib.palette import CharacterPalette


# parts_colcd_table from eff01.c - maps animation parts_colcd to color codes
# 0x2000 bit = ABSOLUTE slot (use directly), otherwise RELATIVE (add to base)
PARTS_COLCD_TABLE = [
    0x2000,  # 0: absolute slot 0 (inherit master)
    0x0,  # 1: relative offset 0
    0x6,  # 2: relative offset 6  -> style 21
    0x2000,  # 3: absolute slot 0
    0x4,  # 4: relative offset 4  -> style 19
    0x2020,  # 5: absolute slot 32
    0x4,  # 6: relative offset 4
    0x4,  # 7: relative offset 4
    0x0,  # 8: relative offset 0
    0x6,  # 9: relative offset 6
    0x5,  # 10: relative offset 5 -> style 20
    0x4,  # 11: relative offset 4
    0x203C,  # 12: absolute slot 60
    0x202A,  # 13: absolute slot 42
]


class VirtualColorRAM:
    """512-slot ColorRAM mirror matching the game's palette architecture.

    Slot layout for P1 (base=0), P2 (base=16):
    - Slot 0/16: Main character (style based on costume 0-5)
    - Slots 1-6 / 17-22: Effect palettes (styles 16-21)
    - Slot 7/23: Hitmark (special)
    - Slot 8/24: Character variant
    - Slots 9-14 / 25-30: Variant effects
    - Slots 502-505 / 506-509: 256-color effect block (styles 22-25)
    - Slots 32-299: Stage palettes (absolute references)
    - Slots 300-501: Global effect palettes
    """

    def __init__(self):
        # 512 slots, each with 64 RGB tuples
        self.slots: list[list[tuple[int, int, int]] | None] = [None] * 512
        # Track which slots are loaded
        self.loaded_slots: set[int] = set()

    def load_character_palette(self, char_pal: CharacterPalette, player_id: int = 0, costume_style: int = 0) -> None:
        """Load character palette into correct ColorRAM slots.

        Args:
            char_pal: CharacterPalette object with all 28 styles
            player_id: 0 for P1, 1 for P2
            costume_style: Costume selection (0-5)
        """
        base = player_id * 16

        # Slot 0/16: Main character palette (costume-selected style)
        self.slots[base] = char_pal.get_style_rgb_list(costume_style)
        self.loaded_slots.add(base)

        # Slots 1-6 / 17-22: Effect palettes (styles 16-21)
        for i in range(6):
            slot = base + 1 + i
            self.slots[slot] = char_pal.get_style_rgb_list(16 + i)
            self.loaded_slots.add(slot)

        # Slot 8/24: Character variant (same style for now)
        self.slots[base + 8] = char_pal.get_style_rgb_list(costume_style)
        self.loaded_slots.add(base + 8)

        # Slots 9-14 / 25-30: Variant effect palettes
        for i in range(6):
            slot = base + 9 + i
            self.slots[slot] = char_pal.get_style_rgb_list(16 + i)
            self.loaded_slots.add(slot)

        # Slots 502-505 (P1) or 506-509 (P2): 256-color effect block
        effect_base = 502 if player_id == 0 else 506
        for i in range(4):
            if 22 + i < char_pal.num_styles:
                slot = effect_base + i
                self.slots[slot] = char_pal.get_style_rgb_list(22 + i)
                self.loaded_slots.add(slot)

    def load_character_palette_with_effect(
        self, char_pal: CharacterPalette, player_id: int = 0, costume_style: int = 0, effect_type: str | None = None
    ) -> None:
        """Load character palette with optional effect transformation.

        This method extends load_character_palette by applying an effect
        transformation (like grey tint, burned, frozen) to the main palette slot.

        Args:
            char_pal: CharacterPalette object with all 28 styles
            player_id: 0 for P1, 1 for P2
            costume_style: Costume selection (0-6 for LP-EX)
            effect_type: Optional effect ("grey_tint", "burned", "frozen", "sa_parry")
        """
        base = player_id * 16

        # Apply effect transformation if requested
        if effect_type:
            # Get transformed colors
            transformed = char_pal.get_style_with_effect(costume_style, effect_type)
            self.slots[base] = [c.to_rgb_tuple() for c in transformed]
        else:
            self.slots[base] = char_pal.get_style_rgb_list(costume_style)

        self.loaded_slots.add(base)

        # Load remaining effect slots normally (styles 16-21)
        for i in range(6):
            slot = base + 1 + i
            self.slots[slot] = char_pal.get_style_rgb_list(16 + i)
            self.loaded_slots.add(slot)

        # Slot 8/24: Character variant
        if effect_type:
            transformed = char_pal.get_style_with_effect(costume_style, effect_type)
            self.slots[base + 8] = [c.to_rgb_tuple() for c in transformed]
        else:
            self.slots[base + 8] = char_pal.get_style_rgb_list(costume_style)
        self.loaded_slots.add(base + 8)

        # Slots 9-14 / 25-30: Variant effect palettes
        for i in range(6):
            slot = base + 9 + i
            self.slots[slot] = char_pal.get_style_rgb_list(16 + i)
            self.loaded_slots.add(slot)

        # Slots 502-505 (P1) or 506-509 (P2): 256-color effect block
        effect_base = 502 if player_id == 0 else 506
        for i in range(4):
            if 22 + i < char_pal.num_styles:
                slot = effect_base + i
                self.slots[slot] = char_pal.get_style_rgb_list(22 + i)
                self.loaded_slots.add(slot)

    def get_color(self, slot: int, index: int) -> tuple[int, int, int]:
        """Get color from a specific slot and index.

        Args:
            slot: ColorRAM slot (0-511)
            index: Color index within slot (0-63)

        Returns:
            RGB tuple, or magenta (255, 0, 255) if slot not loaded
        """
        if slot < 0 or slot >= 512:
            return (255, 0, 255)  # Out of bounds

        palette = self.slots[slot]
        if palette is None:
            return (255, 0, 255)  # Slot not loaded

        if index < 0 or index >= len(palette):
            return (255, 0, 255)  # Index out of bounds

        return palette[index]

    def get_slot_palette(self, slot: int) -> list[tuple[int, int, int]] | None:
        """Get the full 64-color palette from a slot.

        Args:
            slot: ColorRAM slot (0-511)

        Returns:
            List of 64 RGB tuples, or None if not loaded
        """
        if 0 <= slot < 512:
            return self.slots[slot]
        return None

    def get_256_color_effect_palette(self, player_id: int = 0) -> list[tuple[int, int, int]]:
        """Get the combined 256-color effect palette (styles 22-25).

        Args:
            player_id: 0 for P1, 1 for P2

        Returns:
            List of 256 RGB tuples (or fewer if not all slots loaded)
        """
        effect_base = 502 if player_id == 0 else 506
        result: list[tuple[int, int, int]] = []

        for i in range(4):
            slot = effect_base + i
            palette = self.slots[slot]
            if palette is not None:
                result.extend(palette)
            else:
                # Pad with black if slot not loaded
                result.extend([(0, 0, 0)] * 64)

        return result

    def resolve_parts_colcd(self, parts_colcd: int, base_slot: int = 0) -> tuple[int, bool]:
        """Resolve parts_colcd to actual ColorRAM slot.

        Uses parts_colcd_table logic from the game engine.

        Args:
            parts_colcd: Value from animation data (0-13)
            base_slot: Character's base ColorRAM slot (0 for P1, 16 for P2)

        Returns:
            Tuple of (slot_index, is_absolute)
            - slot_index: The ColorRAM slot to use
            - is_absolute: True if this is an absolute global slot
        """
        if parts_colcd <= 0 or parts_colcd >= len(PARTS_COLCD_TABLE):
            # Default: use base character slot
            return (base_slot, False)

        col_code = PARTS_COLCD_TABLE[parts_colcd]
        is_absolute = bool(col_code & 0x2000)
        offset = col_code & 0x1FFF

        if is_absolute:
            return (offset, True)
        return (base_slot + offset, False)
