#!/usr/bin/env python3
"""
SF3:3rd Asset Explorer - Main package initialization
"""

__version__ = "1.0.0"
__author__ = "Your Name"
__email__ = "your.email@example.com"

# Global constants
APP_NAME = "SF3:3rd Asset Explorer"
APP_VERSION = __version__
COMPANY_NAME = "YourCompany"

# Configuration paths
DEFAULT_CONFIG_PATH = "config/sf3assetexplorer.conf"
LOG_DIR = "logs"
CACHE_DIR = "cache"

# Supported file formats
SUPPORTED_AUDIO_FORMATS = [".adx", ".wav", ".mp3", ".ogg"]
SUPPORTED_IMAGE_FORMATS = [".png", ".jpg", ".jpeg", ".bmp", ".gif"]
SUPPORTED_ASSET_FORMATS = SUPPORTED_AUDIO_FORMATS + SUPPORTED_IMAGE_FORMATS

# Recent files limit
MAX_RECENT_FILES = 10
