#!/usr/bin/env python3
"""
Monkey patch system for sf33rd library integration
This module provides integration between the sf33rd library and the GUI application.
"""

import io
import logging
import sys
import threading
import traceback
from collections.abc import Callable

# Import Qt modules
try:
    from PyQt6.QtCore import QCoreApplication, QThread, QTimer

    QT_AVAILABLE = True
except ImportError:
    QTimer = None  # type: ignore[misc, assignment]
    QThread = None  # type: ignore[misc, assignment]
    QCoreApplication = None  # type: ignore[misc, assignment]
    QT_AVAILABLE = False

try:
    import sf33rd
except ImportError:
    sf33rd = None  # type: ignore


class GuiLogHandler(logging.Handler):
    """Custom log handler that sends logs to GUI components"""

    def __init__(self, log_callback: Callable | None = None):
        """
        Initialize the GUI log handler

        Args:
            log_callback: Optional callback function to handle log messages
        """
        super().__init__()
        self.log_callback = log_callback
        self.log_records: list[logging.LogRecord] = []
        self._lock = threading.Lock()

    def emit(self, record):
        """Emit a log record"""
        try:
            # Store the record safely
            with self._lock:
                self.log_records.append(record)

            # Call the callback if provided
            if self.log_callback:
                # Ensure callback is called in the main thread for Qt safety
                if QT_AVAILABLE and QCoreApplication is not None and QThread is not None and QTimer is not None:
                    instance = QCoreApplication.instance()
                    if instance is not None:
                        curr_thread = QThread.currentThread()
                        if curr_thread is not None and curr_thread != instance.thread():
                            # Schedule callback for main thread
                            QTimer.singleShot(0, lambda: self._safe_callback(record))
                            return

                self._safe_callback(record)

        except Exception:  # pylint: disable=broad-exception-caught
            self.handleError(record)

    def _safe_callback(self, record):
        """Safely call the callback function"""
        try:
            if self.log_callback:
                self.log_callback(record)
        except Exception:  # pylint: disable=broad-exception-caught
            self.handleError(record)


class StdoutRedirector(io.StringIO):
    """Redirect stdout to GUI components"""

    def __init__(self, output_callback: Callable | None = None):
        """
        Initialize the stdout redirector

        Args:
            output_callback: Optional callback for output handling
        """
        super().__init__()
        self.output_callback = output_callback
        self._original_stdout = sys.stdout
        self._lock = threading.Lock()

    def write(self, s):
        """Write to the stream and redirect to callback"""
        # Call parent write method
        result = super().write(s)

        # Send to callback if provided and not empty
        if self.output_callback and s.strip():
            # Ensure callback is called in the main thread for Qt safety
            self._safe_callback(s)

        return result

    def flush(self):
        """Flush the stream"""
        super().flush()
        if hasattr(self._original_stdout, "flush"):
            self._original_stdout.flush()

    def _safe_callback(self, text):
        """Safely call the callback function"""
        try:
            if QT_AVAILABLE and QCoreApplication is not None and QThread is not None and QTimer is not None:
                instance = QCoreApplication.instance()
                if instance is not None:
                    curr_thread = QThread.currentThread()
                    if curr_thread is not None and curr_thread != instance.thread():
                        # Schedule callback for main thread
                        if self.output_callback:
                            cb = self.output_callback
                            QTimer.singleShot(0, lambda: cb(text))
                        return

            if self.output_callback:
                self.output_callback(text)
        except Exception as e:  # pylint: disable=broad-exception-caught
            # Log error but don't crash
            print(f"Error in stdout callback: {e}", file=self._original_stdout)


class Sf33rdPatcher:
    """Main class for applying sf33rd library patches"""

    def __init__(self):
        self.patches_applied = False
        self.original_stdout = None
        self.original_stderr = None
        self.gui_log_handler = None
        self.stdout_redirector = None
        self.stderr_redirector = None
        self.patched_functions = {}
        self._lock = threading.Lock()

    def apply_monkey_patches(self):
        """Apply all monkey patches for sf33rd integration"""
        if self.patches_applied:
            return

        try:
            self._patch_logging()
            self._patch_stdout_stderr()
            self._patch_sf33rd_functions()

            self.patches_applied = True
            print("Monkey patches applied successfully")

        except Exception as e:  # pylint: disable=broad-exception-caught
            print(f"Failed to apply monkey patches: {e}")
            print(f"Traceback: {traceback.format_exc()}")
            # Don't raise - the application should still work without patches

    def _patch_logging(self):
        """Patch the logging system to integrate with GUI"""
        try:
            # Get the root logger
            root_logger = logging.getLogger()

            # Create GUI log handler
            self.gui_log_handler = GuiLogHandler()

            # Add the handler to the root logger
            root_logger.addHandler(self.gui_log_handler)

            print("Logging system patched successfully")

        except Exception as e:  # pylint: disable=broad-exception-caught
            print(f"Failed to patch logging: {e}")
            print(f"Traceback: {traceback.format_exc()}")

    def _patch_stdout_stderr(self):
        """Patch stdout and stderr to redirect to GUI"""
        try:
            # Save original streams
            self.original_stdout = sys.stdout
            self.original_stderr = sys.stderr

            # Create redirectors
            self.stdout_redirector = StdoutRedirector(self._handle_output)
            self.stderr_redirector = StdoutRedirector(self._handle_error)

            # Replace system streams
            sys.stdout = self.stdout_redirector
            sys.stderr = self.stderr_redirector

            print("Stdout/stderr redirection set up successfully")

        except Exception as e:  # pylint: disable=broad-exception-caught
            print(f"Failed to patch stdout/stderr: {e}")
            print(f"Traceback: {traceback.format_exc()}")

    def _patch_sf33rd_functions(self):
        """Patch specific sf33rd functions"""
        if sf33rd is None:
            print("sf33rd library not found - skipping function patches")
            return

        try:
            # List of functions to patch
            functions_to_patch = ["extract_audio", "extract_image", "parse_file", "get_metadata", "process_directory"]

            for func_name in functions_to_patch:
                if hasattr(sf33rd, func_name):
                    original_func = getattr(sf33rd, func_name)
                    wrapped_func = self._wrap_sf33rd_function(original_func, func_name)
                    setattr(sf33rd, func_name, wrapped_func)
                    self.patched_functions[func_name] = original_func

            print(f"sf33rd functions patched successfully: {list(self.patched_functions.keys())}")

        except Exception as e:  # pylint: disable=broad-exception-caught
            print(f"Failed to patch sf33rd functions: {e}")
            print(f"Traceback: {traceback.format_exc()}")

    def _wrap_sf33rd_function(self, original_function, func_name):
        """Wrap an sf33rd function to capture its output"""

        def wrapper(*args, **kwargs):
            try:
                print(f"Calling sf33rd function: {func_name}")
                result = original_function(*args, **kwargs)
                print(f"sf33rd function {func_name} completed successfully")
                return result
            except Exception as e:  # pylint: disable=broad-exception-caught
                print(f"Error in sf33rd function {func_name}: {e}")
                print(f"Args: {args[:3]}..." if len(args) > 3 else f"Args: {args}")
                raise

        return wrapper

    def _handle_output(self, text):
        """Handle normal output (implementation provided by set_output_callback)"""
        _ = text

    def _handle_error(self, text):
        """Handle error output (implementation provided by set_error_callback)"""
        _ = text

    def set_output_callback(self, callback):
        """Set the callback for handling output"""
        if self.stdout_redirector:
            self.stdout_redirector.output_callback = callback

    def set_error_callback(self, callback):
        """Set the callback for handling errors"""
        if self.stderr_redirector:
            self.stderr_redirector.output_callback = callback

    def set_log_callback(self, callback):
        """Set the callback for handling log messages"""
        if self.gui_log_handler:
            self.gui_log_handler.log_callback = callback

    def remove_monkey_patches(self):
        """Remove all monkey patches"""
        if not self.patches_applied:
            return

        try:
            with self._lock:
                # Restore original streams
                if self.original_stdout:
                    sys.stdout = self.original_stdout
                if self.original_stderr:
                    sys.stderr = self.original_stderr

                # Remove log handler
                if self.gui_log_handler:
                    root_logger = logging.getLogger()
                    if self.gui_log_handler in root_logger.handlers:
                        root_logger.removeHandler(self.gui_log_handler)

                # Restore original sf33rd functions
                if self.patched_functions and sf33rd:
                    try:
                        for func_name, original_func in self.patched_functions.items():
                            setattr(sf33rd, func_name, original_func)
                        print(f"Restored sf33rd functions: {list(self.patched_functions.keys())}")
                        self.patched_functions.clear()
                    except Exception as e:  # pylint: disable=broad-exception-caught
                        print(f"Error restoring sf33rd functions: {e}")

                print("Monkey patches removed successfully")
                self.patches_applied = False

        except Exception as e:  # pylint: disable=broad-exception-caught
            print(f"Failed to remove monkey patches: {e}")
            print(f"Traceback: {traceback.format_exc()}")


# Global patcher instance
_patcher_instance = None  # pylint: disable=invalid-name


def apply_monkey_patches():
    """Apply monkey patches for sf33rd integration"""
    global _patcher_instance  # pylint: disable=global-statement
    if _patcher_instance is None:
        _patcher_instance = Sf33rdPatcher()
    _patcher_instance.apply_monkey_patches()


def get_patcher():
    """Get the global patcher instance"""
    global _patcher_instance  # pylint: disable=global-statement
    if _patcher_instance is None:
        _patcher_instance = Sf33rdPatcher()
    return _patcher_instance


def setup_gui_callbacks(output_callback=None, error_callback=None, log_callback=None):
    """Setup GUI callbacks for output handling"""
    patcher = get_patcher()
    if output_callback:
        patcher.set_output_callback(output_callback)
    if error_callback:
        patcher.set_error_callback(error_callback)
    if log_callback:
        patcher.set_log_callback(log_callback)
