#!/usr/bin/env python3
"""
Custom logging setup for the application
"""

from __future__ import annotations

import json
import logging
import logging.handlers
import os
import sys
import threading
from collections import deque
from collections.abc import Callable
from datetime import datetime
from typing import Any

# Define dummy classes if PyQt6 is not available
# This allows type checkers to see the attributes, and runtime code to execute
# without errors if QCoreApplication etc. are None.


class _DummyQCoreApplication:  # pylint: disable=too-few-public-methods
    """Dummy QCoreApplication for when PyQt6 is not available."""

    @classmethod
    def instance(cls) -> Any:
        """Return None as no application instance exists."""
        return None

    def thread(self) -> Any:
        """Return None as no thread exists."""
        return None  # For core_app_instance.thread()


class _DummyQThread:  # pylint: disable=too-few-public-methods
    """Dummy QThread for when PyQt6 is not available."""

    @classmethod
    def currentThread(cls) -> Any:  # noqa: N802
        """Return None as no current thread exists."""
        return None


class _DummyQTimer:  # pylint: disable=too-few-public-methods
    """Dummy QTimer for when PyQt6 is not available."""

    @classmethod
    def singleShot(cls, msec: int, callback: Callable) -> None:  # noqa: N802
        """No-op singleShot."""


# Initialize runtime variables
qt_available = False
QCoreApplication: Any = _DummyQCoreApplication
QThread: Any = _DummyQThread
QTimer: Any = _DummyQTimer

try:
    from PyQt6.QtCore import QCoreApplication as _QCoreApplication_Real
    from PyQt6.QtCore import QThread as _QThread_Real
    from PyQt6.QtCore import QTimer as _QTimer_Real

    QCoreApplication = _QCoreApplication_Real
    QThread = _QThread_Real
    QTimer = _QTimer_Real
    qt_available = True
except ImportError:
    # They remain the Dummy classes as initialized above, and QT_AVAILABLE
    # remains False.
    pass


class GuiLogHandler(logging.Handler):
    """Custom log handler that sends logs to GUI components"""

    def __init__(self, console_callback: Callable[[str], None] | None = None, max_records: int = 1000):
        """
        Initialize the GUI log handler

        Args:
            console_callback: Callback function to handle log messages
            max_records: Maximum number of log records to keep in memory
        """
        super().__init__()
        self.console_callback = console_callback
        self.log_records: deque[str] = deque(maxlen=max_records)
        self._lock = threading.Lock()
        self.setFormatter(self._create_formatter())

    def _create_formatter(self) -> logging.Formatter:
        """Create a formatter for GUI output"""
        return logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s", datefmt="%H:%M:%S")

    def emit(self, record):
        """Emit a log record"""
        try:
            # Store the record safely
            with self._lock:
                self.log_records.append(self.format(record))

            # Call the callback if provided
            if self.console_callback:
                # We can assume QCoreApplication, QThread, QTimer are always classes (real or dummy) here.
                # QT_AVAILABLE determines if they are real or dummy.

                # Get instances or current thread information
                core_app_instance = QCoreApplication.instance()
                current_thread_obj = QThread.currentThread()  # It's a method on the class itself

                # Only proceed with Qt threading logic if QT_AVAILABLE is True
                if core_app_instance is not None and current_thread_obj is not None:
                    _timer_to_use = QTimer  # Capture QTimer locally
                    if current_thread_obj != core_app_instance.thread():
                        _timer_to_use.singleShot(0, lambda: self._safe_callback(self.format(record)))
                    else:
                        self._safe_callback(self.format(record))
                else:
                    # Either qt_available is False (using dummy classes), or QCoreApplication.instance()
                    # or QThread.currentThread() returned None.
                    # In both cases, directly call the callback without Qt
                    # threading.
                    self._safe_callback(self.format(record))

        except Exception:  # pylint: disable=broad-exception-caught
            self.handleError(record)

    def _safe_callback(self, message: str):
        """Safely call the callback function"""
        if self.console_callback:
            self.console_callback(message)

    def get_recent_logs(self, count: int = 100) -> list:
        """Get recent log records"""
        with self._lock:
            return list(self.log_records)[-count:]

    def clear_logs(self):
        """Clear all log records"""
        with self._lock:
            self.log_records.clear()


class ColoredFormatter(logging.Formatter):
    """Formatter that adds colors for console output"""

    COLORS = {
        "DEBUG": "\033[36m",  # Cyan
        "INFO": "\033[32m",  # Green
        "WARNING": "\033[33m",  # Yellow
        "ERROR": "\033[31m",  # Red
        "CRITICAL": "\033[35m",  # Magenta
        "RESET": "\033[0m",  # Reset
    }

    def format(self, record):
        """Format the log record with colors"""
        color = self.COLORS.get(record.levelname, "")
        reset = self.COLORS["RESET"]

        # Format the message
        formatted = super().format(record)

        # Add color to the level name
        if color:
            formatted = formatted.replace(f"[{record.levelname}]", f"{color}[{record.levelname}]{reset}")

        return formatted


class JsonFormatter(logging.Formatter):
    """Formatter that outputs logs in JSON format"""

    def format(self, record):
        """Format the log record as JSON"""
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        # Add extra fields
        for key, value in record.__dict__.items():
            if key not in [
                "name",
                "msg",
                "args",
                "levelname",
                "levelno",
                "pathname",
                "filename",
                "module",
                "exc_info",
                "exc_text",
                "stack_info",
                "lineno",
                "funcName",
                "created",
                "msecs",
                "relativeCreated",
                "thread",
                "threadName",
                "processName",
                "process",
                "getMessage",
            ]:
                log_entry[key] = value

        return json.dumps(log_entry, ensure_ascii=False, indent=2)


def setup_logging(
    level: int = logging.INFO,
    log_file: str | None = None,
    console_output: bool = True,
    enable_colors: bool = True,
    max_log_records: int = 1000,
) -> dict[str, Any]:
    """
    Set up logging configuration

    Args:
        level: Logging level
        log_file: Optional log file path
        console_output: Whether to output to console
        enable_colors: Whether to enable colored console output
        max_log_records: Maximum number of log records to keep in memory

    Returns:
        Dictionary containing logger and GUI handler
    """
    # Create logger
    logger = logging.getLogger()
    logger.setLevel(level)

    # Clear existing handlers
    logger.handlers.clear()

    # Create formatters
    detailed_formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )

    simple_formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")

    # Add console handler
    if console_output:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(level)

        if enable_colors and os.name != "nt":  # Colors work on Unix-like systems
            colored_formatter = ColoredFormatter(
                "%(asctime)s [%(levelname)s] %(name)s: %(message)s", datefmt="%H:%M:%S"
            )
            console_handler.setFormatter(colored_formatter)
        else:
            console_handler.setFormatter(simple_formatter)

        logger.addHandler(console_handler)

    # Add file handler
    if log_file:
        log_dir = os.path.dirname(log_file)
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)

        file_handler = logging.handlers.RotatingFileHandler(
            log_file, maxBytes=10485760, backupCount=5, encoding="utf-8"
        )
        file_handler.setLevel(level)
        file_handler.setFormatter(detailed_formatter)
        logger.addHandler(file_handler)

    # Create GUI handler
    gui_handler = GuiLogHandler(max_records=max_log_records)
    gui_handler.setLevel(level)
    gui_handler.setFormatter(simple_formatter)
    logger.addHandler(gui_handler)

    # Create a summary log for critical events
    summary_logger = logging.getLogger("summary")
    summary_logger.setLevel(logging.WARNING)

    # Add summary handler (only for WARNING and above)
    if log_file:
        summary_handler = logging.handlers.RotatingFileHandler(
            log_file.replace(".log", "_summary.log"), maxBytes=1048576, backupCount=3, encoding="utf-8"
        )
        summary_handler.setLevel(logging.WARNING)
        summary_handler.setFormatter(detailed_formatter)
        summary_logger.addHandler(summary_handler)

    # Log application startup
    logger.info("=" * 60)
    logger.info("Application logging initialized")
    logger.info("Logging level: %s", logging.getLevelName(level))
    logger.info("Log file: %s", log_file if log_file else "None")
    logger.info("=" * 60)

    return {"logger": logger, "gui_handler": gui_handler, "summary_logger": summary_logger}


def get_logger(name: str) -> logging.Logger:
    """Get a named logger"""
    return logging.getLogger(name)


def log_exception(logger: logging.Logger, message: str, exc_info: tuple | None = None):
    """Log an exception with context"""
    if exc_info is None:
        exc_info = sys.exc_info()

    logger.error("%s: %s", message, exc_info[1], exc_info=exc_info)


# Global logging state
_LOGGING_INITIALIZED = False
_GUI_HANDLER = None


def setup_global_logging(level: int = logging.INFO, log_file: str | None = None):
    """Set up global logging configuration"""
    global _LOGGING_INITIALIZED, _GUI_HANDLER  # pylint: disable=global-statement

    if not _LOGGING_INITIALIZED:
        result = setup_logging(level, log_file)
        _GUI_HANDLER = result["gui_handler"]
        _LOGGING_INITIALIZED = True
        return result

    return {"logger": logging.getLogger(), "gui_handler": _GUI_HANDLER}


def get_global_gui_handler():
    """Get the global GUI log handler"""
    return _GUI_HANDLER
