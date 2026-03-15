"""
Generate effect palettes matching PalMod's secondary palette effects.

This module provides utilities for generating effect palette variations
that match the game's behavior for states like burned, frozen, and faded.

Reference: PalMod GameDef.h paletteBuddy_GreyTint_* definitions
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sf33rd.lib.palette_constants import (
    BURNED_BLUE_FACTOR,
    BURNED_GREEN_FACTOR,
    BURNED_RED_BOOST,
    BURNED_RED_OFFSET,
    FROZEN_BLUE_BOOST,
    FROZEN_BLUE_OFFSET,
    FROZEN_GREEN_FACTOR,
    FROZEN_GREEN_OFFSET,
    FROZEN_RED_FACTOR,
    FROZEN_RED_OFFSET,
    GREY_TINT_BLEND_FACTOR,
    GREY_TINT_COLOR,
)

if TYPE_CHECKING:
    from sf33rd.lib.palette import Color


def generate_grey_tint_palette(base_colors: list[Color], blend_factor: float = GREY_TINT_BLEND_FACTOR) -> list[Color]:
    """Generate grey-tinted version of a palette.

    Matches PalMod's MOD_BLEND operation with rgb(124,124,124).
    Used for hit stun, freeze frames, faded states, etc.

    Args:
        base_colors: Source palette colors
        blend_factor: Blend amount (0.0 = original, 1.0 = full grey)

    Returns:
        Grey-tinted palette colors
    """
    # pylint: disable=import-outside-toplevel
    from sf33rd.lib.palette import Color  # Runtime import to avoid cycle

    result: list[Color] = []
    for color in base_colors:
        if color.a == 0:  # Keep transparent colors transparent
            result.append(Color(0, 0, 0, 0))
            continue

        r = int(color.r * (1 - blend_factor) + GREY_TINT_COLOR[0] * blend_factor)
        g = int(color.g * (1 - blend_factor) + GREY_TINT_COLOR[1] * blend_factor)
        b = int(color.b * (1 - blend_factor) + GREY_TINT_COLOR[2] * blend_factor)
        result.append(Color(r, g, b, 255))
    return result


def generate_burned_palette(base_colors: list[Color]) -> list[Color]:
    """Generate burned/red parry palette effect.

    Applies a red tint to simulate fire damage or red parry state.
    The transformation increases red channel while reducing green and blue.

    Args:
        base_colors: Source palette colors

    Returns:
        Red-tinted palette colors for burned state
    """
    # pylint: disable=import-outside-toplevel
    from sf33rd.lib.palette import Color  # Runtime import to avoid cycle

    result: list[Color] = []
    for color in base_colors:
        if color.a == 0:
            result.append(Color(0, 0, 0, 0))
            continue

        # Boost red, reduce green/blue to create fire effect
        r = min(255, int(color.r * BURNED_RED_BOOST + BURNED_RED_OFFSET))
        g = int(color.g * BURNED_GREEN_FACTOR)
        b = int(color.b * BURNED_BLUE_FACTOR)
        result.append(Color(r, g, b, 255))
    return result


def generate_frozen_palette(base_colors: list[Color]) -> list[Color]:
    """Generate frozen/super flash palette effect.

    Applies a blue/white tint to simulate ice/freeze or super flash state.
    The transformation shifts colors toward blue and increases brightness.

    Args:
        base_colors: Source palette colors

    Returns:
        Blue-tinted palette colors for frozen state
    """
    # pylint: disable=import-outside-toplevel
    from sf33rd.lib.palette import Color  # Runtime import to avoid cycle

    result: list[Color] = []
    for color in base_colors:
        if color.a == 0:
            result.append(Color(0, 0, 0, 0))
            continue

        # Shift toward blue/white for ice effect
        r = int(color.r * FROZEN_RED_FACTOR + FROZEN_RED_OFFSET)
        g = int(color.g * FROZEN_GREEN_FACTOR + FROZEN_GREEN_OFFSET)
        b = min(255, int(color.b * FROZEN_BLUE_BOOST + FROZEN_BLUE_OFFSET))
        result.append(Color(min(255, r), min(255, g), b, 255))
    return result


def generate_sa_parry_palette(base_colors: list[Color]) -> list[Color]:
    """Generate super art/parry palette effect.

    Applies a bright flash effect used during super art activation
    and successful parry states.

    Args:
        base_colors: Source palette colors

    Returns:
        Brightened palette colors for SA/parry state
    """
    # pylint: disable=import-outside-toplevel
    from sf33rd.lib.palette import Color  # Runtime import to avoid cycle

    result: list[Color] = []
    for color in base_colors:
        if color.a == 0:
            result.append(Color(0, 0, 0, 0))
            continue

        # Brighten all channels for flash effect
        brightness_boost = 1.3
        r = min(255, int(color.r * brightness_boost + 30))
        g = min(255, int(color.g * brightness_boost + 30))
        b = min(255, int(color.b * brightness_boost + 30))
        result.append(Color(r, g, b, 255))
    return result


def apply_effect_to_palette(base_colors: list[Color], effect_type: str | None) -> list[Color]:
    """Apply an effect transformation to palette colors.

    Args:
        base_colors: Source palette colors
        effect_type: One of "grey_tint", "burned", "frozen", "sa_parry", or None

    Returns:
        Transformed palette colors (or original if effect_type is None)
    """
    if effect_type is None:
        return base_colors

    if effect_type == "grey_tint":
        return generate_grey_tint_palette(base_colors)
    if effect_type == "burned":
        return generate_burned_palette(base_colors)
    if effect_type == "frozen":
        return generate_frozen_palette(base_colors)
    if effect_type == "sa_parry":
        return generate_sa_parry_palette(base_colors)

    return base_colors
