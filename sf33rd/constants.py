"""
Constants for SF3:3rd Strike Asset Explorer
"""

SF3_EXTENSIONS = {
    ".adx",  # ADX audio files
    ".bg",  # Background images
    ".bgx",  # Background images (variant)
    ".chr",  # Character data
    ".pl",  # Player data
    ".st",  # Stage data
    ".bin",  # Binary data
    ".dat",  # Data files
    ".pac",  # Archive files
    ".pfs",  # Package files
}

SUPPORTED_AUDIO_EXTENSIONS = [".adx", ".wav", ".mp3", ".ogg", ".flac", ".m4a"]
SUPPORTED_IMAGE_EXTENSIONS = [".png", ".jpg", ".jpeg", ".bmp", ".gif", ".tiff", ".webp"]
SUPPORTED_ARCHIVE_EXTENSIONS = [".zip", ".rar", ".7z", ".tar", ".gz"]

SF3_PATTERNS = [
    r"bgm.*\.(adx|wav)$",  # Background music
    r"se.*\.(adx|wav)$",  # Sound effects
    r"voice.*\.(adx|wav)$",  # Voice files
    r"bg.*\.(png|jpg|bg|bgx)$",  # Background graphics
    r"stage.*\.(png|jpg|bg|bgx)$",  # Stage graphics
    r"char.*\.(png|jpg|chr)$",  # Character graphics
    r"player.*\.(png|jpg|pl)$",  # Player graphics
    r"font.*\.(png|fnt)$",  # Font files
    r"system.*\.(png|dat)$",  # System files
    r"\.(pac|pfs|bin|dat)$",  # Archive and data files
]

SF3_KEYWORDS = [
    "bgm",
    "se",
    "voice",
    "sfx",  # Audio
    "bg",
    "stage",
    "char",
    "player",  # Graphics
    "font",
    "system",
    "menu",  # UI
    "common",
    "select",
    "ending",  # Game modes
]

SYSTEM_KEYWORDS = [
    "End",
    "VS",
    "Open",
    "Sel",
    "Win",
    "Judge",
    "Over",
    "Gill",
    "Bo",
    "Staff",
    "Remix",
    "Menu",
    "Logo",
]

UI_KEYWORDS = [
    "Select",
    "Win",
    "Rank",
    "Title",
    "Warning",
    "CapLogo",
    "Option",
    "mcicon",
]

CHAR_MAP = {
    "PL00": "Gill",
    "PL01": "Alex",
    "PL02": "Ryu",
    "PL03": "Yun",
    "PL04": "Dudley",
    "PL05": "Necro",
    "PL06": "Hugo",
    "PL07": "Ibuki",
    "PL08": "Elena",
    "PL09": "Oro",
    "PL10": "Yang",
    "PL11": "Ken",
    "PL12": "Sean",
    "PL13": "Urien",
    "PL14": "Akuma",
    "PL15": "Twelve",
    "PL16": "Chun-Li",
    "PL17": "Makoto",
    "PL18": "Q",
    "PL19": "Gill (2)",
}

AUDIO_SAMPLE_RATES = [
    8000,
    11025,
    16000,
    22050,
    32000,
    44100,
    48000,
    88200,
    96000,
    176400,
    192000,
]

AUDIO_BIT_DEPTHS = [8, 16, 24, 32]
