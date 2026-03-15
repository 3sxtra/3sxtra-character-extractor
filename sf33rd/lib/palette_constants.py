"""
SF3:3rd Strike palette constants matching PalMod conventions.

Reference: https://github.com/Preppy/PalMod/blob/master/palmod/Game/SFIII3_A_DEF.h

This module provides standardized naming for character palette styles,
matching the conventions used by PalMod for consistency and familiarity.
"""

from enum import IntEnum
from typing import NamedTuple


class PaletteStyle(IntEnum):
    """Character palette style indices matching game's COL structure.

    The game's color3rd.c defines:
        typedef struct { u16 col[2][28][64]; } COL;

    Styles 0-6 are the main player-selectable costume colors.
    Styles 7-15 are reserved/additional variations.
    Styles 16-21 are character effect palettes.
    Styles 22-25 are the 256-color effect block.
    Styles 26-27 are special palettes (Gill effects, etc.).
    """

    # Main costume colors (player-selectable)
    LP = 0  # Light Punch
    MP = 1  # Medium Punch
    HP = 2  # Heavy Punch
    LK = 3  # Light Kick
    MK = 4  # Medium Kick
    HK = 5  # Heavy Kick
    EX = 6  # EX/Super color

    # Reserved/additional variations (7-15)
    VARIANT_1 = 7
    VARIANT_2 = 8
    VARIANT_3 = 9
    VARIANT_4 = 10
    VARIANT_5 = 11
    VARIANT_6 = 12
    VARIANT_7 = 13
    VARIANT_8 = 14
    VARIANT_9 = 15

    # Effect palettes (16-21)
    EFFECT_1 = 16  # Effect palette 1 (projectiles, etc.)
    EFFECT_2 = 17  # Effect palette 2
    EFFECT_3 = 18  # Burned/Red Parry state
    EFFECT_4 = 19  # Frozen/Super Flash state
    EFFECT_5 = 20  # SA Animation/Parry
    EFFECT_6 = 21  # SA Trail

    # 256-color effect block (22-25)
    EFFECT_256_1 = 22
    EFFECT_256_2 = 23
    EFFECT_256_3 = 24
    EFFECT_256_4 = 25

    # Special palettes (26-27)
    SPECIAL_1 = 26  # Gill resurrection, metamorphosis, etc.
    SPECIAL_2 = 27


# User-friendly display names for UI dropdowns
STYLE_DISPLAY_NAMES: dict[PaletteStyle, str] = {
    PaletteStyle.LP: "LP (Light Punch)",
    PaletteStyle.MP: "MP (Medium Punch)",
    PaletteStyle.HP: "HP (Heavy Punch)",
    PaletteStyle.LK: "LK (Light Kick)",
    PaletteStyle.MK: "MK (Medium Kick)",
    PaletteStyle.HK: "HK (Heavy Kick)",
    PaletteStyle.EX: "EX (Super Color)",
}

# Short button labels for compact UI (matching PalMod's DEF_BUTTONLABEL7_SF3)
BUTTON_LABELS: list[str] = ["LP", "MP", "HP", "LK", "MK", "HK", "EX"]

# Map from button label to style index
BUTTON_TO_STYLE: dict[str, PaletteStyle] = {
    "LP": PaletteStyle.LP,
    "MP": PaletteStyle.MP,
    "HP": PaletteStyle.HP,
    "LK": PaletteStyle.LK,
    "MK": PaletteStyle.MK,
    "HK": PaletteStyle.HK,
    "EX": PaletteStyle.EX,
}


class EffectPaletteInfo(NamedTuple):
    """Describes a secondary/effect palette slot."""

    name: str
    style_index: int  # Absolute style index in the COL structure
    description: str


# Effect palettes matching PalMod's SFIII3_A_*_Support_PALETTES structure
# These are the secondary palettes used for special states
EFFECT_PALETTES: dict[str, EffectPaletteInfo] = {
    "ex_attack_1": EffectPaletteInfo("EX Attack (1)", 16, "First EX move trail effect"),
    "ex_attack_2": EffectPaletteInfo("EX Attack (2)", 17, "Second EX move trail effect"),
    "burned": EffectPaletteInfo("Burned/Red Parry", 18, "Fire damage and red parry state"),
    "frozen": EffectPaletteInfo("Frozen/Super Flash", 19, "Ice/freeze and super activation state"),
    "sa_parry": EffectPaletteInfo("SA Animation/Parry", 20, "Super art and parry effect"),
    "sa_trail_1": EffectPaletteInfo("SA Trail 1", 21, "Super art motion trail 1"),
    "sa_trail_2": EffectPaletteInfo("SA Trail 2", 22, "Super art motion trail 2"),
    "sa_trail_3": EffectPaletteInfo("SA Trail 3", 23, "Super art motion trail 3"),
}

# Effect state display names for UI dropdown
EFFECT_STATE_NAMES: list[str] = [
    "Normal",
    "Burned/Red Parry",
    "Frozen/Super Flash",
    "Grey Tint (Faded)",
    "SA Animation/Parry",
]

# Map effect state name to internal effect type
EFFECT_STATE_TO_TYPE: dict[str, str | None] = {
    "Normal": None,
    "Burned/Red Parry": "burned",
    "Frozen/Super Flash": "frozen",
    "Grey Tint (Faded)": "grey_tint",
    "SA Animation/Parry": "sa_parry",
}

# Grey tint blend color for faded effects
# From PalMod GameDef.h: "3S uses a blend of rgb(124,124,124) to achieve
# the Faded effects"
GREY_TINT_COLOR: tuple[int, int, int] = (124, 124, 124)
GREY_TINT_BLEND_FACTOR: float = 0.5  # 50% blend with grey

# Burned effect color shift parameters
BURNED_RED_BOOST: float = 1.3
BURNED_RED_OFFSET: int = 40
BURNED_GREEN_FACTOR: float = 0.6
BURNED_BLUE_FACTOR: float = 0.5

# Frozen effect color shift parameters
FROZEN_RED_FACTOR: float = 0.7
FROZEN_RED_OFFSET: int = 50
FROZEN_GREEN_FACTOR: float = 0.8
FROZEN_GREEN_OFFSET: int = 60
FROZEN_BLUE_BOOST: float = 1.2
FROZEN_BLUE_OFFSET: int = 80
