#!/usr/bin/env python3
"""
Custom log handler for GUI integration
"""

import logging


class GuiLogHandler(logging.Handler):
    """Bridge between python logging and UI elements/services."""

    def __init__(self, callback=None):
        """
        Initialize the GUI log handler

        Args:
            callback: Callback function to handle log records
        """
        super().__init__()
        self.callback = callback

    def emit(self, record):
        """Emit a log record"""
        try:
            if self.callback:
                self.callback(record)
        except Exception:  # pylint: disable=broad-exception-caught
            self.handleError(record)
