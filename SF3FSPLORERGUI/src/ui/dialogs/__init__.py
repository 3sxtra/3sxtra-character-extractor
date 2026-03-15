#!/usr/bin/env python3
"""
SF3:3rd Character Editor - Dialogs (standalone)
"""
# Standalone release - only Character Editor dialogs
from .about import BaseAboutDialog
from .progress_dialog import ProgressDialog, BackgroundTaskDialog

__all__ = [
    "BaseAboutDialog",
    "ProgressDialog",
    "BackgroundTaskDialog",
]
