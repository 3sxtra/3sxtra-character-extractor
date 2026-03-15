"""
Swizzling utilities for Dreamcast texture formats.
Provides functions to swizzle and unswizzle textures using Morton codes or Dreamcast table-based methods.
"""


def morton_to_xy(morton):
    """Decodes a Morton code into x and y coordinates.

    Args:
        morton (int): The Morton code.

    Returns:
        tuple: A tuple containing the x and y coordinates.
    """
    x = 0
    y = 0
    for i in range(16):  # Supports up to 32-bit index
        if (morton >> (2 * i)) & 1:
            x |= 1 << i
        if (morton >> (2 * i + 1)) & 1:
            y |= 1 << i
    return x, y


def xy_to_morton(x, y):
    """Encodes x and y coordinates into a Morton code.

    Args:
        x (int): The x-coordinate.
        y (int): The y-coordinate.

    Returns:
        int: The Morton code.
    """
    morton = 0
    for i in range(16):
        if (x >> i) & 1:
            morton |= 1 << (2 * i)
        if (y >> i) & 1:
            morton |= 1 << (2 * i + 1)
    return morton


def generate_dctex_linear():
    """Generates the Dreamcast texture swizzling table.

    This table is used to convert linear texture coordinates to the swizzled
    format used by the Dreamcast's PowerVR GPU for small textures (<= 32x32).
    This implementation is based on the `ppgMakeConvTableTexDC` function from
    the game's source code.

    Returns:
        list: A list of 1024 integers representing the swizzling table.
    """
    seed = [
        0x0000,
        0x0002,
        0x0008,
        0x000A,
        0x0020,
        0x0022,
        0x0028,
        0x002A,
        0x0080,
        0x0082,
        0x0088,
        0x008A,
        0x00A0,
        0x00A2,
        0x00A8,
        0x00AA,
        0x0200,
        0x0202,
        0x0208,
        0x020A,
        0x0220,
        0x0222,
        0x0228,
        0x022A,
        0x0280,
        0x0282,
        0x0288,
        0x028A,
        0x02A0,
        0x02A2,
        0x02A8,
        0x02AA,
    ]

    seed_add = [
        0x0000,
        0x0004,
        0x0010,
        0x0014,
        0x0040,
        0x0044,
        0x0050,
        0x0054,
        0x0100,
        0x0104,
        0x0110,
        0x0114,
        0x0140,
        0x0144,
        0x0150,
        0x0154,
    ]

    dctex_linear = [0] * 1024

    for i in range(16):
        for j in range(32):
            dctex_linear[j + i * 64] = seed[j] + seed_add[i]
        for j in range(32):
            dctex_linear[j + (i * 64 + 32)] = dctex_linear[j + i * 64] + 1

    return dctex_linear


DCTEX_LINEAR = generate_dctex_linear()


def unswizzle_dreamcast(data, width, height, bitdepth=1):
    """Unswizzles Dreamcast texture data.

    For small textures (<= 32x32), this function uses the table-based
    unswizzling method. For larger textures, it falls back to standard
    Morton unswizzling.

    Args:
        data (bytes): The swizzled texture data.
        width (int): The width of the texture.
        height (int): The height of the texture.
        bitdepth (int, optional): The number of bytes per pixel. Defaults to 1.

    Returns:
        bytearray: The unswizzled (linear) texture data.
    """
    if width <= 32 and height <= 32 and bitdepth >= 1:
        dst = bytearray(len(data))
        for y in range(height):
            for x in range(width):
                linear_idx = y * width + x
                if linear_idx >= 1024:
                    continue

                swizzled_idx = DCTEX_LINEAR[linear_idx]
                if swizzled_idx * bitdepth >= len(data):
                    continue

                src_idx = swizzled_idx * bitdepth
                dst_idx = linear_idx * bitdepth

                if src_idx + bitdepth <= len(data) and dst_idx + bitdepth <= len(dst):
                    dst[dst_idx : dst_idx + bitdepth] = data[src_idx : src_idx + bitdepth]
        return dst

    # For large textures or 4-bit, use standard Morton
    return unswizzle_morton(data, width, height, bitdepth)


def unswizzle_morton(data, width, height, bytes_per_pixel=1):
    """Unswizzles Morton-encoded data to linear order.

    Args:
        data (bytes): The Morton-encoded data.
        width (int): The width of the texture.
        height (int): The height of the texture.
        bytes_per_pixel (int, optional): The number of bytes per pixel.
            Defaults to 1.

    Returns:
        bytearray: The unswizzled (linear) data.
    """
    if bytes_per_pixel == 0:  # 4-bit packed
        return unswizzle_morton(data, width // 2, height, 1)

    if len(data) < width * height * bytes_per_pixel:
        return data

    unswizzled = bytearray(len(data))
    total_pixels = width * height

    for i in range(total_pixels):
        x, y = morton_to_xy(i)
        if x < width and y < height:
            src_idx = i * bytes_per_pixel
            dst_idx = (y * width + x) * bytes_per_pixel

            if bytes_per_pixel == 1:
                unswizzled[dst_idx] = data[src_idx]
            elif bytes_per_pixel == 2:
                unswizzled[dst_idx] = data[src_idx]
                unswizzled[dst_idx + 1] = data[src_idx + 1]
            elif bytes_per_pixel == 4:
                unswizzled[dst_idx] = data[src_idx]
                unswizzled[dst_idx + 1] = data[src_idx + 1]
                unswizzled[dst_idx + 2] = data[src_idx + 2]
                unswizzled[dst_idx + 3] = data[src_idx + 3]
            else:
                unswizzled[dst_idx : dst_idx + bytes_per_pixel] = data[src_idx : src_idx + bytes_per_pixel]

    return unswizzled


def swizzle_dreamcast(data, width, height, bitdepth=1):
    """Swizzles data into the Dreamcast texture format.

    For small textures (<= 32x32), this function uses the table-based
    swizzling method. For larger textures, it falls back to standard
    Morton swizzling.

    Args:
        data (bytes): The linear texture data.
        width (int): The width of the texture.
        height (int): The height of the texture.
        bitdepth (int, optional): The number of bytes per pixel. Defaults to 1.

    Returns:
        bytearray: The swizzled texture data.
    """
    if width <= 32 and height <= 32 and bitdepth >= 1:
        dst = bytearray(len(data))
        for y in range(height):
            for x in range(width):
                linear_idx = y * width + x
                if linear_idx >= 1024:
                    continue

                swizzled_idx = DCTEX_LINEAR[linear_idx]
                # Check if swizzled index is within bounds of data/dst?
                # swizzled_idx is index into flattened array.
                # Here we map linear -> swizzled.
                # dst_idx = swizzled_idx * bitdepth.

                src_idx = linear_idx * bitdepth
                dst_idx = swizzled_idx * bitdepth

                if swizzled_idx * bitdepth >= len(dst) or src_idx + bitdepth > len(data):
                    continue

                if dst_idx + bitdepth <= len(dst):
                    dst[dst_idx : dst_idx + bitdepth] = data[src_idx : src_idx + bitdepth]
        return dst

    return swizzle_morton(data, width, height, bitdepth)


def swizzle_morton(data, width, height, bytes_per_pixel=1):
    """Swizzles linear data to Morton order.

    Args:
        data (bytes): The linear data.
        width (int): The width of the texture.
        height (int): The height of the texture.
        bytes_per_pixel (int, optional): The number of bytes per pixel.
            Defaults to 1.

    Returns:
        bytearray: The Morton-encoded data.
    """
    if bytes_per_pixel == 0:  # 4-bit packed
        return swizzle_morton(data, width // 2, height, 1)

    if len(data) < width * height * bytes_per_pixel:
        return data

    swizzled = bytearray(len(data))
    total_pixels = width * height

    for i in range(total_pixels):
        x, y = morton_to_xy(i)
        if x < width and y < height:
            src_idx = (y * width + x) * bytes_per_pixel
            dst_idx = i * bytes_per_pixel

            if bytes_per_pixel == 1:
                swizzled[dst_idx] = data[src_idx]
            elif bytes_per_pixel == 2:
                swizzled[dst_idx] = data[src_idx]
                swizzled[dst_idx + 1] = data[src_idx + 1]
            elif bytes_per_pixel == 4:
                swizzled[dst_idx] = data[src_idx]
                swizzled[dst_idx + 1] = data[src_idx + 1]
                swizzled[dst_idx + 2] = data[src_idx + 2]
                swizzled[dst_idx + 3] = data[src_idx + 3]
            else:
                swizzled[dst_idx : dst_idx + bytes_per_pixel] = data[src_idx : src_idx + bytes_per_pixel]

    return swizzled
