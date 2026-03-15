#!/usr/bin/env python3
"""
Base class for all background workers
"""

import logging
import os
import tempfile
import threading
import time
import traceback
from collections.abc import Callable
from typing import Any

from PyQt6.QtCore import QThread, pyqtSignal


class WorkerCancelledError(Exception):
    """Exception raised when a worker is cancelled"""


class WorkerTimeoutError(Exception):
    """Exception raised when a worker times out"""


class BaseWorker(QThread):
    """Base class for all background workers"""

    # pylint: disable=too-many-public-methods,too-many-instance-attributes,R0902

    # Common signals
    progress = pyqtSignal(int, int)  # current, maximum
    status = pyqtSignal(str)  # status message
    finished = pyqtSignal(object)  # result data
    error = pyqtSignal(str)  # error message
    started = pyqtSignal()  # worker started
    cancelled = pyqtSignal()  # worker cancelled
    # chunk progress: processed, total, message
    progress_chunk = pyqtSignal(int, int, str)

    def __init__(self):
        """Initialize the base worker"""
        super().__init__()

        # Worker state
        self._is_running = False
        self._is_cancelled = False
        self._timeout = 300  # 5 minutes default timeout
        self.error_occurred = self.error  # Alias for compatibility
        self._start_time: float | None = None

        # Threading
        self._thread = None
        self._thread_lock = threading.Lock()

        # Error handling
        self._last_error = None
        self._retry_count = 0
        self._max_retries = 3

        # Progress tracking
        self._progress_current = 0
        self._progress_maximum = 0
        self._chunk_size = 100

        # Configuration
        self._batch_mode = False
        self._priority = 0  # Higher values = higher priority

        # Callbacks
        self._completion_callback = None
        self._error_callback = None

        # Logging
        # Logging
        self.logger = logging.getLogger(self.__class__.__name__)

        # Temporary files
        self._temp_files: list[str] = []
        self._working_directory: str = ""

        # Statistics
        self._statistics: dict[str, Any] = {
            "start_time": None,
            "end_time": None,
            "duration": 0.0,
            "items_processed": 0,
            "items_total": 0,
            "memory_usage": 0,
        }

    def set_logger(self, logger):
        """Set the logger for this worker"""
        if logger:
            self.logger = logger

    def run(self):
        """Execute the worker task"""
        with self._thread_lock:
            if self._is_running:
                self.logger.warning("Worker %s is already running", self.__class__.__name__)
                return

            self._is_running = True
            self._is_cancelled = False
            self._start_time = time.time()
            self._statistics["start_time"] = self._start_time

        try:
            self.logger.info("Starting %s", self.__class__.__name__)
            self.started.emit()
            self.update_status(f"Starting {self.__class__.__name__}")

            # Setup timeout monitoring
            if self._timeout > 0:
                self._start_timeout_monitor()

            # Call the specific worker implementation
            result = self._do_work()

            # Check if worker was cancelled
            if self._is_cancelled:
                self.logger.info("%s was cancelled", self.__class__.__name__)
                self.cancelled.emit()
                return

            # Complete successfully
            self._statistics["end_time"] = time.time()
            start_time = self._statistics["start_time"]
            end_time = self._statistics["end_time"]
            if start_time is not None and end_time is not None:
                self._statistics["duration"] = end_time - start_time

            self.logger.info("Completed %s in %ss", self.__class__.__name__, self._statistics["duration"])
            self.update_status(f"Completed {self.__class__.__name__}")

            self.finished.emit(result)

            # Call completion callback if provided
            if self._completion_callback:
                self._completion_callback(result)

        except WorkerCancelledError as e:
            self.logger.info("%s was cancelled: %s", self.__class__.__name__, e)
            self.cancelled.emit()

        except Exception as e:  # pylint: disable=broad-exception-caught
            self._handle_error(e)

        finally:
            with self._thread_lock:
                self._is_running = False
            self._cleanup()

    def _do_work(self):
        """
        Worker implementation method to be overridden by subclasses

        Returns:
            Result data to be emitted via finished signal
        """
        raise NotImplementedError("Subclasses must implement _do_work method")

    def cancel(self):
        """Cancel the worker"""
        with self._thread_lock:
            if not self._is_running:
                return

            self._is_cancelled = True

        self.logger.info("Cancelling %s", self.__class__.__name__)
        self.update_status(f"Cancelling {self.__class__.__name__}")
        self.cancelled.emit()

    def is_cancelled(self) -> bool:
        """Check if worker is cancelled"""
        return self._is_cancelled

    def is_running(self) -> bool:
        """Check if worker is currently running"""
        return self._is_running

    def set_timeout(self, timeout_seconds: int):
        """
        Set timeout for worker execution

        Args:
            timeout_seconds: Timeout in seconds (0 = no timeout)
        """
        self._timeout = timeout_seconds
        self.logger.debug("Set timeout to %s seconds", timeout_seconds)

    def get_timeout(self) -> int:
        """Get current timeout setting"""
        return self._timeout

    def set_progress(self, current: int, maximum: int):
        """
        Set progress information

        Args:
            current: Current progress value
            maximum: Maximum progress value
        """
        self._progress_current = current
        self._progress_maximum = maximum
        self.progress.emit(current, maximum)

        # Emit chunk progress for batch operations
        if self._batch_mode and maximum > 0:
            chunk_progress = (current // self._chunk_size) * self._chunk_size
            if chunk_progress > 0 and chunk_progress % (self._chunk_size * 10) == 0:
                percentage = (current / maximum) * 100 if maximum > 0 else 0
                message = f"Progress: {current}/{maximum} ({percentage:.1f}%)"
                self.progress_chunk.emit(current, maximum, message)

    def update_status(self, message: str):
        """
        Update worker status message

        Args:
            message: Status message
        """
        self.status.emit(message)
        self.logger.debug("Status: %s", message)

    def check_cancellation(self):
        """Check if worker should be cancelled and raise exception if so"""
        if self._is_cancelled:
            raise WorkerCancelledError(f"{self.__class__.__name__} was cancelled")

    def check_timeout(self):
        """Check if worker has exceeded timeout"""
        if self._timeout > 0 and self._start_time:
            elapsed = time.time() - self._start_time
            if elapsed > self._timeout:
                raise WorkerTimeoutError(f"{self.__class__.__name__} exceeded timeout of {self._timeout} seconds")

    def set_chunk_size(self, chunk_size: int):
        """Set chunk size for progress reporting"""
        self._chunk_size = max(1, chunk_size)

    def enable_batch_mode(self, enable: bool = True):
        """Enable batch mode for chunked progress reporting"""
        self._batch_mode = enable

    def set_priority(self, priority: int):
        """Set worker priority (higher values = higher priority)"""
        self._priority = priority

    def get_priority(self) -> int:
        """Get worker priority"""
        return self._priority

    def set_retry_count(self, max_retries: int):
        """Set maximum retry attempts"""
        self._max_retries = max_retries

    def get_statistics(self) -> dict[str, Any]:
        """Get worker execution statistics"""
        return self._statistics.copy()

    def set_completion_callback(self, callback: Callable):
        """Set callback function to call on successful completion"""
        self._completion_callback = callback

    def set_error_callback(self, callback: Callable):
        """Set callback function to call on error"""
        self._error_callback = callback

    def _handle_error(self, error: Exception):
        """Handle worker errors"""
        error_msg = f"Error in {self.__class__.__name__}: {str(error)}"
        error_details = traceback.format_exc()

        self._last_error = error
        self._statistics["end_time"] = time.time()
        start_time = self._statistics["start_time"]
        end_time = self._statistics["end_time"]
        if start_time is not None and end_time is not None:
            self._statistics["duration"] = end_time - start_time

        self.logger.error("%s\n%s", error_msg, error_details)
        self.error.emit(error_msg)

        # Call error callback if provided
        if self._error_callback:
            self._error_callback(error)

    def _start_timeout_monitor(self):
        """Start timeout monitoring thread"""

        def timeout_check():
            while self._is_running and not self._is_cancelled:
                time.sleep(1)
                self.check_timeout()

        timeout_thread = threading.Thread(target=timeout_check, daemon=True)
        timeout_thread.start()

    def _create_temp_file(self, extension: str) -> str:
        """Create a temporary file with the given extension"""
        temp_fd, temp_path = tempfile.mkstemp(suffix=extension, dir=self._working_directory or None)
        os.close(temp_fd)  # Close the file descriptor
        self._temp_files.append(temp_path)
        return temp_path

    def _cleanup_temp_files(self):
        """Clean up temporary files"""
        for temp_file in self._temp_files[:]:  # Copy list to avoid modification during iteration
            try:
                if os.path.exists(temp_file):
                    os.unlink(temp_file)
                    self._temp_files.remove(temp_file)
            except OSError as e:
                self.logger.warning("Could not delete temp file %s: %s", temp_file, e)

    def _cleanup(self):
        """Clean up worker resources"""
        try:
            # Clean up any temporary resources
            self.logger.debug("Cleaning up %s", self.__class__.__name__)
            self._cleanup_temp_files()

            # Reset state
            self._start_time = None
            self._progress_current = 0
            self._progress_maximum = 0

        except Exception as e:  # pylint: disable=broad-exception-caught
            self.logger.error("Error during cleanup: %s", e)

    def get_worker_info(self) -> dict[str, Any]:
        """Get comprehensive worker information"""
        return {
            "class_name": self.__class__.__name__,
            "is_running": self._is_running,
            "is_cancelled": self._is_cancelled,
            "timeout": self._timeout,
            "priority": self._priority,
            "batch_mode": self._batch_mode,
            "chunk_size": self._chunk_size,
            "progress": {
                "current": self._progress_current,
                "maximum": self._progress_maximum,
                "percentage": (self._progress_current / self._progress_maximum * 100)
                if self._progress_maximum > 0
                else 0,
            },
            "statistics": self._statistics,
            "last_error": str(self._last_error) if self._last_error else None,
        }

    def validate_config(self) -> bool:
        """Validate worker configuration before execution"""
        try:
            if self._timeout < 0:
                raise ValueError("Timeout must be non-negative")

            if self._chunk_size <= 0:
                raise ValueError("Chunk size must be positive")

            return True

        except Exception as e:  # pylint: disable=broad-exception-caught
            self.logger.error("Configuration validation failed: %s", e)
            return False
