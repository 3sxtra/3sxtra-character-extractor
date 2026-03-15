"""
This file contains the data model for the game's assets, based on the information provided in
the Master Asset File List.
"""

import struct


class TEX:
    """Represents a TEX data block, which contains sprite dimensions and pixel data.

    The TEX format is not fully understood, but it is known to contain the
    width and height of the sprite, as well as the raw pixel data.

    Attributes:
        width (int): The width of the sprite in pixels.
        height (int): The height of the sprite in pixels.
        data (bytes): The raw pixel data of the sprite.
    """

    # pylint: disable=too-few-public-methods

    def __init__(self, data: bytes) -> None:
        """Initializes the TEX object from a byte string.

        Args:
            data (bytes): The byte string representing the TEX data block.
        """
        # The TEX format is not fully understood, but we know it contains width and height.
        # Based on the C code, the width and height are encoded in a single byte.
        # The lower 4 bits are the width, and the upper 4 bits are the height.
        # Each value is a multiple of 8.
        wh = data[0]
        self.width = (wh & 0x0F) * 8
        self.height = ((wh >> 4) & 0x0F) * 8
        self.data = data[1:]


class PPLFileHeader:
    """Represents the header of a .ppl file.

    The .ppl file format is used for storing palettes.

    Attributes:
        magic (bytes): The magic number of the file, which should be b'PPL\x00'.
        pal_type (int): The type of the palette.
        unknown1 (int): An unknown value.
        num_colors (int): The number of colors in the palette.
        compress (int): The compression type.
        unknown2 (int): An unknown value.
    """

    # pylint: disable=too-few-public-methods

    def __init__(self, data: bytes) -> None:
        """Initializes the PPLFileHeader object from a byte string.

        Args:
            data (bytes): The byte string representing the PPL file header.
        """
        self.magic, self.pal_type, self.unknown1, self.num_colors, self.compress, self.unknown2 = struct.unpack(
            ">4sBBHHH", data
        )


class PPGFileHeader:
    """Represents the header of a .ppg file.

    The .ppg file format is used for storing graphics, such as stage backgrounds.

    Attributes:
        magic (bytes): The magic number of the file, which should be b'PPG\x00'.
        file_size (int): The size of the file in bytes.
        width (int): The width of the image in pixels.
        height (int): The height of the image in pixels.
        compress (int): The compression type.
        pixel (int): The pixel format.
        form_argb (int): The ARGB format.
        trans_nums (int): The number of transparent colors.
    """

    # pylint: disable=too-few-public-methods

    def __init__(self, data: bytes) -> None:
        """Initializes the PPGFileHeader object from a byte string.

        Args:
            data (bytes): The byte string representing the PPG file header.
        """
        # Based on structs.h:
        # u32 magic; u32 fileSize; u8 width; u8 height; u8 compress; u8 pixel;
        # u16 formARGB; u16 transNums;
        (
            self.magic,
            self.file_size,
            self.width,
            self.height,
            self.compress,
            self.pixel,
            self.form_argb,
            self.trans_nums,
        ) = struct.unpack(">4sIBBBBHH", data)


class PPXFileHeader:
    """Represents the header of a .ppx file.

    The .ppx file format is a container for other file types.

    Attributes:
        magic (bytes): The magic number of the file, which should be b'PPX\x00'.
        file_size (int): The size of the file in bytes.
        id (int): The ID of the file.
        compress (int): The compression type.
        free (int): A free value.
        exp_size (int): The size of the file when expanded.
    """

    # pylint: disable=too-few-public-methods

    def __init__(self, data: bytes) -> None:
        """Initializes the PPXFileHeader object from a byte string.

        Args:
            data (bytes): The byte string representing the PPX file header.
        """
        # Based on structs.h:
        # u32 magic; u32 fileSize; u16 id; u8 compress; u8 free; u32 expSize;
        self.magic, self.file_size, self.id, self.compress, self.free, self.exp_size = struct.unpack(">4sIHBBI", data)


character_data = {
    # Offsets from texgrpdat in texgroup.c:
    # - to_tex: offset to texture data
    # - to_chd: offset to CharInitData header (25 pointers to animation tables)
    # - num_of_1st: base frame number for this character (GBIX -> local = GBIX - num_of_1st)
    "Gill": {
        "tex": "pl00.bin",
        "col": "pl00pl.bin",
        "anim": "pl00plm.bin",
        "to_tex": 210820,
        "to_chd": 0x2CF158,
        "num_of_1st": 0,
    },
    "Alex": {
        "tex": "pl01.bin",
        "col": "pl01pl.bin",
        "anim": "pl01plm.bin",
        "to_tex": 116432,
        "to_chd": 0x24EDE0,
        "num_of_1st": 1568,
    },
    "Ryu": {
        "tex": "pl02.bin",
        "col": "pl02pl.bin",
        "anim": "pl02plm.bin",
        "to_tex": 72828,
        "to_chd": 0x178F38,
        "num_of_1st": 2592,
    },
    "Yun": {
        "tex": "pl03.bin",
        "col": "pl03pl.bin",
        "anim": "pl03plm.bin",
        "to_tex": 114816,
        "to_chd": 0x1FAA0C,
        "num_of_1st": 3552,
    },
    "Dudley": {
        "tex": "pl04.bin",
        "col": "pl04pl.bin",
        "anim": "pl04plm.bin",
        "to_tex": 110728,
        "to_chd": 0x1E1D54,
        "num_of_1st": 4992,
    },
    "Necro": {
        "tex": "pl05.bin",
        "col": "pl05pl.bin",
        "anim": "pl05plm.bin",
        "to_tex": 116636,
        "to_chd": 0x2BCE28,
        "num_of_1st": 6144,
    },
    "Hugo": {
        "tex": "pl06.bin",
        "col": "pl06pl.bin",
        "anim": "pl06plm.bin",
        "to_tex": 158400,
        "to_chd": 0x31392C,
        "num_of_1st": 7392,
    },
    "Ibuki": {
        "tex": "pl07.bin",
        "col": "pl07pl.bin",
        "anim": "pl07plm.bin",
        "to_tex": 151744,
        "to_chd": 0x25D908,
        "num_of_1st": 8384,
    },
    "Elena": {
        "tex": "pl08.bin",
        "col": "pl08pl.bin",
        "anim": "pl08plm.bin",
        "to_tex": 142292,
        "to_chd": 0x1A0CCC,
        "num_of_1st": 10208,
    },
    "Oro": {
        "tex": "pl09.bin",
        "col": "pl09pl.bin",
        "anim": "pl09plm.bin",
        "to_tex": 137680,
        "to_chd": 0x205694,
        "num_of_1st": 11776,
    },
    "Yang": {
        "tex": "pl10.bin",
        "col": "pl10pl.bin",
        "anim": "pl10plm.bin",
        "to_tex": 116892,
        "to_chd": 0x216E64,
        "num_of_1st": 13280,
    },
    "Ken": {
        "tex": "pl11.bin",
        "col": "pl11pl.bin",
        "anim": "pl11plm.bin",
        "to_tex": 71900,
        "to_chd": 0x17C0F8,
        "num_of_1st": 14656,
    },
    "Sean": {
        "tex": "pl12.bin",
        "col": "pl12pl.bin",
        "anim": "pl12plm.bin",
        "to_tex": 80596,
        "to_chd": 0x18B378,
        "num_of_1st": 15712,
    },
    "Urien": {
        "tex": "pl13.bin",
        "col": "pl13pl.bin",
        "anim": "pl13plm.bin",
        "to_tex": 135428,
        "to_chd": 0x215C68,
        "num_of_1st": 16800,
    },
    "Akuma": {
        "tex": "pl14.bin",
        "col": "pl14pl.bin",
        "anim": "pl14plm.bin",
        "to_tex": 116116,
        "to_chd": 0x26DFC8,
        "num_of_1st": 18272,
    },
    "Chun-Li": {
        "tex": "pl16.bin",
        "col": "pl16pl.bin",
        "anim": "pl16plm.bin",
        "to_tex": 144584,
        "to_chd": 0x26C73C,
        "num_of_1st": 19456,
    },
    "Makoto": {
        "tex": "pl17.bin",
        "col": "pl17pl.bin",
        "anim": "pl17plm.bin",
        "to_tex": 177724,
        "to_chd": 0x2837C4,
        "num_of_1st": 21120,
    },
    "Q": {
        "tex": "pl18.bin",
        "col": "pl18pl.bin",
        "anim": "pl18plm.bin",
        "to_tex": 222124,
        "to_chd": 0x37F0B4,
        "num_of_1st": 23008,
    },
    "Twelve": {
        "tex": "pl19.bin",
        "col": "pl19pl.bin",
        "anim": "pl19plm.bin",
        "to_tex": 131348,
        "to_chd": 0x21B47C,
        "num_of_1st": 24704,
    },
    "Remy": {
        "tex": "pl20.bin",
        "col": "pl20pl.bin",
        "anim": "pl20plm.bin",
        "to_tex": 125420,
        "to_chd": 0x1A4F50,
        "num_of_1st": 25856,
    },
}
"""A dictionary that maps character names to their associated asset files.

The keys are the character names, and the values are dictionaries containing the
filenames for the character's textures, colors, and animations.

Each character dictionary has the following keys:
    - "tex" (str): The filename of the texture file.
    - "col" (str): The filename of the color palette file.
    - "anim" (str): The filename of the animation data file.
    - "to_tex" (int): The offset to the texture data within the texture file.
"""
