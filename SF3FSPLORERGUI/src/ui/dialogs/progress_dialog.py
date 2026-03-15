#!/usr/bin/env python3
"""
Progress Dialog for Background Operations
Displays progress information for long-running operations with cancellation support.
"""

from collections.abc import Callable

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QCloseEvent
from PyQt6.QtWidgets import QDialog, QFrame, QHBoxLayout, QLabel, QMessageBox, QProgressBar, QPushButton, QVBoxLayout


class ProgressDialog(QDialog):
    """Enhanced progress dialog for background operations"""

    # Signals
    cancelled = pyqtSignal()
    timeout_occurred = pyqtSignal()

    def __init__(
        self,
        title: str = "Operation in Progress",
        message: str = "Please wait...",
        parent=None,
        *,
        show_details: bool = True,
        auto_close: bool = True,
        timeout_seconds: int = 0,
    ):
        """
        Initialize progress dialog

        Args:
            title: Dialog title
            message: Main message text
            parent: Parent widget
            show_details: Show details area for additional information
            auto_close: Automatically close when progress reaches 100%
            timeout_seconds: Auto-cancel after this many seconds (0 = no timeout)
        """
        super().__init__(parent)

        self.setWindowTitle(title)
        self.setModal(True)
        self.setWindowFlag(Qt.WindowType.WindowCloseButtonHint, False)  # Remove X button

        # State variables
        self.current_value = 0
        self.maximum_value = 100
        self.is_cancelled = False
        self.auto_close = auto_close
        self.timeout_seconds = timeout_seconds
        self.elapsed_time = 0

        # UI components
        self.progress_bar: QProgressBar | None = None
        self.message_label: QLabel | None = None
        self.details_label: QLabel | None = None
        self.time_label: QLabel | None = None
        self.cancel_button: QPushButton | None = None
        self.progress_label: QLabel | None = None
        self.progress_status_label: QLabel | None = None
        self.update_timer: QTimer | None = None
        self.timeout_timer: QTimer | None = None
        self.details_frame: QFrame | None = None
        self.details_layout: QVBoxLayout | None = None
        self.show_details = show_details

        # Timers
        self.update_timer = None
        self.timeout_timer = None

        # Callbacks
        self.progress_callback: Callable | None = None
        self.cancel_callback: Callable | None = None

        self.setup_ui()
        self.setup_timers()

        # Set initial message
        self.set_message(message)
        self.set_details("")

    def setup_ui(self):
        """Set up the dialog UI"""
        main_layout = QVBoxLayout(self)

        # Main content area
        content_layout = QVBoxLayout()

        # Message label
        self.message_label = QLabel()
        self.message_label.setWordWrap(True)
        self.message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.message_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        content_layout.addWidget(self.message_label)

        # Progress bar
        progress_layout = QHBoxLayout()

        self.progress_label = QLabel("Progress:")
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFixedHeight(25)

        progress_layout.addWidget(self.progress_label)
        progress_layout.addWidget(self.progress_bar)

        content_layout.addLayout(progress_layout)

        # Details area
        self.details_frame = QFrame()
        self.details_frame.setFrameShape(QFrame.Shape.Box)
        self.details_frame.setFrameShadow(QFrame.Shadow.Sunken)
        self.details_layout = QVBoxLayout(self.details_frame)

        self.details_label = QLabel()
        self.details_label.setWordWrap(True)
        self.details_label.setTextFormat(Qt.TextFormat.PlainText)
        self.details_layout.addWidget(self.details_label)

        content_layout.addWidget(self.details_frame)
        if not self.show_details:
            self.details_frame.hide()

        # Time and status
        status_layout = QHBoxLayout()

        self.progress_status_label = QLabel("Ready")
        self.time_label = QLabel("00:00:00")
        self.time_label.setAlignment(Qt.AlignmentFlag.AlignRight)

        status_layout.addWidget(self.progress_status_label)
        status_layout.addWidget(self.time_label)

        content_layout.addLayout(status_layout)

        main_layout.addLayout(content_layout)

        # Button area
        button_layout = QHBoxLayout()

        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.on_cancel)

        button_layout.addStretch()
        button_layout.addWidget(self.cancel_button)

        main_layout.addLayout(button_layout)

        # Set minimum size
        self.setMinimumSize(400, 200)
        self.setMaximumSize(600, 400)

    def setup_timers(self):
        """Set up update and timeout timers"""
        # Update timer for time display and progress updates
        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(self.update_time_display)
        self.update_timer.start(1000)  # Update every second

        # Timeout timer
        if self.timeout_seconds > 0:
            self.timeout_timer = QTimer(self)
            self.timeout_timer.timeout.connect(self.on_timeout)
            self.timeout_timer.start(self.timeout_seconds * 1000)

    def set_message(self, message: str):
        """Set the main message text"""
        if self.message_label:
            self.message_label.setText(message)

    def set_details(self, details: str):
        """Set the details text"""
        if self.details_label:
            self.details_label.setText(details)

    def set_progress(self, current: int, maximum: int = 100):
        """Set progress value and maximum"""
        self.current_value = max(0, min(current, maximum))
        self.maximum_value = maximum

        # Update progress bar
        if self.progress_bar:
            self.progress_bar.setMinimum(0)
            self.progress_bar.setMaximum(maximum)
            self.progress_bar.setValue(self.current_value)

        # Update progress text
        if maximum > 0:
            percentage = (self.current_value / maximum) * 100
            if self.progress_bar:
                self.progress_bar.setFormat(f"{percentage:.1f}% ({self.current_value}/{maximum})")

            # Update status text
            if self.progress_status_label:
                self.progress_status_label.setText(f"Completed: {self.current_value}/{maximum} ({percentage:.1f}%)")

        # Auto-close if enabled and complete
        if self.auto_close and current >= maximum:
            QTimer.singleShot(1000, self.accept)  # Close after 1 second

    def increment_progress(self, increment: int = 1):
        """Increment progress by given amount"""
        self.set_progress(self.current_value + increment, self.maximum_value)

    def update_details(self, details: str):
        """Update details with timestamp"""
        timestamp = self.format_time(self.elapsed_time)
        full_details = f"[{timestamp}] {details}"
        if self.details_label:
            self.details_label.setText(full_details)

    def update_time_display(self):
        """Update elapsed time display"""
        self.elapsed_time += 1
        time_str = self.format_time(self.elapsed_time)
        if self.time_label:
            self.time_label.setText(time_str)

    def format_time(self, seconds: int) -> str:
        """Format seconds as HH:MM:SS"""
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"

    def on_cancel(self):
        """Handle cancel button click"""
        self.is_cancelled = True
        if self.cancel_button:
            self.cancel_button.setEnabled(False)
            self.cancel_button.setText("Cancelling...")

        if self.cancel_callback:
            try:
                self.cancel_callback()
            except Exception as e:  # pylint: disable=broad-exception-caught
                print(f"Error in cancel callback: {e}")

        self.cancelled.emit()

    def on_timeout(self):
        """Handle timeout"""
        if self.timeout_timer:
            self.timeout_timer.stop()

        self.timeout_occurred.emit()

        # Show timeout message
        self.set_message("Operation timed out")
        self.set_details("The operation took longer than expected and was automatically cancelled.")
        if self.cancel_button:
            self.cancel_button.setText("Close")
        if self.progress_bar:
            self.progress_bar.setFormat("Timeout")

    def set_cancel_text(self, text: str):
        """Set custom cancel button text"""
        if self.cancel_button:
            self.cancel_button.setText(text)

    def set_cancel_callback(self, callback: Callable):
        """Set callback function for cancel action"""
        self.cancel_callback = callback

    def set_progress_callback(self, callback: Callable):
        """Set callback function for progress updates"""
        self.progress_callback = callback

    def set_indeterminate(self, indeterminate: bool = True):
        """Set progress bar to indeterminate mode"""
        if not self.progress_bar:
            return
        if indeterminate:
            self.progress_bar.setMaximum(0)  # Qt style for indeterminate
            self.progress_bar.setValue(0)
        else:
            self.progress_bar.setMaximum(self.maximum_value)
            self.progress_bar.setValue(self.current_value)

    def closeEvent(self, event: QCloseEvent | None):
        """Handle close event"""
        # Prevent closing if operation is still running (unless cancelled)
        if not self.is_cancelled and self.current_value < self.maximum_value:
            if event:
                event.ignore()
            QMessageBox.information(
                self, "Operation in Progress", "Please wait for the operation to complete or click Cancel to stop it."
            )
        else:
            if event:
                event.accept()

    def reject(self):
        """Override reject to prevent closing if not cancelled"""
        if not self.is_cancelled and self.current_value < self.maximum_value:
            return
        super().reject()

    def showEvent(self, event):
        """Handle show event"""
        super().showEvent(event)
        # Reset elapsed time when dialog is shown
        self.elapsed_time = 0
        if self.time_label:
            self.time_label.setText("00:00:00")

    @classmethod
    def show_simple_progress(cls, parent, title: str, message: str, *, duration: int = 0, show_cancel: bool = True):
        """
        Show a simple progress dialog

        Args:
            parent: Parent widget
            title: Dialog title
            message: Message text
            duration: Expected duration in seconds (0 = unknown)
            show_cancel: Show cancel button

        Returns:
            ProgressDialog instance
        """
        dialog = cls(title, message, parent)
        dialog.set_indeterminate(duration == 0)

        if not show_cancel and dialog.cancel_button:
            dialog.cancel_button.hide()

        if duration > 0:
            # Note: ProgressDialog doesn't have a set_timeout method, it's
            # timeout_seconds in __init__
            pass

        dialog.show()
        return dialog


class BackgroundTaskDialog(QDialog):
    """Dialog for monitoring background tasks with multiple progress indicators"""

    task_completed = pyqtSignal(str, bool)  # task_name, success

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Background Tasks")
        self.setModal(False)

        self.tasks = {}  # task_name -> task_info
        self.setup_ui()

    def setup_ui(self):
        """Set up the task monitoring UI"""
        layout = QVBoxLayout(self)

        # Title
        title_label = QLabel("Background Task Monitor")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(title_label)

        # Tasks list
        self.tasks_layout = QVBoxLayout()
        layout.addLayout(self.tasks_layout)

        # Summary
        summary_layout = QHBoxLayout()

        self.active_tasks_label = QLabel("Active: 0")
        self.completed_tasks_label = QLabel("Completed: 0")
        self.failed_tasks_label = QLabel("Failed: 0")

        summary_layout.addWidget(self.active_tasks_label)
        summary_layout.addWidget(self.completed_tasks_label)
        summary_layout.addWidget(self.failed_tasks_label)
        summary_layout.addStretch()

        layout.addLayout(summary_layout)

        # Close button
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        layout.addWidget(close_button)

        self.setMinimumSize(500, 300)

    def add_task(self, task_name: str, description: str, max_progress: int = 100):
        """Add a new task to monitor"""
        task_widget = self.create_task_widget(task_name, description, max_progress)
        self.tasks_layout.addWidget(task_widget)

        self.tasks[task_name] = {
            "widget": task_widget,
            "description": description,
            "current": 0,
            "maximum": max_progress,
            "completed": False,
            "success": False,
        }

        self.update_summary()

    def create_task_widget(self, task_name: str, description: str, max_progress: int):
        """Create widget for individual task"""
        widget = QFrame()
        widget.setFrameShape(QFrame.Shape.Box)
        widget.setFrameShadow(QFrame.Shadow.Sunken)

        layout = QVBoxLayout(widget)

        # Task header
        header_layout = QHBoxLayout()

        task_label = QLabel(f"{task_name}:")
        task_label.setStyleSheet("font-weight: bold;")

        status_label = QLabel("Running")
        status_label.setObjectName(f"status_{task_name}")

        header_layout.addWidget(task_label)
        header_layout.addWidget(status_label)
        header_layout.addStretch()

        layout.addLayout(header_layout)

        # Description
        desc_label = QLabel(description)
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label)

        # Progress
        progress_layout = QHBoxLayout()

        progress_bar = QProgressBar()
        progress_bar.setMinimum(0)
        progress_bar.setMaximum(max_progress)
        progress_bar.setValue(0)

        progress_label = QLabel("0%")
        progress_label.setObjectName(f"progress_{task_name}")

        progress_layout.addWidget(progress_bar)
        progress_layout.addWidget(progress_label)

        layout.addLayout(progress_layout)

        # Details
        details_label = QLabel("")
        details_label.setWordWrap(True)
        details_label.setObjectName(f"details_{task_name}")
        layout.addWidget(details_label)

        return widget

    def update_task(self, task_name: str, current: int, details: str = ""):
        """Update task progress"""
        if task_name not in self.tasks:
            return

        task_info = self.tasks[task_name]
        task_info["current"] = current

        # Update progress bar and label
        widget = task_info["widget"]
        progress_bar = widget.findChild(QProgressBar)
        progress_label = widget.findChild(QLabel, f"progress_{task_name}")

        if progress_bar:
            progress_bar.setValue(current)

        if progress_label and task_info["maximum"] > 0:
            percentage = (current / task_info["maximum"]) * 100
            progress_label.setText(f"{percentage:.1f}%")

        # Update details
        details_label = widget.findChild(QLabel, f"details_{task_name}")
        if details_label:
            details_label.setText(details)

    def complete_task(self, task_name: str, success: bool = True):
        """Mark task as completed"""
        if task_name not in self.tasks:
            return

        task_info = self.tasks[task_name]
        task_info["completed"] = True
        task_info["success"] = success

        # Update status
        widget = task_info["widget"]
        status_label = widget.findChild(QLabel, f"status_{task_name}")

        if status_label:
            status_text = "Completed" if success else "Failed"
            status_label.setText(status_text)
            status_label.setStyleSheet("color: green;" if success else "color: red;")

        self.task_completed.emit(task_name, success)
        self.update_summary()

    def update_summary(self):
        """Update task summary"""
        active = sum(1 for task in self.tasks.values() if not task["completed"])
        completed = sum(1 for task in self.tasks.values() if task["completed"] and task["success"])
        failed = sum(1 for task in self.tasks.values() if task["completed"] and not task["success"])

        self.active_tasks_label.setText(f"Active: {active}")
        self.completed_tasks_label.setText(f"Completed: {completed}")
        self.failed_tasks_label.setText(f"Failed: {failed}")

    def get_task_count(self) -> int:
        """Get total number of tasks"""
        return len(self.tasks)

    def get_active_count(self) -> int:
        """Get number of active tasks"""
        return sum(1 for task in self.tasks.values() if not task["completed"])

    def get_completed_count(self) -> int:
        """Get number of completed tasks"""
        return sum(1 for task in self.tasks.values() if task["completed"])

    def clear_completed_tasks(self):
        """Remove completed tasks from display"""
        completed_tasks = [name for name, info in self.tasks.items() if info["completed"]]

        for task_name in completed_tasks:
            widget = self.tasks[task_name]["widget"]
            self.tasks_layout.removeWidget(widget)
            widget.deleteLater()
            del self.tasks[task_name]

        self.update_summary()
