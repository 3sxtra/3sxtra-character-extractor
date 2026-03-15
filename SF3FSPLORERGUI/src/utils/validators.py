#!/usr/bin/env python3
"""
Input validation utilities
"""

from pathlib import Path

from sf33rd.constants import (
    AUDIO_BIT_DEPTHS,
    AUDIO_SAMPLE_RATES,
    SUPPORTED_AUDIO_EXTENSIONS,
    SUPPORTED_IMAGE_EXTENSIONS,
)


def validate_file_path(path: str) -> bool:
    """
    Validate if a file path exists and is accessible

    Args:
        path: File path to validate

    Returns:
        True if valid file path, False otherwise
    """
    if not path or not isinstance(path, str):
        return False

    try:
        path_obj = Path(path)
        return path_obj.is_file() and path_obj.exists()
    except OSError:
        return False


def validate_directory_path(path: str) -> bool:
    """
    Validate if a directory path exists and is accessible

    Args:
        path: Directory path to validate

    Returns:
        True if valid directory path, False otherwise
    """
    if not path or not isinstance(path, str):
        return False

    try:
        path_obj = Path(path)
        return path_obj.is_dir() and path_obj.exists()
    except OSError:
        return False


def validate_audio_format(format_name: str) -> bool:
    """
    Validate if an audio format is supported

    Args:
        format_name: Audio format name (with or without dot)

    Returns:
        True if supported format, False otherwise
    """
    if not format_name or not isinstance(format_name, str):
        return False

    format_name = format_name.lower()

    # Add dot if not present
    if not format_name.startswith("."):
        format_name = "." + format_name

    return format_name in SUPPORTED_AUDIO_EXTENSIONS


def validate_image_format(format_name: str) -> bool:
    """
    Validate if an image format is supported

    Args:
        format_name: Image format name (with or without dot)

    Returns:
        True if supported format, False otherwise
    """
    if not format_name or not isinstance(format_name, str):
        return False

    format_name = format_name.lower()

    # Add dot if not present
    if not format_name.startswith("."):
        format_name = "." + format_name

    return format_name in SUPPORTED_IMAGE_EXTENSIONS


def validate_numeric_range(value: int | float, min_val: int | float, max_val: int | float) -> bool:
    """
    Validate if a numeric value is within a specified range

    Args:
        value: Value to validate
        min_val: Minimum allowed value
        max_val: Maximum allowed value

    Returns:
        True if value is within range, False otherwise
    """
    try:
        num_value = float(value)
        return min_val <= num_value <= max_val
    except (ValueError, TypeError):
        return False


def validate_window_size(width: int, height: int) -> bool:
    """
    Validate window dimensions

    Args:
        width: Window width
        height: Window height

    Returns:
        True if valid dimensions, False otherwise
    """
    return validate_numeric_range(width, 100, 3840) and validate_numeric_range(height, 100, 2160)


def validate_sample_rate(sample_rate: int) -> bool:
    """
    Validate audio sample rate

    Args:
        sample_rate: Audio sample rate in Hz

    Returns:
        True if valid sample rate, False otherwise
    """
    return sample_rate in AUDIO_SAMPLE_RATES


def validate_bit_depth(bit_depth: int) -> bool:
    """
    Validate audio bit depth

    Args:
        bit_depth: Audio bit depth

    Returns:
        True if valid bit depth, False otherwise
    """
    return bit_depth in AUDIO_BIT_DEPTHS


def validate_volume_level(volume: int) -> bool:
    """
    Validate audio volume level

    Args:
        volume: Volume level (0-100)

    Returns:
        True if valid volume level, False otherwise
    """
    return validate_numeric_range(volume, 0, 100)
