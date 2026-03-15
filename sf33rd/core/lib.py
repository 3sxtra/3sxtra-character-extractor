"""A library of utility functions for working with game assets.

This module contains a collection of utility functions for reading and
manipulating the game's asset files.
"""

import struct
import zlib
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from typing import BinaryIO


def read_u8(data: bytes, offset: int) -> int:
    """Reads a big-endian unsigned 8-bit integer from a byte array.

    Args:
        data (bytes): The byte array to read from.
        offset (int): The offset in the byte array to read from.

    Returns:
        int: The unsigned 8-bit integer.
    """
    return cast(int, struct.unpack(">B", data[offset : offset + 1])[0])


def read_s16_be(data: bytes, offset: int) -> int:
    """Reads a big-endian signed 16-bit integer from a byte array.

    Args:
        data (bytes): The byte array to read from.
        offset (int): The offset in the byte array to read from.

    Returns:
        int: The signed 16-bit integer.
    """
    return cast(int, struct.unpack(">h", data[offset : offset + 2])[0])


def read_u16_be(data: bytes, offset: int) -> int:
    """Reads a big-endian unsigned 16-bit integer from a byte array.

    Args:
        data (bytes): The byte array to read from.
        offset (int): The offset in the byte array to read from.

    Returns:
        int: The unsigned 16-bit integer.
    """
    return cast(int, struct.unpack(">H", data[offset : offset + 2])[0])


def read_u32_be(data: bytes, offset: int) -> int:
    """Reads a big-endian unsigned 32-bit integer from a byte array.

    Args:
        data (bytes): The byte array to read from.
        offset (int): The offset in the byte array to read from.

    Returns:
        int: The unsigned 32-bit integer.
    """
    return cast(int, struct.unpack(">I", data[offset : offset + 4])[0])


def decompress(data: bytes, compression_type: int) -> bytes:
    """Decompresses data based on the compression type.

    Args:
        data (bytes): The data to decompress.
        compression_type (int): The compression type.
            2 for zlib, 1 for P6.

    Returns:
        bytes: The decompressed data.
    """
    if compression_type == 2:  # zlib
        return zlib.decompress(data)
    if compression_type == 1:  # P6
        return bytes(decompress_p6_fx(data))
    return data


def decompress_p6_fx(src: bytes, expected_size: int | None = None) -> bytearray:
    """Decompresses P6 FX compressed data.

    P6 is a custom LZ77-based compression format used in some Capcom games.
    This function is a Python port of the original C decompression routine.

    Args:
        src (bytes): The compressed data.
        expected_size (int, optional): The expected size of the
            decompressed data. Defaults to None.

    Returns:
        bytearray: The decompressed data.
    """
    dst = bytearray()
    i = 0

    while i < len(src):
        if expected_size and len(dst) >= expected_size:
            break

        if i >= len(src):
            break

        cmd = src[i]
        i += 1

        if cmd < 0x40:
            dst.append(cmd)
        elif cmd < 0x80:
            if i >= len(src):
                break
            dist = ((cmd & 0x3F) >> 2) + 1
            length = (cmd & 3) + 2
            start = len(dst) - dist
            for j in range(length):
                if start + j >= 0 and start + j < len(dst):
                    dst.append(dst[start + j])
        elif cmd < 0xC0:
            if i >= len(src):
                break
            val = ((cmd & 0x3F) << 8) | src[i]
            i += 1
            dist = (val >> 6) + 1
            length = (val & 0x3F) + 2
            start = len(dst) - dist
            for j in range(length):
                if start + j >= 0 and start + j < len(dst):
                    dst.append(dst[start + j])
        else:
            flag = cmd & 0x30
            count = (cmd & 0x0F) + 2
            for _ in range(count):
                if i >= len(src):
                    break
                val = src[i]
                i += 1
                dst.append(flag | (val >> 4))
                dst.append(flag | (val & 0x0F))
    return dst


def decompress_p6_cx(src: bytes, palette: list[int], expected_size: int | None = None) -> bytearray:
    """Decompresses P6 CX compressed data.

    P6 CX is a variation of P6 that is used for palettized images.

    Args:
        src (bytes): The compressed data.
        palette (list): The palette to use for decompression.
        expected_size (int, optional): The expected size of the
            decompressed data. Defaults to None.

    Returns:
        bytearray: The decompressed data.
    """
    dst = bytearray()
    i = 0

    while i < len(src):
        if expected_size and len(dst) >= expected_size:
            break

        if i >= len(src):
            break

        cmd = src[i]
        i += 1

        if cmd < 0x40:
            dst.extend(struct.pack(">H", palette[cmd]))
        elif cmd < 0x80:
            if i >= len(src):
                break
            dist = (((cmd & 0x3F) >> 2) + 1) * 2
            length = (cmd & 3) + 2
            start = len(dst) - dist
            for j in range(length):
                if start + j >= 0 and start + j < len(dst):
                    dst.append(dst[start + j])
        elif cmd < 0xC0:
            if i >= len(src):
                break
            val = ((cmd & 0x3F) << 8) | src[i]
            i += 1
            dist = ((val >> 6) + 1) * 2
            length = (val & 0x3F) + 2
            start = len(dst) - dist
            for j in range(length):
                if start + j >= 0 and start + j < len(dst):
                    dst.append(dst[start + j])
        else:
            flag = cmd & 0x30
            count = (cmd & 0x0F) + 2
            for _ in range(count):
                if i >= len(src):
                    break
                val = src[i]
                i += 1
                dst.extend(struct.pack(">H", palette[flag | (val >> 4)]))
                dst.extend(struct.pack(">H", palette[flag | (val & 0x0F)]))

    if len(dst) % 2 != 0:
        dst.append(0)

    return dst


def swap_endian_u16(value: int) -> int:
    """Swaps the endianness of a 16-bit unsigned integer.

    Args:
        value (int): The 16-bit unsigned integer.

    Returns:
        int: The swapped 16-bit unsigned integer.
    """
    return cast(int, struct.unpack("<H", struct.pack(">H", value))[0])


def swap_endian_u32(value: int) -> int:
    """Swaps the endianness of a 32-bit unsigned integer.

    Args:
        value (int): The 32-bit unsigned integer.

    Returns:
        int: The swapped 32-bit unsigned integer.
    """
    return cast(int, struct.unpack("<I", struct.pack(">I", value))[0])


def read_struct(file: "BinaryIO", struct_class: Any) -> Any:
    """Reads and unpacks a structure from a file.

    Args:
        file (file-like object): The file to read from.
        struct_class (class): The class representing the structure. It must
            have a `size` attribute and a `from_bytes` class method.

    Returns:
        object: An instance of the struct_class with the
            unpacked data, or None if the end of the file is reached.
    """
    data = file.read(struct_class.size)
    if not data:
        return None
    return struct_class.from_bytes(data)


def argb1555_to_rgb888(value: int) -> tuple[int, int, int]:
    """Converts a big-endian ARGB1555 color value to an RGB888 tuple.

    The ARGB1555 format is a 16-bit color format where the most significant
    bit is alpha, and the remaining 15 bits are split into 5 bits for red,
    5 bits for green, and 5 bits for blue.

    Args:
        value (int): The big-endian ARGB1555 color value.

    Returns:
        tuple: An (r, g, b) tuple, where each component is an 8-bit integer.
    """
    # The value is already in big-endian, so we don't need to swap it.

    # Extract 5-bit color components
    r = (value >> 10) & 0x1F
    g = (value >> 5) & 0x1F
    b = value & 0x1F

    # Scale from 5-bit (0-31) to 8-bit (0-255)
    # This is a more accurate scaling method than (c * 255) // 31
    r = (r << 3) | (r >> 2)
    g = (g << 3) | (g >> 2)
    b = (b << 3) | (b >> 2)

    return (r, g, b)
